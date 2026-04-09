# conditions.py — Multi-condition response generation for quality ablation studies.
#
# Defines 4 experimental conditions to isolate the contribution of each
# Soul Protocol component (personality, memory, emotional state, bond):
#
#   1. FULL_SOUL        — personality + memories + somatic markers + bond
#   2. RAG_ONLY         — generic prompt + memories (no personality/emotion)
#   3. PROMPT_PERSONALITY — personality prompt + no memories
#   4. BARE_BASELINE    — generic prompt, no memories, no personality
#
# Created: 2026-03-07

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum

from soul_protocol import Soul
from soul_protocol.runtime.types import MemoryEntry

from ..haiku_engine import HaikuCognitiveEngine
from .responder import BASELINE_SYSTEM_PROMPT, _build_prompt


class Condition(Enum):
    """The four experimental conditions for quality ablation."""

    FULL_SOUL = "full_soul"
    RAG_ONLY = "rag_only"
    PROMPT_PERSONALITY = "prompt_personality"
    BARE_BASELINE = "bare_baseline"


CONDITION_LABELS: dict[Condition, str] = {
    Condition.FULL_SOUL: "Full Soul",
    Condition.RAG_ONLY: "RAG Only",
    Condition.PROMPT_PERSONALITY: "Personality Only",
    Condition.BARE_BASELINE: "No Memory/Personality",
}


@dataclass
class ConditionResponse:
    """The output of a single condition's response generation.

    Captures the response text plus the inputs that produced it,
    so downstream judges and analysis can inspect what was fed to the model.
    """

    condition: Condition
    response: str
    system_prompt: str
    context: str  # what was injected between system prompt and user message


def _format_memories_as_context(memories: list[MemoryEntry]) -> str:
    """Format recalled memories as plain-text context without emotional framing.

    Strips somatic markers, bond info, and personality-modulated language.
    Returns just the factual memory content so the RAG-Only condition gets
    the same data as Full Soul but without psychological scaffolding.
    """
    if not memories:
        return ""

    lines = ["[Recalled memories]"]
    for i, mem in enumerate(memories, 1):
        lines.append(f"  {i}. {mem.content}")
    return "\n".join(lines)


class MultiConditionResponder:
    """Generate responses under different experimental conditions.

    Each condition varies what information reaches the LLM:
    - System prompt: personality-modulated vs generic
    - Context: full soul context vs raw memories vs nothing

    All conditions use the same HaikuCognitiveEngine and the same Soul
    instance, so the underlying data (memories, personality) is identical —
    only the presentation changes.
    """

    def __init__(self, soul: Soul, engine: HaikuCognitiveEngine) -> None:
        self._soul = soul
        self._engine = engine

    async def generate(self, user_message: str, condition: Condition) -> ConditionResponse:
        """Generate a response under the specified condition."""
        if condition is Condition.FULL_SOUL:
            return await self._generate_full_soul(user_message)
        elif condition is Condition.RAG_ONLY:
            return await self._generate_rag_only(user_message)
        elif condition is Condition.PROMPT_PERSONALITY:
            return await self._generate_prompt_personality(user_message)
        elif condition is Condition.BARE_BASELINE:
            return await self._generate_bare_baseline(user_message)
        else:
            raise ValueError(f"Unknown condition: {condition}")

    async def generate_all(self, user_message: str) -> dict[Condition, ConditionResponse]:
        """Generate responses under all 4 conditions concurrently.

        Runs all conditions in parallel since they are independent reads
        against the same soul state. This keeps latency close to a single
        call rather than 4x sequential.
        """
        tasks = {cond: asyncio.create_task(self.generate(user_message, cond)) for cond in Condition}
        results: dict[Condition, ConditionResponse] = {}
        for cond, task in tasks.items():
            results[cond] = await task
        return results

    # ------------------------------------------------------------------
    # Condition implementations
    # ------------------------------------------------------------------

    async def _generate_full_soul(self, user_message: str) -> ConditionResponse:
        """Condition 1: Full soul — personality + memories + somatic state + bond.

        Uses soul.to_system_prompt() for the personality-modulated system prompt
        and soul.context_for() for significance-weighted memories with emotional
        state and bond information baked in.
        """
        system_prompt = self._soul.to_system_prompt()
        context = await self._soul.context_for(user_message, max_memories=5)
        prompt = _build_prompt(system_prompt, context, user_message)
        response = await self._engine.think(prompt)
        return ConditionResponse(
            condition=Condition.FULL_SOUL,
            response=response,
            system_prompt=system_prompt,
            context=context,
        )

    async def _generate_rag_only(self, user_message: str) -> ConditionResponse:
        """Condition 2: RAG only — generic prompt + raw memory retrieval.

        Uses the same recall path as the full soul (soul.recall) so the
        retrieved memories are identical. But strips all emotional framing,
        bond info, and personality from the prompt. This isolates memory's
        contribution to response quality.
        """
        memories = await self._soul.recall(user_message, limit=5)
        context = _format_memories_as_context(memories)
        prompt = _build_prompt(BASELINE_SYSTEM_PROMPT, context, user_message)
        response = await self._engine.think(prompt)
        return ConditionResponse(
            condition=Condition.RAG_ONLY,
            response=response,
            system_prompt=BASELINE_SYSTEM_PROMPT,
            context=context,
        )

    async def _generate_prompt_personality(self, user_message: str) -> ConditionResponse:
        """Condition 3: Personality only — OCEAN-modulated prompt, no memories.

        Uses the full personality system prompt (same as full soul) but passes
        no context at all — no memories, no emotional state, no bond info.
        This isolates personality's contribution without memory.
        """
        system_prompt = self._soul.to_system_prompt()
        prompt = _build_prompt(system_prompt, "", user_message)
        response = await self._engine.think(prompt)
        return ConditionResponse(
            condition=Condition.PROMPT_PERSONALITY,
            response=response,
            system_prompt=system_prompt,
            context="",
        )

    async def _generate_bare_baseline(self, user_message: str) -> ConditionResponse:
        """Condition 4: Bare baseline — generic prompt, no memory, no personality.

        The control condition. A plain helpful-assistant prompt with nothing
        injected. Any quality difference between this and other conditions
        is attributable to the soul components.
        """
        prompt = _build_prompt(BASELINE_SYSTEM_PROMPT, "", user_message)
        response = await self._engine.think(prompt)
        return ConditionResponse(
            condition=Condition.BARE_BASELINE,
            response=response,
            system_prompt=BASELINE_SYSTEM_PROMPT,
            context="",
        )
