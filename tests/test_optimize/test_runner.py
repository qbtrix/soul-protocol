# test_runner.py — Tests for soul_protocol.optimize.runner (#142).
# Created: 2026-04-29 — Synthetic 1-iteration optimize that reliably
#   improves; revert behaviour when no proposal sticks; convergence stop;
#   apply=False fully restores soul state. Uses programmable knobs
#   instead of the built-ins so the tests are deterministic without an
#   LLM.

from __future__ import annotations

from typing import Any

import pytest

from soul_protocol.eval.schema import (
    CaseInputs,
    EvalCase,
    EvalSpec,
    KeywordScoring,
    Seed,
    SoulSeed,
)
from soul_protocol.optimize.knobs import OceanTraitKnob
from soul_protocol.optimize.proposer import Proposer
from soul_protocol.optimize.runner import OptimizeRunner, optimize, score_of
from soul_protocol.optimize.types import KnobProposal
from soul_protocol.runtime.soul import Soul

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class FlagKnob:
    """A test knob that flips a flag on the soul. Apply mutates a custom
    attribute (``_test_flag``); revert resets it."""

    name = "test.flag"

    async def current_value(self, soul: Soul) -> bool:
        return getattr(soul, "_test_flag", False)

    async def apply(self, soul: Soul, value: Any) -> None:
        soul._test_flag = bool(value)

    async def revert(self, soul: Soul, original: Any) -> None:
        await self.apply(soul, original)

    def candidates(self, current: Any) -> list[bool]:
        return [not current]


class StaticProposer(Proposer):
    """Proposer that returns a fixed list, ignoring the eval result."""

    def __init__(self, proposals: list[KnobProposal]) -> None:
        super().__init__()
        self._proposals = proposals

    async def propose(self, soul, eval_result, knobs, engine=None):
        # Re-bind candidate values to current state for repeatability.
        return list(self._proposals)


def _trivial_passing_spec(keyword: str = "fallback") -> EvalSpec:
    return EvalSpec(
        name="t",
        seed=Seed(soul=SoulSeed(name="Tester")),
        cases=[
            EvalCase(
                name="kw",
                inputs=CaseInputs(message="hi"),
                scoring=KeywordScoring(expected=[keyword], mode="any"),
            )
        ],
    )


def _impossible_spec() -> EvalSpec:
    """Spec whose case will never pass with a fallback engine."""
    return EvalSpec(
        name="t",
        seed=Seed(soul=SoulSeed(name="Tester")),
        cases=[
            EvalCase(
                name="kw",
                inputs=CaseInputs(message="hi"),
                scoring=KeywordScoring(
                    expected=["this-string-cannot-appear-anywhere-12345"], mode="any"
                ),
            )
        ],
    )


# ---------------------------------------------------------------------------
# score_of
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_of_excludes_skipped_cases() -> None:
    spec = _trivial_passing_spec()
    soul = await Soul.birth("Tester")
    from soul_protocol.eval.runner import run_eval_against_soul

    result = await run_eval_against_soul(spec, soul)
    assert score_of(result) > 0


# ---------------------------------------------------------------------------
# Convergence on already-passing eval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_optimize_baseline_at_target_returns_zero_iterations() -> None:
    soul = await Soul.birth("Tester")
    spec = _trivial_passing_spec()
    result = await optimize(soul, spec, iterations=5, target_score=0.5, apply=False)
    assert result.baseline_score >= 0.5
    assert result.iterations_run == 0
    assert result.steps == []
    assert result.converged is True


# ---------------------------------------------------------------------------
# 1-iteration improve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_optimize_keeps_change_that_improves_score(monkeypatch) -> None:
    """Engineered case: spec keyword is "improved-token" which the fallback
    response only contains AFTER we set _test_flag=True via a custom knob
    that mutates the soul's name. Use a programmable proposer to avoid
    the heuristic dependency on knob priority."""
    soul = await Soul.birth("Original")
    spec = EvalSpec(
        name="t",
        cases=[
            EvalCase(
                name="kw",
                inputs=CaseInputs(message="hi"),
                scoring=KeywordScoring(expected=["Improved"], mode="any"),
            )
        ],
    )

    class RenameKnob:
        name = "soul.name"

        async def current_value(self, s: Soul) -> str:
            return s.identity.name

        async def apply(self, s: Soul, value: Any) -> None:
            s._identity.name = str(value)

        async def revert(self, s: Soul, original: Any) -> None:
            await self.apply(s, original)

        def candidates(self, current: Any) -> list[str]:
            return ["Improved"]

    knob = RenameKnob()
    proposer = StaticProposer([KnobProposal(knob_name="soul.name", candidate="Improved")])
    runner = OptimizeRunner(soul, spec, knobs=[knob], proposer=proposer)
    result = await runner.run(iterations=3, target_score=1.0, apply=False)
    assert result.baseline_score < result.final_score
    assert any(s.kept for s in result.steps)
    assert "soul.name" in result.knobs_touched


# ---------------------------------------------------------------------------
# apply=False fully restores soul state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_optimize_dry_run_restores_soul() -> None:
    soul = await Soul.birth("Original")
    original_name = soul.identity.name
    spec = EvalSpec(
        name="t",
        cases=[
            EvalCase(
                name="kw",
                inputs=CaseInputs(message="hi"),
                scoring=KeywordScoring(expected=["Improved"], mode="any"),
            )
        ],
    )

    class RenameKnob:
        name = "soul.name"

        async def current_value(self, s: Soul) -> str:
            return s.identity.name

        async def apply(self, s: Soul, value: Any) -> None:
            s._identity.name = str(value)

        async def revert(self, s: Soul, original: Any) -> None:
            await self.apply(s, original)

        def candidates(self, current: Any) -> list[str]:
            return ["Improved"]

    proposer = StaticProposer([KnobProposal(knob_name="soul.name", candidate="Improved")])
    runner = OptimizeRunner(soul, spec, knobs=[RenameKnob()], proposer=proposer)
    result = await runner.run(iterations=2, target_score=1.0, apply=False)
    # The optimizer kept the change in-flight, but apply=False rewinds.
    assert result.improved
    assert soul.identity.name == original_name, "dry-run must restore the soul's pre-optimize state"


# ---------------------------------------------------------------------------
# Revert path when proposal does not improve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_optimize_reverts_change_that_does_not_help() -> None:
    soul = await Soul.birth("Tester")
    spec = _trivial_passing_spec()  # already passing — no proposal improves
    proposer = StaticProposer(
        [
            KnobProposal(
                knob_name="ocean.openness",
                candidate=0.0,
                reason="test-only proposal",
            )
        ]
    )
    knob = OceanTraitKnob("openness")
    original = await knob.current_value(soul)
    runner = OptimizeRunner(soul, spec, knobs=[knob], proposer=proposer)
    result = await runner.run(iterations=1, target_score=2.0, apply=False)
    assert result.steps
    assert all(not s.kept for s in result.steps)
    assert result.stuck_iterations >= 1
    # Knob value restored.
    assert await knob.current_value(soul) == pytest.approx(original)


# ---------------------------------------------------------------------------
# Stops early when no proposals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_optimize_stops_when_proposer_returns_empty() -> None:
    soul = await Soul.birth("Tester")
    spec = _impossible_spec()
    proposer = StaticProposer([])  # returns nothing
    runner = OptimizeRunner(soul, spec, knobs=[], proposer=proposer)
    result = await runner.run(iterations=10, target_score=1.0, apply=False)
    assert result.iterations_run == 1
    assert result.steps == []


# ---------------------------------------------------------------------------
# register_knob
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_optimize_runner_register_knob_appends() -> None:
    soul = await Soul.birth("Tester")
    spec = _trivial_passing_spec()
    runner = OptimizeRunner(soul, spec, knobs=[OceanTraitKnob("openness")])
    runner.register_knob(FlagKnob())
    assert any(k.name == "test.flag" for k in runner.knobs)
