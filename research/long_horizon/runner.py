# runner.py — Long-horizon ablation runner.
# Updated: 2026-03-12 — Added comment documenting private attribute access for
#   episodic/semantic counts (matches pattern in conditions.py).
# Updated: 2026-03-11 — Added use_dspy_significance option. When enabled, the
#   full_soul condition creates Soul with use_dspy=True, routing significance
#   assessment through the DSPy-optimized gate instead of heuristics.
# Updated: 2026-03-11 — Added DSPy query expansion support for enhanced recall.
# Created: 2026-03-11
# Runs long-horizon scenarios (100+ turns) through 4 ablation conditions
# and collects infrastructure metrics: recall precision, memory efficiency,
# bond strength, memory count per tier.
#
# Works WITHOUT an LLM by default (no API key needed).
# Optionally uses DSPy QueryExpander for enhanced recall (needs API key).
# The runner measures infrastructure metrics (memory count, recall hit rate, bond),
# not response quality (which needs LLM judges and is a separate concern).

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from soul_protocol.runtime.types import Interaction

from .scenarios import LongHorizonScenario

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Condition definitions for long-horizon study
# ---------------------------------------------------------------------------


class ConditionType:
    """The 4 ablation conditions for long-horizon evaluation."""

    FULL_SOUL = "full_soul"
    RAG_ONLY = "rag_only"
    PERSONALITY_ONLY = "personality_only"
    BARE_BASELINE = "bare_baseline"


ALL_CONDITIONS = [
    ConditionType.FULL_SOUL,
    ConditionType.RAG_ONLY,
    ConditionType.PERSONALITY_ONLY,
    ConditionType.BARE_BASELINE,
]


# ---------------------------------------------------------------------------
# Per-condition result
# ---------------------------------------------------------------------------


@dataclass
class ConditionResult:
    """Metrics collected for one condition on one scenario."""

    condition: str
    scenario_id: str
    total_turns: int = 0
    duration_seconds: float = 0.0

    # Recall precision: fraction of test points where the expected content was found
    recall_hits: int = 0
    recall_misses: int = 0
    recall_results: list[dict[str, Any]] = field(default_factory=list)

    # Memory efficiency
    total_memories: int = 0
    episodic_count: int = 0
    semantic_count: int = 0

    # Bond
    bond_strength: float = 0.0
    bond_trajectory: list[float] = field(default_factory=list)

    # Memory growth over time: (turn_index, memory_count)
    memory_growth: list[tuple[int, int]] = field(default_factory=list)

    @property
    def recall_precision(self) -> float:
        total = self.recall_hits + self.recall_misses
        return self.recall_hits / total if total > 0 else 0.0

    @property
    def memory_efficiency(self) -> float:
        """Memories stored / total turns. Lower = more selective."""
        return self.total_memories / self.total_turns if self.total_turns > 0 else 0.0


@dataclass
class ScenarioResults:
    """All condition results for one scenario."""

    scenario_id: str
    scenario_name: str
    condition_results: dict[str, ConditionResult] = field(default_factory=dict)


@dataclass
class LongHorizonResults:
    """Complete results across all scenarios and conditions."""

    scenario_results: list[ScenarioResults] = field(default_factory=list)
    total_duration: float = 0.0

    def to_rows(self) -> list[dict[str, Any]]:
        """Flatten to tabular rows for analysis."""
        rows = []
        for sr in self.scenario_results:
            for cond, cr in sr.condition_results.items():
                rows.append(
                    {
                        "scenario": sr.scenario_id,
                        "scenario_name": sr.scenario_name,
                        "condition": cond,
                        "total_turns": cr.total_turns,
                        "recall_precision": cr.recall_precision,
                        "recall_hits": cr.recall_hits,
                        "recall_total": cr.recall_hits + cr.recall_misses,
                        "memory_efficiency": cr.memory_efficiency,
                        "total_memories": cr.total_memories,
                        "episodic_count": cr.episodic_count,
                        "semantic_count": cr.semantic_count,
                        "bond_strength": cr.bond_strength,
                        "duration_seconds": cr.duration_seconds,
                    }
                )
        return rows


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class LongHorizonRunner:
    """Run long-horizon scenarios through all ablation conditions.

    Uses Soul Protocol's observe/recall APIs to measure infrastructure
    metrics without needing an LLM for response generation.
    """

    def __init__(
        self,
        conditions: list[str] | None = None,
        seed: int = 42,
        use_dspy_recall: bool = False,
        use_dspy_significance: bool = False,
        dspy_model: str = "anthropic/claude-haiku-4-5-20251001",
        optimized_modules_path: str | None = None,
    ) -> None:
        self.conditions = conditions or ALL_CONDITIONS
        self.seed = seed
        self.use_dspy_recall = use_dspy_recall
        self.use_dspy_significance = use_dspy_significance
        self.dspy_model = dspy_model
        self.optimized_modules_path = optimized_modules_path
        self._dspy_processor = None

        if use_dspy_recall:
            try:
                from soul_protocol.runtime.cognitive.dspy_adapter import DSPyCognitiveProcessor

                self._dspy_processor = DSPyCognitiveProcessor(
                    lm_model=dspy_model,
                    optimized_path=optimized_modules_path,
                )
                logger.info("DSPy query expansion enabled for recall")
            except Exception as e:
                logger.warning("DSPy init failed, falling back to heuristic: %s", e)
                self.use_dspy_recall = False

    async def run_scenario(
        self,
        scenario: LongHorizonScenario,
    ) -> ScenarioResults:
        """Run a single scenario through all conditions."""
        results = ScenarioResults(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
        )

        for condition in self.conditions:
            logger.info(
                "Running scenario=%s condition=%s (%d turns)",
                scenario.scenario_id,
                condition,
                scenario.turn_count,
            )
            cr = await self._run_condition(scenario, condition)
            results.condition_results[condition] = cr

        return results

    async def run_all(
        self,
        scenarios: list[LongHorizonScenario],
    ) -> LongHorizonResults:
        """Run all scenarios through all conditions."""
        t_start = time.monotonic()
        results = LongHorizonResults()

        for scenario in scenarios:
            sr = await self.run_scenario(scenario)
            results.scenario_results.append(sr)

        results.total_duration = time.monotonic() - t_start
        return results

    async def _run_condition(
        self,
        scenario: LongHorizonScenario,
        condition: str,
    ) -> ConditionResult:
        """Run one scenario under one condition, collecting metrics."""
        t_start = time.monotonic()
        result = ConditionResult(
            condition=condition,
            scenario_id=scenario.scenario_id,
            total_turns=scenario.turn_count,
        )

        # Build the soul for this condition
        soul = await self._create_soul(condition)

        # Feed all turns through the pipeline
        for turn_idx, (user_input, agent_output) in enumerate(scenario.turns):
            interaction = Interaction(
                user_input=user_input,
                agent_output=agent_output,
            )

            if condition == ConditionType.FULL_SOUL:
                await soul.observe(interaction)
                if turn_idx % 50 == 0:
                    logger.info("  turn %d/%d processed", turn_idx, scenario.turn_count)
            elif condition == ConditionType.RAG_ONLY:
                # Store everything directly, bypass psychology pipeline
                content = f"User: {user_input}\nAgent: {agent_output}"
                await soul.remember(content, importance=5)
            elif condition == ConditionType.PERSONALITY_ONLY:
                # No memory storage, personality only via system prompt
                pass
            elif condition == ConditionType.BARE_BASELINE:
                # Nothing at all
                pass

            # Track memory growth periodically
            if turn_idx % 10 == 0 or turn_idx == scenario.turn_count - 1:
                mem_count = soul.memory_count if condition != ConditionType.BARE_BASELINE else 0
                result.memory_growth.append((turn_idx, mem_count))

            # Track bond for full soul
            if condition == ConditionType.FULL_SOUL:
                result.bond_trajectory.append(soul.bond.bond_strength)

        # Collect final state metrics
        if condition not in (ConditionType.PERSONALITY_ONLY, ConditionType.BARE_BASELINE):
            result.total_memories = soul.memory_count
            # Count per tier
            # NOTE: Accessing internal store state for metrics — matches pattern in conditions.py
            result.episodic_count = len(soul._memory._episodic._memories)
            result.semantic_count = len(soul._memory._semantic._facts)

        if condition == ConditionType.FULL_SOUL:
            result.bond_strength = soul.bond.bond_strength

        # Run recall tests at each test point
        for tp in scenario.test_points:
            if tp.test_type != "recall":
                continue

            if condition in (ConditionType.PERSONALITY_ONLY, ConditionType.BARE_BASELINE):
                # No memory means no recall
                result.recall_misses += 1
                result.recall_results.append(
                    {
                        "query": tp.query,
                        "expected": tp.expected_content,
                        "hit": False,
                        "description": tp.description,
                        "recalled": [],
                    }
                )
                continue

            # Use DSPy query expansion if available
            queries = [tp.query]
            if self.use_dspy_recall and self._dspy_processor:
                try:
                    queries = await self._dspy_processor.expand_query(tp.query)
                except Exception:
                    pass  # fall back to original query

            # Try all query variations
            all_recalled = []
            for q in queries:
                recalled = await soul.recall(q, limit=10)
                all_recalled.extend(recalled)

            # Deduplicate by content
            seen = set()
            unique_recalled = []
            for m in all_recalled:
                if m.content not in seen:
                    seen.add(m.content)
                    unique_recalled.append(m)

            recalled_contents = [m.content.lower() for m in unique_recalled]
            expected_lower = tp.expected_content.lower()

            hit = any(expected_lower in content for content in recalled_contents)

            if hit:
                result.recall_hits += 1
            else:
                result.recall_misses += 1

            result.recall_results.append(
                {
                    "query": tp.query,
                    "queries_used": queries,
                    "expected": tp.expected_content,
                    "hit": hit,
                    "description": tp.description,
                    "recalled": [m.content for m in unique_recalled[:3]],
                }
            )

        result.duration_seconds = time.monotonic() - t_start
        return result

    async def _create_soul(self, condition: str):
        """Create a Soul instance configured for the given condition."""
        from soul_protocol import Soul

        ocean = {
            "openness": 0.7,
            "conscientiousness": 0.6,
            "extraversion": 0.5,
            "agreeableness": 0.8,
            "neuroticism": 0.3,
        }

        if condition == ConditionType.PERSONALITY_ONLY:
            # Has personality (OCEAN) but no memory will be stored
            soul = await Soul.birth(
                name="LongHorizonAgent",
                archetype="The Empathetic Companion",
                values=["empathy", "curiosity", "reliability"],
                ocean=ocean,
                persona="I am a supportive companion who remembers and cares.",
            )
        elif condition == ConditionType.BARE_BASELINE:
            # Minimal soul — no personality emphasis, no memory
            soul = await Soul.birth(
                name="BaselineAgent",
                archetype="Generic Assistant",
                values=[],
                persona="I am an assistant.",
            )
        elif condition == ConditionType.FULL_SOUL and self.use_dspy_significance:
            # Full soul with DSPy-optimized significance gate
            soul = await Soul.birth(
                name="LongHorizonAgent",
                archetype="The Empathetic Companion",
                values=["empathy", "curiosity", "reliability"],
                ocean=ocean,
                persona="I am a supportive companion who remembers and cares.",
                use_dspy=True,
                dspy_model=self.dspy_model,
                dspy_optimized_path=self.optimized_modules_path,
            )
        else:
            # Full soul (heuristic) or RAG-only: both get OCEAN personality
            soul = await Soul.birth(
                name="LongHorizonAgent",
                archetype="The Empathetic Companion",
                values=["empathy", "curiosity", "reliability"],
                ocean=ocean,
                persona="I am a supportive companion who remembers and cares.",
            )

        return soul
