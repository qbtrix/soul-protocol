# optimize/runner.py — The eval-improve-eval optimization loop.
# Created: 2026-04-29 (#142) — Implements optimize() + OptimizeRunner.
#   Each iteration:
#     1. eval (run_eval_against_soul) — record baseline score
#     2. proposer.propose(...) — get a ranked list of knob changes
#     3. for each proposal in order:
#          snapshot original; apply candidate; re-eval
#          if score improved: keep, append OptimizeStep, break to next iter
#          else: revert, log a "rejected" OptimizeStep
#     4. iteration is "stuck" when no proposal stuck — continue or stop
#     5. stop conditions: target_score reached OR iterations exhausted
#
# Safety rails:
#   - apply=False (default): every change applied during the run is
#     reverted at the end so the soul is byte-identical to its starting
#     state. No trust chain entries written for kept changes.
#   - apply=True: kept changes stay, and one ``soul.optimize.applied``
#     trust-chain entry is appended per kept change with payload
#     {knob_name, before, after, score_delta}. If a change is reverted,
#     no chain entry is written.
#
# The score read from the eval result is the average of per-case scores.
# Skipped cases (e.g. judge cases without an engine) don't contribute —
# they neither raise nor lower the score.

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from soul_protocol.eval.runner import run_eval_against_soul
from soul_protocol.eval.schema import load_eval_spec

from .knobs import Knob, default_knobs
from .proposer import Proposer
from .types import KnobProposal, OptimizeResult, OptimizeStep

if TYPE_CHECKING:
    from soul_protocol.eval.runner import EvalResult
    from soul_protocol.eval.schema import EvalSpec
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine
    from soul_protocol.runtime.soul import Soul

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Score helper
# ---------------------------------------------------------------------------


def score_of(eval_result: EvalResult) -> float:
    """Mean per-case score, ignoring skipped cases.

    A run with zero non-skipped cases scores 0.0 (the same value the eval
    runner uses when seed application fails). The runner treats this as
    "no signal" — improvements off zero are still credited, but the
    convergence test still has to pass.
    """
    if eval_result.error:
        return 0.0
    contributing = [c for c in eval_result.cases if not c.skipped]
    if not contributing:
        return 0.0
    return sum(c.score for c in contributing) / len(contributing)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class OptimizeRunner:
    """Stateful wrapper around the optimize loop with knob registration.

    Intended for callers that want to add custom knobs before kicking
    off the run (the function-level :func:`optimize` is a thin wrapper).
    Construction takes the eval spec + soul; :meth:`register_knob`
    appends extra knobs; :meth:`run` executes the loop.
    """

    def __init__(
        self,
        soul: Soul,
        eval_spec: EvalSpec,
        *,
        knobs: list[Knob] | None = None,
        engine: CognitiveEngine | None = None,
        proposer: Proposer | None = None,
    ) -> None:
        self.soul = soul
        self.eval_spec = eval_spec
        self.engine = engine
        self.knobs: list[Knob] = list(knobs) if knobs is not None else default_knobs(engine=engine)
        self.proposer: Proposer = proposer or Proposer()

    def register_knob(self, knob: Knob) -> None:
        """Append a custom knob to the runner's pool.

        Knobs registered here are eligible for proposal alongside the
        defaults. The proposer ranks built-ins ahead of custom knobs in
        heuristic mode so custom knobs only fire when none of the defaults
        moved the score.
        """
        self.knobs.append(knob)

    async def run(
        self,
        *,
        iterations: int = 10,
        target_score: float = 1.0,
        apply: bool = False,
    ) -> OptimizeResult:
        return await _optimize_inner(
            soul=self.soul,
            eval_spec=self.eval_spec,
            knobs=self.knobs,
            engine=self.engine,
            proposer=self.proposer,
            iterations=iterations,
            target_score=target_score,
            apply=apply,
        )


# ---------------------------------------------------------------------------
# Functional entry point
# ---------------------------------------------------------------------------


async def optimize(
    soul: Soul,
    eval_spec_path: str | Path | EvalSpec,
    *,
    iterations: int = 10,
    target_score: float = 1.0,
    knobs: list[Knob] | None = None,
    engine: CognitiveEngine | None = None,
    proposer: Proposer | None = None,
    apply: bool = False,
) -> OptimizeResult:
    """Run the eval-improve-eval loop against ``soul``.

    Args:
        soul: The soul to tune. Modified in place when ``apply=True``;
            restored to its starting state when ``apply=False``.
        eval_spec_path: Path to a YAML eval spec, or a pre-parsed
            :class:`EvalSpec` instance. The spec's ``seed`` block is
            ignored — the live soul is the seed (matches the
            ``run_eval_against_soul`` semantics).
        iterations: Maximum loop iterations. Default 10.
        target_score: Stop early when the eval score reaches this
            threshold. Default 1.0 (i.e. only stop early on perfect
            score).
        knobs: Custom knob list. Defaults to :func:`default_knobs`.
        engine: Optional :class:`CognitiveEngine` powering judge cases
            and the LLM-assisted proposer. When ``None`` the heuristic
            proposer fires and judge cases skip cleanly.
        proposer: Custom proposer; defaults to a stock :class:`Proposer`.
        apply: When ``False`` (default), every applied change is reverted
            at the end and no trust chain entries are written. When
            ``True``, kept changes stay and per-kept-change
            ``soul.optimize.applied`` chain entries are appended.

    Returns:
        :class:`OptimizeResult` with baseline / final scores, per-step
        record, knobs touched, and convergence iteration.
    """
    if isinstance(eval_spec_path, str | Path):
        spec = load_eval_spec(eval_spec_path)
    else:
        spec = eval_spec_path
    knob_list: list[Knob] = list(knobs) if knobs is not None else default_knobs(engine=engine)
    return await _optimize_inner(
        soul=soul,
        eval_spec=spec,
        knobs=knob_list,
        engine=engine,
        proposer=proposer or Proposer(),
        iterations=iterations,
        target_score=target_score,
        apply=apply,
    )


# ---------------------------------------------------------------------------
# Internal driver
# ---------------------------------------------------------------------------


async def _optimize_inner(
    *,
    soul: Soul,
    eval_spec: EvalSpec,
    knobs: list[Knob],
    engine: CognitiveEngine | None,
    proposer: Proposer,
    iterations: int,
    target_score: float,
    apply: bool,
) -> OptimizeResult:
    started = time.monotonic()
    knob_by_name: dict[str, Knob] = {k.name: k for k in knobs}
    # Snapshot original values for every knob; the apply=False path uses
    # this to fully restore the soul at end-of-run.
    originals: dict[str, object] = {}
    for k in knobs:
        try:
            originals[k.name] = await k.current_value(soul)
        except Exception:  # pragma: no cover — defensive
            logger.warning("knob.current_value failed for %s during snapshot", k.name)

    # Baseline eval
    baseline_eval = await run_eval_against_soul(eval_spec, soul, engine=engine)
    baseline_score = score_of(baseline_eval)
    current_score = baseline_score

    result = OptimizeResult(
        spec_name=eval_spec.name,
        baseline_score=round(baseline_score, 4),
        final_score=round(baseline_score, 4),
        target_score=target_score,
        iterations_run=0,
        applied=apply,
    )
    knobs_touched: set[str] = set()
    convergence_iter: int | None = None

    if baseline_score >= target_score:
        result.iterations_run = 0
        result.duration_ms = int((time.monotonic() - started) * 1000)
        result.knobs_touched = sorted(knobs_touched)
        return result

    for it in range(1, iterations + 1):
        result.iterations_run = it
        latest_eval = baseline_eval if it == 1 else None
        if latest_eval is None:
            latest_eval = await run_eval_against_soul(eval_spec, soul, engine=engine)
            current_score = score_of(latest_eval)
        proposals: list[KnobProposal] = await proposer.propose(
            soul, latest_eval, knobs, engine=engine
        )
        if not proposals:
            logger.info("optimize: iteration %d produced no proposals; stopping", it)
            break

        kept_in_iter = False
        for prop in proposals:
            knob = knob_by_name.get(prop.knob_name)
            if knob is None:
                logger.warning("optimize: proposer returned unknown knob %s", prop.knob_name)
                continue
            try:
                before = await knob.current_value(soul)
            except Exception:  # pragma: no cover — defensive
                continue
            try:
                await knob.apply(soul, prop.candidate)
            except Exception as e:
                logger.warning(
                    "optimize: apply failed for %s candidate=%r: %s",
                    knob.name,
                    prop.candidate,
                    e,
                )
                continue
            try:
                trial_eval = await run_eval_against_soul(eval_spec, soul, engine=engine)
            except Exception as e:
                logger.warning("optimize: trial eval raised: %s", e)
                await knob.revert(soul, before)
                continue
            trial_score = score_of(trial_eval)
            improved = trial_score > current_score
            step = OptimizeStep(
                iteration=it,
                knob_name=knob.name,
                before=_normalize_for_json(before),
                after=_normalize_for_json(prop.candidate),
                score_before=round(current_score, 4),
                score_after=round(trial_score, 4),
                kept=improved,
                reason=prop.reason,
            )
            result.steps.append(step)
            if improved:
                logger.info(
                    "optimize: iter=%d kept knob=%s before=%r after=%r score %.3f -> %.3f",
                    it,
                    knob.name,
                    before,
                    prop.candidate,
                    current_score,
                    trial_score,
                )
                kept_delta = step.delta
                current_score = trial_score
                knobs_touched.add(knob.name)
                kept_in_iter = True
                if apply:
                    _safe_chain_append(
                        soul,
                        knob_name=knob.name,
                        before=_normalize_for_json(before),
                        after=_normalize_for_json(prop.candidate),
                        score_delta=round(kept_delta, 4),
                    )
                # Move on to the next outer iteration — proposer will
                # see the updated state and propose again.
                break
            else:
                logger.info(
                    "optimize: iter=%d reverted knob=%s candidate=%r score %.3f -> %.3f",
                    it,
                    knob.name,
                    prop.candidate,
                    current_score,
                    trial_score,
                )
                await knob.revert(soul, before)

        if current_score >= target_score:
            convergence_iter = it
            break

        if not kept_in_iter:
            # No proposal moved the score this iteration. The next loop
            # would just re-propose the same set, so break early.
            logger.info("optimize: stuck at score %.3f after iter %d", current_score, it)
            break

    # If apply=False, restore every knob to its starting value.
    if not apply:
        for name, original in originals.items():
            knob = knob_by_name.get(name)
            if knob is None:  # pragma: no cover — defensive
                continue
            try:
                await knob.revert(soul, original)
            except Exception as e:
                logger.warning("optimize: revert failed for %s during dry-run cleanup: %s", name, e)

    result.final_score = round(current_score, 4)
    result.knobs_touched = sorted(knobs_touched)
    result.convergence_iteration = convergence_iter
    result.duration_ms = int((time.monotonic() - started) * 1000)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_for_json(value: object) -> object:
    """Coerce knob values into JSON-friendly primitives.

    Tuples become lists; everything else passes through. Pydantic copes
    with the rest because :class:`OptimizeStep` allows arbitrary types.
    """
    if isinstance(value, tuple):
        return list(value)
    return value


def _safe_chain_append(
    soul: Soul,
    *,
    knob_name: str,
    before: object,
    after: object,
    score_delta: float,
) -> None:
    """Append a ``soul.optimize.applied`` trust chain entry.

    Mirrors the existing ``_safe_append_chain`` callsites in Soul: the
    write is best-effort; failures (no signing key, verification-only
    mode) are swallowed by the underlying helper. The ``apply=True`` path
    calls this once per kept change; the ``apply=False`` path never calls
    it.
    """
    payload = {
        "knob_name": knob_name,
        "before": before,
        "after": after,
        "score_delta": float(score_delta),
    }
    summary = f"{knob_name}: {before!r} -> {after!r} (Δ={score_delta:+.3f})"
    try:
        soul._safe_append_chain("soul.optimize.applied", payload, summary=summary)
    except Exception as e:  # pragma: no cover — defensive
        logger.warning("optimize: chain append raised: %s", e)


__all__ = ["OptimizeRunner", "optimize", "score_of"]
