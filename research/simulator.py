# simulator.py — Core simulation engine for the Soul Protocol ablation study.
#
# Runs the full factorial experiment: agents x conditions x use_cases.
# Each (agent, condition, use_case) triple produces one AgentRunMetrics.
# Execution is async with configurable batch parallelism to avoid overwhelming
# the Soul Protocol runtime. Failed runs are logged and skipped so one bad
# agent never crashes the whole experiment.
#
# Created: 2026-03-06
# Changes: Initial implementation — SimulationEngine, _run_single, SimulationResults.

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from soul_protocol.runtime.types import Interaction

from .agents import AgentProfile, UserProfile, generate_agents, generate_users
from .conditions import BaseCondition, ObserveResult, create_condition
from .config import ExperimentConfig, MemoryCondition, UseCase
from .metrics import (
    AgentRunMetrics,
    BondMetrics,
    EmotionalMetrics,
    MemoryEfficiencyMetrics,
    PersonalityMetrics,
    RecallMetrics,
    SkillMetrics,
)
from .scenarios import generate_scenarios

logger = logging.getLogger(__name__)

# Type alias for optional progress callbacks.
# Callback receives (completed_runs, total_runs, latest_label).
ProgressCallback = Callable[[int, int, str], None]


# ---------------------------------------------------------------------------
# Results container
# ---------------------------------------------------------------------------


@dataclass
class SimulationResults:
    """Aggregated output from a full experiment run."""

    all_metrics: list[AgentRunMetrics] = field(default_factory=list)
    config: ExperimentConfig = field(default_factory=ExperimentConfig)
    duration_seconds: float = 0.0
    errors: list[dict[str, Any]] = field(default_factory=list)

    # -- Convenience accessors ------------------------------------------------

    def to_dataframe_rows(self) -> list[dict[str, Any]]:
        """Flatten every AgentRunMetrics into a dict row for tabular analysis."""
        return [m.to_row() for m in self.all_metrics]

    def save(self, path: str | Path) -> Path:
        """Persist results as JSON.  Returns the resolved path."""
        dest = Path(path)
        if dest.is_dir():
            dest = dest / "results.json"
        dest.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "config": {
                "num_agents": self.config.num_agents,
                "interactions_per_agent": self.config.interactions_per_agent,
                "num_sessions": self.config.num_sessions,
                "interactions_per_session": self.config.interactions_per_session,
                "conditions": [c.value for c in self.config.conditions],
                "use_cases": [u.value for u in self.config.use_cases],
                "random_seed": self.config.random_seed,
                "significance_threshold": self.config.significance_threshold,
                "activation_decay_rate": self.config.activation_decay_rate,
                "total_runs": self.config.total_runs,
            },
            "duration_seconds": self.duration_seconds,
            "total_completed": len(self.all_metrics),
            "total_errors": len(self.errors),
            "rows": self.to_dataframe_rows(),
            "errors": self.errors,
        }

        dest.write_text(json.dumps(payload, indent=2, default=str))
        logger.info("Results saved to %s", dest)
        return dest


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------


class SimulationEngine:
    """Orchestrates the full factorial experiment.

    For each (agent, condition, use_case) triple the engine:
      1. Creates a fresh condition instance
      2. Sets it up with the agent profile
      3. Runs every generated scenario (observe turns, then test recall)
      4. Collects metrics into AgentRunMetrics

    Runs are batched with ``asyncio.gather`` for throughput.  A failed
    individual run is caught, logged, and skipped — the experiment
    continues.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        *,
        batch_size: int = 50,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.config = config
        self.batch_size = batch_size
        self._progress_cb = progress_callback

        # Pre-generate agents once (shared across conditions / use cases).
        self._agents: list[AgentProfile] = []
        # User pools keyed by use-case value string.
        self._users: dict[str, list[UserProfile]] = {}

    # -- Public API -----------------------------------------------------------

    async def run(self) -> SimulationResults:
        """Execute the full experiment and return collected results."""
        t_start = time.monotonic()

        # Generate agent pool.
        self._agents = generate_agents(
            n=self.config.num_agents,
            seed=self.config.random_seed,
            ocean_mean=self.config.ocean_mean,
            ocean_std=self.config.ocean_std,
        )

        # Generate user pools per use-case.
        for uc in self.config.use_cases:
            self._users[uc.value] = generate_users(
                n=self.config.num_agents,
                seed=self.config.random_seed,
                use_case=uc.value,
            )

        # Build the full run manifest: every (agent, condition, use_case) triple.
        run_specs: list[_RunSpec] = []
        for agent in self._agents:
            for cond in self.config.conditions:
                for uc in self.config.use_cases:
                    user = self._users[uc.value][agent.agent_id]
                    run_specs.append(
                        _RunSpec(
                            agent=agent,
                            user=user,
                            condition_type=cond,
                            use_case=uc,
                        )
                    )

        total = len(run_specs)
        logger.info(
            "Starting experiment: %d runs (%d agents x %d conditions x %d use-cases)",
            total,
            len(self._agents),
            len(self.config.conditions),
            len(self.config.use_cases),
        )

        # Execute in batches.
        results = SimulationResults(config=self.config)
        completed = 0

        for batch_start in range(0, total, self.batch_size):
            batch = run_specs[batch_start : batch_start + self.batch_size]
            coros = [self._run_guarded(spec) for spec in batch]
            batch_results = await asyncio.gather(*coros)

            for outcome in batch_results:
                if isinstance(outcome, AgentRunMetrics):
                    results.all_metrics.append(outcome)
                else:
                    # outcome is an error dict
                    results.errors.append(outcome)

            completed += len(batch)
            label = f"batch {batch_start // self.batch_size + 1}"
            self._report_progress(completed, total, label)

        results.duration_seconds = time.monotonic() - t_start
        logger.info(
            "Experiment complete: %d successful, %d errors, %.1fs",
            len(results.all_metrics),
            len(results.errors),
            results.duration_seconds,
        )
        return results

    # -- Internal helpers -----------------------------------------------------

    def _report_progress(self, completed: int, total: int, label: str) -> None:
        """Emit progress via callback and/or logger."""
        pct = completed / total * 100 if total else 0
        msg = f"[{completed}/{total}] ({pct:.1f}%) — {label}"
        logger.info(msg)
        if self._progress_cb is not None:
            self._progress_cb(completed, total, label)

    async def _run_guarded(self, spec: _RunSpec) -> AgentRunMetrics | dict[str, Any]:
        """Run a single spec, catching errors so the experiment never crashes."""
        try:
            return await self._run_single(
                agent_profile=spec.agent,
                user_profile=spec.user,
                condition_type=spec.condition_type,
                use_case=spec.use_case,
            )
        except Exception as exc:  # noqa: BLE001
            error_info = {
                "agent_id": spec.agent.agent_id,
                "condition": spec.condition_type.value,
                "use_case": spec.use_case.value,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
            logger.warning(
                "Run failed for agent=%d cond=%s uc=%s: %s",
                spec.agent.agent_id,
                spec.condition_type.value,
                spec.use_case.value,
                exc,
            )
            return error_info

    async def _run_single(
        self,
        agent_profile: AgentProfile,
        user_profile: UserProfile,
        condition_type: MemoryCondition,
        use_case: UseCase,
    ) -> AgentRunMetrics:
        """Execute all scenarios for one (agent, condition, use_case) triple.

        Steps:
          1. Create and set up the condition instance.
          2. Generate scenarios for the user/use-case pair.
          3. For each scenario, iterate turns — call condition.observe().
          4. After turns, run recall queries and measure hit accuracy.
          5. Aggregate all measurements into AgentRunMetrics.
        """
        condition: BaseCondition = create_condition(condition_type)
        await condition.setup(agent_profile)

        scenarios = generate_scenarios(
            user=user_profile,
            use_case=use_case.value,
            seed=self.config.random_seed,
        )

        # Metric accumulators
        recall_metrics = RecallMetrics()
        emotional_metrics = EmotionalMetrics()
        personality_metrics = PersonalityMetrics()
        efficiency_metrics = MemoryEfficiencyMetrics()
        bond_metrics = BondMetrics()
        skill_metrics = SkillMetrics()

        interaction_count = 0

        for scenario in scenarios:
            # ---- Run turns --------------------------------------------------
            for turn in scenario.turns:
                interaction = Interaction(
                    user_input=turn.user_input,
                    agent_output=turn.agent_output,
                )
                result: ObserveResult = await condition.observe(interaction)
                interaction_count += 1

                # Track significance scores for efficiency analysis.
                efficiency_metrics.significance_scores.append(result.significance_score)

                # Track memory growth: (interaction_count, memory_count).
                efficiency_metrics.memory_growth_rate.append(
                    (interaction_count, result.memory_count)
                )

                # Track bond trajectory.
                bond_metrics.strength_trajectory.append(result.bond_strength)

                # Record bond milestones at 25%, 50%, 75% thresholds.
                for milestone in (25, 50, 75):
                    threshold = milestone / 100
                    if (
                        result.bond_strength >= threshold
                        and milestone not in bond_metrics.interaction_count_at_milestones
                    ):
                        bond_metrics.interaction_count_at_milestones[milestone] = interaction_count

                # Track skill counts over time.
                if result.skills_count > skill_metrics.skills_discovered:
                    skill_metrics.skills_discovered = result.skills_count

                # Emotional tracking: compare somatic valence to expected emotion.
                if turn.expected_emotion:
                    # A somatic valence was returned and is non-None — record
                    # whether the condition even attempted emotional tracking.
                    if result.somatic_valence is not None:
                        # Heuristic: negative emotions should produce negative
                        # valence, positive emotions positive valence.
                        expected_negative = turn.expected_emotion in {
                            "frustrated",
                            "stressed",
                            "anxious",
                            "sad",
                            "angry",
                        }
                        valence_negative = result.somatic_valence < 0
                        match = expected_negative == valence_negative
                        emotional_metrics.emotion_accuracy.append(match)
                    else:
                        # No somatic marker at all — counts as miss.
                        emotional_metrics.emotion_accuracy.append(False)

                if result.somatic_valence is not None:
                    emotional_metrics.valence_trajectory.append(result.somatic_valence)

            # ---- Recall evaluation ------------------------------------------
            for query, expected_fact in scenario.recall_queries:
                recalled = await condition.recall(query, limit=10)
                recalled_contents = [m.content.lower() for m in recalled]

                # Hit: does any recalled memory contain the expected fact?
                expected_lower = expected_fact.lower()
                hit = any(expected_lower in content for content in recalled_contents)
                recall_metrics.hit_at_k.append(hit)

                # Precision: of the returned memories, how many are relevant
                # to the expected fact?  We use substring matching as proxy.
                if recalled_contents:
                    relevant_count = sum(1 for c in recalled_contents if expected_lower in c)
                    recall_metrics.precision_scores.append(relevant_count / len(recalled_contents))
                else:
                    recall_metrics.precision_scores.append(0.0)

                # Recall: of the planted facts in this scenario, how many were
                # retrieved by this single query?  (1.0 if hit, 0.0 if not.)
                recall_metrics.recall_scores.append(1.0 if hit else 0.0)

        # ---- Finalize state snapshot ----------------------------------------
        state = await condition.get_state()

        # Update skill metrics from final state if available.
        if "skills" in state:
            skill_metrics.skills_discovered = max(
                skill_metrics.skills_discovered, state.get("skills", 0)
            )

        # Personality drift: if the condition tracks OCEAN over time we could
        # compare start vs end.  For now record zero drift (personality is
        # fixed in the current protocol — drift measures future evolution).
        for trait in (
            "openness",
            "conscientiousness",
            "extraversion",
            "agreeableness",
            "neuroticism",
        ):
            personality_metrics.trait_drift[trait] = [0.0]

        return AgentRunMetrics(
            agent_id=agent_profile.agent_id,
            condition=condition_type.value,
            use_case=use_case.value,
            recall=recall_metrics,
            emotional=emotional_metrics,
            personality=personality_metrics,
            efficiency=efficiency_metrics,
            bond=bond_metrics,
            skills=skill_metrics,
        )


# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------


@dataclass
class _RunSpec:
    """Lightweight struct describing one experiment run."""

    agent: AgentProfile
    user: UserProfile
    condition_type: MemoryCondition
    use_case: UseCase
