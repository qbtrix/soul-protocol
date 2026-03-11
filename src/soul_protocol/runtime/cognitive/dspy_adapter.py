# dspy_adapter.py — Bridge between DSPy modules and Soul Protocol's CognitiveProcessor.
# Created: feat/dspy-integration — DSPyCognitiveProcessor is a drop-in replacement
#   for CognitiveProcessor that routes significance assessment, query expansion,
#   and fact extraction through DSPy modules instead of hand-written prompts.
#   Handles async/sync bridge (DSPy is sync-first, Soul is async).
#   Falls back to heuristic path on any DSPy failure.

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from soul_protocol.runtime.types import (
    Interaction,
    MemoryEntry,
    MemoryType,
    SignificanceScore,
    SomaticMarker,
)

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.dspy_modules import (
        FactExtractor,
        QueryExpander,
        SignificanceGate,
    )


class DSPyCognitiveProcessor:
    """Drop-in replacement for CognitiveProcessor that uses DSPy modules.

    Uses DSPy's learnable/optimizable modules for:
    - Significance assessment (should this interaction be stored?)
    - Query expansion (generate multiple search queries for better recall)
    - Fact extraction (pull discrete facts from interactions)

    All other cognitive tasks (sentiment, entities, self-model, reflection)
    still flow through the standard CognitiveProcessor. This processor
    is meant to augment, not fully replace, the existing pipeline.

    The async/sync bridge runs DSPy calls in a thread pool executor
    since DSPy modules are synchronous.
    """

    def __init__(
        self,
        lm_model: str = "anthropic/claude-haiku-4-5-20251001",
        optimized_path: str | None = None,
    ):
        """Initialize DSPy processor with a language model.

        Args:
            lm_model: DSPy-compatible model string (e.g. "anthropic/claude-haiku-4-5-20251001",
                "openai/gpt-4o-mini"). Passed to dspy.LM().
            optimized_path: Optional path to a directory containing
                previously optimized module weights. If provided, loads
                optimized modules instead of using defaults.
        """
        import dspy

        self._lm = dspy.LM(lm_model)
        dspy.configure(lm=self._lm)

        from soul_protocol.runtime.cognitive.dspy_modules import (
            FactExtractor,
            QueryExpander,
            SignificanceGate,
        )

        self._significance_gate: SignificanceGate = SignificanceGate()
        self._query_expander: QueryExpander = QueryExpander()
        self._fact_extractor: FactExtractor = FactExtractor()

        if optimized_path:
            self.load_optimized(optimized_path)

    async def assess_significance(
        self,
        interaction: Interaction,
        core_values: list[str],
        recent_contents: list[str],
    ) -> SignificanceScore:
        """Use DSPy significance gate instead of heuristic.

        Runs the DSPy module in a thread executor to bridge sync→async.

        Args:
            interaction: The interaction to evaluate.
            core_values: The soul's core values.
            recent_contents: Recent episodic memory contents for novelty.

        Returns:
            SignificanceScore compatible with the existing pipeline.
        """
        recent_context = "\n".join(f"- {c[:100]}" for c in recent_contents[-5:])

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self._significance_gate.forward(
                    user_input=interaction.user_input,
                    agent_output=interaction.agent_output,
                    core_values=core_values,
                    recent_context=recent_context,
                ),
            )

            # Parse DSPy prediction into SignificanceScore
            novelty = _safe_float(getattr(result, "novelty", 0.5))
            emotional = _safe_float(getattr(result, "emotional_intensity", 0.3))
            factual = _safe_float(getattr(result, "factual_importance", 0.3))

            # Map factual_importance to goal_relevance for compatibility
            return SignificanceScore(
                novelty=_clamp(novelty, 0.0, 1.0),
                emotional_intensity=_clamp(emotional, 0.0, 1.0),
                goal_relevance=_clamp(factual, 0.0, 1.0),
            )
        except Exception:
            # Fall back to heuristic on any failure
            from soul_protocol.runtime.memory.attention import compute_significance

            return compute_significance(interaction, core_values, recent_contents)

    async def expand_query(
        self,
        query: str,
        personality_summary: str = "",
    ) -> list[str]:
        """Expand a recall query into multiple variations for better retrieval.

        Args:
            query: The original recall query.
            personality_summary: Optional personality context.

        Returns:
            List of expanded queries (always includes the original).
        """
        loop = asyncio.get_event_loop()
        try:
            expanded = await loop.run_in_executor(
                None,
                lambda: self._query_expander.forward(
                    query=query,
                    personality_summary=personality_summary,
                ),
            )
            # Always include the original query
            if query not in expanded:
                expanded = [query] + list(expanded)
            return expanded
        except Exception:
            return [query]

    async def extract_facts(
        self,
        interaction: Interaction,
        existing_facts: list[MemoryEntry] | None = None,
    ) -> list[MemoryEntry]:
        """Extract facts using DSPy module.

        Args:
            interaction: The interaction to extract facts from.
            existing_facts: Already-known facts for dedup.

        Returns:
            List of MemoryEntry objects of type SEMANTIC.
        """
        existing_str = ", ".join(
            f.content for f in (existing_facts or []) if not f.superseded_by
        )

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self._fact_extractor.forward(
                    user_input=interaction.user_input,
                    agent_output=interaction.agent_output,
                    existing_facts=existing_str,
                ),
            )

            facts_list = getattr(result, "facts", [])
            entries: list[MemoryEntry] = []
            for fact_text in facts_list:
                if isinstance(fact_text, str) and fact_text.strip():
                    entries.append(
                        MemoryEntry(
                            type=MemoryType.SEMANTIC,
                            content=fact_text.strip(),
                            importance=6,  # default; optimizer can learn better
                        )
                    )
            return entries
        except Exception:
            return []

    def load_optimized(self, path: str) -> None:
        """Load previously optimized DSPy modules from disk.

        Args:
            path: Directory containing optimized module JSON files.
        """
        import json
        from pathlib import Path

        base = Path(path)
        if (base / "significance_gate.json").exists():
            self._significance_gate._module.load(str(base / "significance_gate.json"))
        if (base / "query_expander.json").exists():
            self._query_expander._module.load(str(base / "query_expander.json"))
        if (base / "fact_extractor.json").exists():
            self._fact_extractor._module.load(str(base / "fact_extractor.json"))

    def save_modules(self, path: str) -> None:
        """Save current DSPy modules to disk.

        Args:
            path: Directory to save module JSON files to.
        """
        from pathlib import Path

        base = Path(path)
        base.mkdir(parents=True, exist_ok=True)
        self._significance_gate._module.save(str(base / "significance_gate.json"))
        self._query_expander._module.save(str(base / "query_expander.json"))
        self._fact_extractor._module.save(str(base / "fact_extractor.json"))


def _safe_float(value: object) -> float:
    """Convert a DSPy prediction value to float safely."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (ValueError, TypeError):
        return 0.5


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp a value between low and high."""
    return max(low, min(high, value))
