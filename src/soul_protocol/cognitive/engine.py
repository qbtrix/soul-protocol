# cognitive/engine.py — CognitiveEngine protocol, HeuristicEngine, CognitiveProcessor.
# Created: v0.2.1 — LLM as first-class citizen for soul cognition.
#   CognitiveEngine: single-method protocol consumers implement.
#   HeuristicEngine: zero-dependency fallback wrapping v0.2.0 heuristic modules.
#   CognitiveProcessor: internal orchestrator delegating psychology tasks to engine.
# Updated: 2026-03-04 — Fix: _is_heuristic_only now checks isinstance(engine, HeuristicEngine)
#   only, dropping the "and fallback is None" condition. Previously, passing
#   engine=HeuristicEngine() alongside any fallback set _is_heuristic_only=False,
#   routing update_self_model() through the LLM path where _self_reflection()
#   returned empty self_images — causing zero domain discovery.

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from soul_protocol.cognitive.prompts import (
    ENTITY_EXTRACTION_PROMPT,
    FACT_EXTRACTION_PROMPT,
    REFLECT_PROMPT,
    SELF_REFLECTION_PROMPT,
    SENTIMENT_PROMPT,
    SIGNIFICANCE_PROMPT,
)
from soul_protocol.types import (
    Interaction,
    MemoryEntry,
    MemoryType,
    ReflectionResult,
    SelfImage,
    SignificanceScore,
    SomaticMarker,
)

if TYPE_CHECKING:
    from soul_protocol.memory.self_model import SelfModelManager


def _heuristic_sentiment(text: str) -> SomaticMarker:
    """Lazy wrapper for v0.2.0 sentiment heuristic (avoids circular import)."""
    from soul_protocol.memory.sentiment import detect_sentiment

    return detect_sentiment(text)


def _heuristic_significance(
    interaction: Interaction,
    core_values: list[str],
    recent_contents: list[str],
) -> SignificanceScore:
    """Lazy wrapper for v0.2.0 significance heuristic (avoids circular import)."""
    from soul_protocol.memory.attention import compute_significance

    return compute_significance(interaction, core_values, recent_contents)


# ---------------------------------------------------------------------------
# CognitiveEngine protocol — the ONE interface consumers provide
# ---------------------------------------------------------------------------


@runtime_checkable
class CognitiveEngine(Protocol):
    """Interface for the soul's cognitive processing.

    The consumer provides an LLM via this interface. The soul uses it
    to think about emotions, significance, facts, and identity.

    Simplest implementation:
        class MyCognitive:
            async def think(self, prompt: str) -> str:
                return await my_llm_client.complete(prompt)
    """

    async def think(self, prompt: str) -> str: ...


# ---------------------------------------------------------------------------
# HeuristicEngine — zero-dependency fallback
# ---------------------------------------------------------------------------


class HeuristicEngine:
    """Zero-dependency fallback that wraps v0.2.0 heuristic modules.

    Used when no LLM is available (offline, testing, cost-constrained).
    Routes prompts to appropriate heuristic based on [TASK:xxx] markers
    and returns structured JSON mimicking LLM output format.
    """

    async def think(self, prompt: str) -> str:
        """Route prompt to appropriate heuristic based on task marker."""
        task = _extract_task_marker(prompt)

        if task == "sentiment":
            return self._sentiment(prompt)
        elif task == "significance":
            return self._significance(prompt)
        elif task == "extract_facts":
            return self._extract_facts(prompt)
        elif task == "extract_entities":
            return self._extract_entities(prompt)
        elif task == "self_reflection":
            return self._self_reflection(prompt)
        elif task == "reflect":
            return json.dumps(
                {
                    "themes": [],
                    "summaries": [],
                    "promote": [],
                    "emotional_patterns": "insufficient data for reflection",
                    "self_insight": "",
                }
            )

        return json.dumps({"error": f"unknown task: {task}"})

    def _sentiment(self, prompt: str) -> str:
        """Extract text from sentiment prompt and run heuristic."""
        text = _extract_field(prompt, "Text:")
        marker = _heuristic_sentiment(text)
        return json.dumps(
            {
                "valence": marker.valence,
                "arousal": marker.arousal,
                "label": marker.label,
            }
        )

    def _significance(self, prompt: str) -> str:
        """Run simplified significance heuristic from prompt text."""
        user_input = _extract_field(prompt, "User:")
        somatic = _heuristic_sentiment(user_input)
        emotional = min(1.0, somatic.arousal + abs(somatic.valence) * 0.3)
        return json.dumps(
            {
                "novelty": 0.5,
                "emotional_intensity": round(emotional, 3),
                "goal_relevance": 0.3,
                "reasoning": "heuristic estimate",
            }
        )

    def _extract_facts(self, prompt: str) -> str:
        """Run simplified fact extraction from prompt text."""
        user_input = _extract_field(prompt, "User:")
        facts: list[dict] = []
        name_match = re.search(r"my name is (\w+)", user_input, re.IGNORECASE)
        if name_match:
            facts.append(
                {
                    "content": f"User's name is {name_match.group(1)}",
                    "importance": 9,
                }
            )
        return json.dumps(facts)

    def _extract_entities(self, prompt: str) -> str:
        """Run simplified entity extraction from prompt text."""
        return json.dumps([])

    def _self_reflection(self, prompt: str) -> str:
        """Return minimal self-reflection."""
        return json.dumps(
            {
                "self_images": [],
                "insights": "heuristic mode — limited self-reflection",
                "relationship_notes": {},
            }
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_task_marker(prompt: str) -> str:
    """Extract [TASK:xxx] marker from prompt text."""
    match = re.search(r"\[TASK:(\w+)\]", prompt)
    return match.group(1) if match else "unknown"


def _extract_field(prompt: str, field: str) -> str:
    """Extract the value after a field label in the prompt.

    Captures everything after 'Field:' until the next blank line,
    next field label (line starting with uppercase + colon), or end of string.
    """
    pattern = re.compile(
        rf"^\s*{re.escape(field)}\s*(.*?)(?:\n\n|\n\s*[A-Z][\w\s]*:|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(prompt)
    return match.group(1).strip() if match else ""


def _parse_json(text: str) -> dict | list:
    """Extract JSON from LLM response, handling markdown fences and preamble.

    Tries in order:
    1. Direct JSON parse
    2. Extract from ```json ... ``` blocks
    3. Find first { or [ and parse from there
    """
    text = text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Markdown fenced block
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find first { or [
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return json.loads(text[i:])
            except json.JSONDecodeError:
                continue

    raise json.JSONDecodeError("No valid JSON found", text, 0)


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value between low and high."""
    return max(low, min(high, float(value)))


# ---------------------------------------------------------------------------
# CognitiveProcessor — internal orchestrator
# ---------------------------------------------------------------------------


class CognitiveProcessor:
    """Internal orchestrator that uses a CognitiveEngine for psychology tasks.

    Handles prompt construction, response parsing, validation, and
    fallback to heuristics on parse failure.

    Two modes:
    - Heuristic-only: calls v0.2.0 functions directly for identical behavior
    - LLM-enhanced: constructs prompts, sends to engine, parses responses,
      falls back to heuristic on failure
    """

    def __init__(
        self,
        engine: CognitiveEngine,
        fallback: HeuristicEngine | None = None,
        fact_extractor: Callable[..., list[MemoryEntry]] | None = None,
        entity_extractor: Callable[..., list[dict]] | None = None,
    ) -> None:
        self._engine = engine
        self._fallback = fallback
        self._is_heuristic_only = isinstance(engine, HeuristicEngine)
        self._fact_extractor = fact_extractor
        self._entity_extractor = entity_extractor

    async def detect_sentiment(self, text: str) -> SomaticMarker:
        """Detect emotional sentiment from text."""
        # Fast path: direct heuristic call (identical to v0.2.0)
        if self._is_heuristic_only:
            return _heuristic_sentiment(text)

        prompt = SENTIMENT_PROMPT.format(text=text)
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            return SomaticMarker(
                valence=_clamp(data["valence"], -1.0, 1.0),
                arousal=_clamp(data["arousal"], 0.0, 1.0),
                label=data.get("label", "neutral"),
            )
        except Exception:
            if self._fallback:
                return _heuristic_sentiment(text)
            return SomaticMarker()

    async def assess_significance(
        self,
        interaction: Interaction,
        core_values: list[str],
        recent_contents: list[str],
    ) -> SignificanceScore:
        """Assess how significant an interaction is for episodic storage."""
        # Fast path: direct heuristic call (identical to v0.2.0)
        if self._is_heuristic_only:
            return _heuristic_significance(interaction, core_values, recent_contents)

        prompt = SIGNIFICANCE_PROMPT.format(
            values=", ".join(core_values) if core_values else "none specified",
            recent_summaries=("\n".join(f"- {r[:100]}" for r in recent_contents[-5:]) or "none"),
            user_input=interaction.user_input,
            agent_output=interaction.agent_output,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            return SignificanceScore(
                novelty=_clamp(data["novelty"], 0.0, 1.0),
                emotional_intensity=_clamp(data["emotional_intensity"], 0.0, 1.0),
                goal_relevance=_clamp(data["goal_relevance"], 0.0, 1.0),
            )
        except Exception:
            if self._fallback:
                return _heuristic_significance(interaction, core_values, recent_contents)
            return SignificanceScore()

    async def extract_facts(
        self,
        interaction: Interaction,
        existing_facts: list[MemoryEntry] | None = None,
    ) -> list[MemoryEntry]:
        """Extract semantic facts from an interaction."""
        # Fast path: delegate to MemoryManager's heuristic extractor
        if self._is_heuristic_only and self._fact_extractor:
            return self._fact_extractor(interaction)

        prompt = FACT_EXTRACTION_PROMPT.format(
            user_input=interaction.user_input,
            agent_output=interaction.agent_output,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            if not isinstance(data, list):
                data = data.get("facts", [])

            entries: list[MemoryEntry] = []
            for item in data:
                entries.append(
                    MemoryEntry(
                        type=MemoryType.SEMANTIC,
                        content=item["content"],
                        importance=min(10, max(1, int(item.get("importance", 5)))),
                    )
                )
            return entries
        except Exception:
            if self._fact_extractor:
                return self._fact_extractor(interaction)
            return []

    async def extract_entities(self, interaction: Interaction) -> list[dict]:
        """Extract named entities from an interaction."""
        # Fast path: delegate to MemoryManager's heuristic extractor
        if self._is_heuristic_only and self._entity_extractor:
            return self._entity_extractor(interaction)

        prompt = ENTITY_EXTRACTION_PROMPT.format(
            user_input=interaction.user_input,
            agent_output=interaction.agent_output,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            if not isinstance(data, list):
                data = data.get("entities", [])

            entities: list[dict] = []
            for item in data:
                entities.append(
                    {
                        "name": item["name"],
                        "type": item.get("type", "unknown"),
                        "relation": item.get("relation"),
                    }
                )
            return entities
        except Exception:
            if self._entity_extractor:
                return self._entity_extractor(interaction)
            return []

    async def update_self_model(
        self,
        interaction: Interaction,
        facts: list[MemoryEntry],
        self_model: SelfModelManager,
    ) -> None:
        """Update the soul's self-concept based on an interaction."""
        # Fast path: direct heuristic call (identical to v0.2.0)
        if self._is_heuristic_only:
            self_model.update_from_interaction(interaction, facts)
            return

        current_images = self_model.get_active_self_images()
        images_text = (
            "\n".join(
                f"- {img.domain}: confidence={img.confidence:.2f}, evidence={img.evidence_count}"
                for img in current_images
            )
            or "none yet"
        )

        recent_text = f"User: {interaction.user_input}\nAgent: {interaction.agent_output}"

        prompt = SELF_REFLECTION_PROMPT.format(
            soul_name="soul",
            current_self_images=images_text,
            recent_episodes=recent_text,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)

            for img_data in data.get("self_images", []):
                domain = img_data.get("domain", "")
                if domain:
                    existing = self_model._self_images.get(domain)
                    evidence = (existing.evidence_count + 1) if existing else 1
                    confidence = _clamp(img_data.get("confidence", 0.5), 0.0, 1.0)
                    self_model._self_images[domain] = SelfImage(
                        domain=domain,
                        confidence=confidence,
                        evidence_count=evidence,
                    )

            for entity, note in data.get("relationship_notes", {}).items():
                if entity and note:
                    self_model._relationship_notes[entity] = note

        except Exception:
            # Fallback to heuristic
            self_model.update_from_interaction(interaction, facts)

    async def reflect(
        self,
        recent_episodes: list[Any],
        current_self_model: dict,
        soul_name: str = "soul",
    ) -> ReflectionResult | None:
        """Run a reflection/consolidation pass (LLM-only).

        Returns None in heuristic-only mode — genuine reflection requires
        an LLM to reason about patterns across episodes.
        """
        if self._is_heuristic_only:
            return None

        episode_texts: list[str] = []
        for ep in recent_episodes[:20]:
            if isinstance(ep, MemoryEntry):
                episode_texts.append(f"- [{ep.created_at}] {ep.content}")
            elif isinstance(ep, dict):
                episode_texts.append(f"- {ep.get('content', str(ep))}")
            else:
                episode_texts.append(f"- {ep}")

        self_model_text = json.dumps(current_self_model, indent=2, default=str)

        prompt = REFLECT_PROMPT.format(
            soul_name=soul_name,
            count=len(episode_texts),
            episodes="\n".join(episode_texts) or "no recent episodes",
            self_model=self_model_text,
        )
        try:
            response = await self._engine.think(prompt)
            data = _parse_json(response)
            return ReflectionResult(
                themes=data.get("themes", []),
                summaries=data.get("summaries", []),
                emotional_patterns=data.get("emotional_patterns", ""),
                self_insight=data.get("self_insight", ""),
            )
        except Exception:
            return None
