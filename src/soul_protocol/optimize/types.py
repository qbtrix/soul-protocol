# optimize/types.py — Pydantic models for the soul-optimize loop.
# Created: 2026-04-29 (#142) — KnobProposal carries (knob_name, candidate
#   value, reason, optional predicted score delta) from the Proposer.
#   OptimizeStep records one iteration of the eval-improve-eval loop:
#   which knob was changed, before/after values, scores around the change,
#   and whether the change was kept. OptimizeResult aggregates the steps
#   plus the baseline / final scores, total iterations, and convergence
#   point. Mirrors the eval module's result-shape pattern (EvalResult /
#   CaseResult) for consistency in CLI/MCP serialization.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnobProposal(BaseModel):
    """A single proposed knob change ranked for trial.

    The :class:`Proposer` returns a list of these in priority order. The
    runner walks the list and trials each in turn, keeping the first one
    that improves the eval score. ``predicted_delta`` is informational
    only — the runner trusts the measured score, not the prediction.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    knob_name: str
    candidate: Any
    reason: str = ""
    predicted_delta: float | None = None


class OptimizeStep(BaseModel):
    """One iteration of the optimize loop, recorded for the audit trail.

    Captures a single proposal-application-evaluation cycle. ``kept``
    distinguishes a change that improved the score from one that was
    reverted. ``iteration`` counts from 1; the first iteration that
    actually moves the score is the convergence iteration.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    iteration: int = Field(ge=1)
    knob_name: str
    before: Any
    after: Any
    score_before: float
    score_after: float
    kept: bool
    reason: str = ""

    @property
    def delta(self) -> float:
        """Measured score change for this step (after - before)."""
        return self.score_after - self.score_before


class OptimizeResult(BaseModel):
    """Top-level result of an :func:`optimize` run.

    ``steps`` is the per-iteration record; the convergence iteration is
    the index of the last kept improvement. ``stuck_iterations`` counts
    iterations where no proposal was kept — useful for spotting evals
    where the available knobs cannot move the score further.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    spec_name: str
    baseline_score: float
    final_score: float
    target_score: float
    iterations_run: int = Field(ge=0)
    convergence_iteration: int | None = None
    applied: bool = False
    steps: list[OptimizeStep] = Field(default_factory=list)
    knobs_touched: list[str] = Field(default_factory=list)
    duration_ms: int = 0

    @property
    def improved(self) -> bool:
        """True when the final eval score is strictly higher than baseline."""
        return self.final_score > self.baseline_score

    @property
    def converged(self) -> bool:
        """True when the run hit the target score before exhausting iterations."""
        return self.final_score >= self.target_score

    @property
    def kept_steps(self) -> list[OptimizeStep]:
        """Subset of ``steps`` where the proposal was kept."""
        return [s for s in self.steps if s.kept]

    @property
    def stuck_iterations(self) -> int:
        """Number of iterations where no proposal improved the score.

        Counted as iterations where every proposal was reverted. When this
        is high relative to ``iterations_run``, the available knobs cannot
        push the score further on the current eval.
        """
        # Group steps by iteration; an iteration is "stuck" when no step
        # in the group is kept.
        per_iter: dict[int, list[OptimizeStep]] = {}
        for s in self.steps:
            per_iter.setdefault(s.iteration, []).append(s)
        return sum(1 for steps in per_iter.values() if not any(s.kept for s in steps))
