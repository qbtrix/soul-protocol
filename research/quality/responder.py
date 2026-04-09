# responder.py — Generate agent responses with and without soul context.
#
# Compares soul-enriched responses (personality, memories, self-model) against
# a generic baseline to measure whether having a soul improves response quality.
#
# Created: 2026-03-06

from __future__ import annotations

from dataclasses import dataclass

from soul_protocol import Soul

from ..haiku_engine import HaikuCognitiveEngine

BASELINE_SYSTEM_PROMPT = "You are a helpful AI assistant. Be concise and helpful."


@dataclass
class ResponsePair:
    """A paired comparison: the same user message answered with and without a soul."""

    user_message: str
    with_soul: str
    without_soul: str
    soul_system_prompt: str
    soul_context: str
    agent_name: str


class SoulResponder:
    """Generates responses using a Soul's full context or a bare baseline.

    The soul may have its own CognitiveEngine for internal cognition (sentiment,
    reflection, etc.), but response generation uses a dedicated engine passed here.
    This keeps cognitive costs and response-generation costs tracked separately.
    """

    def __init__(self, soul: Soul, engine: HaikuCognitiveEngine) -> None:
        self._soul = soul
        self._engine = engine

    async def generate_response(self, user_message: str) -> str:
        """Generate a response grounded in the soul's personality and memories.

        Builds the prompt as:
            System: {soul system prompt}
            {recalled memories + soul state context}
            User: {user_message}
        """
        system_prompt = self._soul.to_system_prompt()
        context = await self._soul.context_for(user_message, max_memories=5)

        prompt = _build_prompt(system_prompt, context, user_message)
        return await self._engine.think(prompt)

    async def generate_response_no_soul(self, user_message: str) -> str:
        """Generate a baseline response with no soul context.

        Uses a generic system prompt and no memory/state injection.
        """
        prompt = _build_prompt(BASELINE_SYSTEM_PROMPT, "", user_message)
        return await self._engine.think(prompt)


async def generate_comparison(
    soul: Soul,
    engine: HaikuCognitiveEngine,
    user_message: str,
) -> ResponsePair:
    """Generate both soul-enriched and baseline responses for comparison.

    Convenience function that wires up a SoulResponder, calls both generation
    paths, and returns a ResponsePair with full debug context attached.
    """
    responder = SoulResponder(soul, engine)

    # Capture the context that was fed to the soul-enriched path.
    soul_system_prompt = soul.to_system_prompt()
    soul_context = await soul.context_for(user_message, max_memories=5)

    with_soul = await responder.generate_response(user_message)
    without_soul = await responder.generate_response_no_soul(user_message)

    return ResponsePair(
        user_message=user_message,
        with_soul=with_soul,
        without_soul=without_soul,
        soul_system_prompt=soul_system_prompt,
        soul_context=soul_context,
        agent_name=soul.name,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_prompt(system: str, context: str, user_message: str) -> str:
    """Assemble a single prompt string for the HaikuCognitiveEngine.

    The engine's think() method accepts one prompt string (sent as a user
    message to the API), so we encode the system prompt and context inline
    using clear delimiters the model can parse.
    """
    parts = [f"System: {system}"]
    if context:
        parts.append(context.rstrip())
    parts.append(f"User: {user_message}")
    return "\n\n".join(parts)
