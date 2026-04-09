# dspy_modules.py — DSPy modules for optimizable cognitive tasks.
# Created: feat/dspy-integration — DSPy-optimizable SignificanceGate,
#   QueryExpander, and FactExtractor modules for the memory pipeline.
#   These replace hand-written prompts with learnable, optimizable versions.
#   All dspy imports are lazy — this module only works when dspy is installed.

from __future__ import annotations


def _import_dspy():
    """Lazy import dspy — raises ImportError with a helpful message."""
    try:
        import dspy

        return dspy
    except ImportError:
        raise ImportError(
            "DSPy is required for optimizable cognitive modules. "
            "Install it with: pip install soul-protocol[dspy]"
        )


class SignificanceGate:
    """DSPy-optimized significance gate for episodic memory storage.

    Replaces the heuristic significance scoring with a learnable module
    that can be optimized via MIPROv2 to better distinguish important
    interactions from noise.
    """

    def __init__(self):
        dspy = _import_dspy()
        self._module = dspy.ChainOfThought(
            "user_input, agent_output, core_values: list[str], recent_context: str -> "
            "should_store: bool, novelty: float, emotional_intensity: float, "
            "factual_importance: float, reasoning: str"
        )

    def forward(
        self, user_input: str, agent_output: str, core_values: list[str], recent_context: str = ""
    ) -> object:
        """Assess whether an interaction should be stored in episodic memory.

        Args:
            user_input: The user's message.
            agent_output: The agent's response.
            core_values: The soul's core values.
            recent_context: Summary of recent interactions for novelty comparison.

        Returns:
            DSPy Prediction with should_store, novelty, emotional_intensity,
            factual_importance, and reasoning fields.
        """
        return self._module(
            user_input=user_input,
            agent_output=agent_output,
            core_values=core_values,
            recent_context=recent_context,
        )


class QueryExpander:
    """Generate multiple query variations for better memory recall.

    The heuristic recall engine uses token overlap / BM25, which misses
    semantic matches. This module expands a single query into multiple
    phrasings that are more likely to surface relevant memories.
    """

    def __init__(self):
        dspy = _import_dspy()
        self._module = dspy.Predict(
            "query, personality_summary: str -> expanded_queries: list[str]"
        )

    def forward(self, query: str, personality_summary: str = "") -> list[str]:
        """Expand a query into multiple search variations.

        Args:
            query: The original recall query.
            personality_summary: Optional personality context for
                persona-aware expansion.

        Returns:
            List of expanded query strings.
        """
        result = self._module(query=query, personality_summary=personality_summary)
        return result.expanded_queries


class FactExtractor:
    """Extract discrete memorable facts from interactions.

    Replaces regex-based fact extraction with an LLM-powered module
    that can be optimized to identify more nuanced factual content
    (preferences, life events, emotional states, etc.).
    """

    def __init__(self):
        dspy = _import_dspy()
        self._module = dspy.ChainOfThought(
            "user_input, agent_output, existing_facts: str -> "
            "facts: list[str], is_update: bool, reasoning: str"
        )

    def forward(self, user_input: str, agent_output: str, existing_facts: str = "") -> object:
        """Extract facts from an interaction.

        Args:
            user_input: The user's message.
            agent_output: The agent's response.
            existing_facts: Comma-separated list of already-known facts
                for deduplication and update detection.

        Returns:
            DSPy Prediction with facts (list of strings), is_update (bool),
            and reasoning (str) fields.
        """
        return self._module(
            user_input=user_input,
            agent_output=agent_output,
            existing_facts=existing_facts,
        )
