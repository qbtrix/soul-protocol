# test_trust_chain_hooks.py — Trust-chain integration for soul optimize (#142).
# Created: 2026-04-29 — Verifies that apply=True writes one
#   ``soul.optimize.applied`` chain entry per kept change, and apply=False
#   writes none. Catches the silent-pollution failure mode where probe
#   attempts that get reverted leak entries into the audit log.

from __future__ import annotations

from typing import Any

import pytest

from soul_protocol.eval.schema import (
    CaseInputs,
    EvalCase,
    EvalSpec,
    KeywordScoring,
)
from soul_protocol.optimize.proposer import Proposer
from soul_protocol.optimize.runner import OptimizeRunner
from soul_protocol.optimize.types import KnobProposal
from soul_protocol.runtime.soul import Soul


class StaticProposer(Proposer):
    def __init__(self, proposals: list[KnobProposal]) -> None:
        super().__init__()
        self._proposals = proposals
        self._call_count = 0

    async def propose(self, soul, eval_result, knobs, engine=None):
        # Return proposals only on first call so we don't loop forever.
        self._call_count += 1
        if self._call_count == 1:
            return list(self._proposals)
        return []


class RenameKnob:
    """Mutates Soul.identity.name; passes a keyword eval when applied."""

    name = "soul.name"

    async def current_value(self, s: Soul) -> str:
        return s.identity.name

    async def apply(self, s: Soul, value: Any) -> None:
        s._identity.name = str(value)

    async def revert(self, s: Soul, original: Any) -> None:
        await self.apply(s, original)

    def candidates(self, current: Any) -> list[str]:
        return ["Improved"]


def _spec_for_keyword(keyword: str) -> EvalSpec:
    return EvalSpec(
        name="t",
        cases=[
            EvalCase(
                name="kw",
                inputs=CaseInputs(message="hi"),
                scoring=KeywordScoring(expected=[keyword], mode="any"),
            )
        ],
    )


def _optimize_chain_entries(soul: Soul):
    return [e for e in soul.trust_chain.entries if e.action == "soul.optimize.applied"]


# ---------------------------------------------------------------------------
# apply=False writes no chain entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_writes_no_chain_entries() -> None:
    soul = await Soul.birth("Original")
    spec = _spec_for_keyword("Improved")
    knob = RenameKnob()
    proposer = StaticProposer([KnobProposal(knob_name="soul.name", candidate="Improved")])
    runner = OptimizeRunner(soul, spec, knobs=[knob], proposer=proposer)
    chain_before = len(soul.trust_chain.entries)
    result = await runner.run(iterations=1, target_score=1.0, apply=False)
    chain_after = len(soul.trust_chain.entries)
    # The knob did move the score, so we expect a kept step in-flight.
    assert any(s.kept for s in result.steps)
    # But on a dry-run, no chain entry should land — and the soul state is
    # restored at the end.
    assert _optimize_chain_entries(soul) == []
    assert chain_after == chain_before


# ---------------------------------------------------------------------------
# apply=True writes one entry per kept change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_writes_one_chain_entry_per_kept_change() -> None:
    soul = await Soul.birth("Original")
    spec = _spec_for_keyword("Improved")
    knob = RenameKnob()
    proposer = StaticProposer([KnobProposal(knob_name="soul.name", candidate="Improved")])
    runner = OptimizeRunner(soul, spec, knobs=[knob], proposer=proposer)
    result = await runner.run(iterations=1, target_score=1.0, apply=True)
    kept = [s for s in result.steps if s.kept]
    entries = _optimize_chain_entries(soul)
    assert len(entries) == len(kept) == 1
    # The chain entry payload-summary should mention the knob name.
    assert "soul.name" in (entries[0].summary or "")
    # The soul state stays mutated when apply=True.
    assert soul.identity.name == "Improved"


# ---------------------------------------------------------------------------
# Reverted proposals never write entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reverted_change_does_not_write_chain_entry() -> None:
    soul = await Soul.birth("Tester")
    # An eval that's already passing → any proposed change can't strictly
    # improve, so it must be reverted.
    spec = EvalSpec(
        name="t",
        cases=[
            EvalCase(
                name="trivial",
                inputs=CaseInputs(message="hi"),
                scoring=KeywordScoring(expected=["fallback"], mode="any"),
            )
        ],
    )
    proposer = StaticProposer([KnobProposal(knob_name="soul.name", candidate="Mutated")])
    runner = OptimizeRunner(soul, spec, knobs=[RenameKnob()], proposer=proposer)
    chain_before = len(soul.trust_chain.entries)
    await runner.run(iterations=1, target_score=2.0, apply=True)  # impossible target
    chain_after = len(soul.trust_chain.entries)
    # Nothing kept → no soul.optimize.applied entries written, even with apply=True.
    assert _optimize_chain_entries(soul) == []
    assert chain_after == chain_before
    assert soul.identity.name == "Tester"


# ---------------------------------------------------------------------------
# Multiple iterations → multiple kept entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_kept_iterations_each_write_one_entry() -> None:
    """Two distinct knobs produced in sequence → two kept changes → two
    chain entries."""

    # Each knob mutates Soul.identity.name to append a tag. The fallback
    # response surfaces ``soul.name`` so both kept changes end up in the
    # output and both keyword cases pass after the second iteration.

    class FirstKnob:
        name = "first"

        async def current_value(self, s: Soul) -> str:
            return s.identity.name

        async def apply(self, s: Soul, value: Any) -> None:
            s._identity.name = str(value)

        async def revert(self, s: Soul, original: Any) -> None:
            await self.apply(s, original)

        def candidates(self, current: Any) -> list[str]:
            return ["Original Step1"]

    class SecondKnob:
        name = "second"

        async def current_value(self, s: Soul) -> str:
            return s.identity.name

        async def apply(self, s: Soul, value: Any) -> None:
            s._identity.name = str(value)

        async def revert(self, s: Soul, original: Any) -> None:
            await self.apply(s, original)

        def candidates(self, current: Any) -> list[str]:
            return [f"{current} Step2"]

    soul = await Soul.birth("Original", archetype="Original")
    spec = EvalSpec(
        name="t",
        cases=[
            # First case wants "Step1" present (first knob), second case wants
            # "Step2" present (second knob).
            EvalCase(
                name="first_kw",
                inputs=CaseInputs(message="hi"),
                scoring=KeywordScoring(expected=["Step1"], mode="any"),
            ),
            EvalCase(
                name="second_kw",
                inputs=CaseInputs(message="hi"),
                scoring=KeywordScoring(expected=["Step2"], mode="any"),
            ),
        ],
    )

    class RoundProposer(Proposer):
        def __init__(self) -> None:
            super().__init__()
            self._calls = 0

        async def propose(self, soul, eval_result, knobs, engine=None):
            self._calls += 1
            if self._calls == 1:
                return [KnobProposal(knob_name="first", candidate="Original Step1")]
            if self._calls == 2:
                # Bind candidate from the soul's CURRENT name so we
                # accumulate "Original Step1 Step2".
                return [
                    KnobProposal(
                        knob_name="second",
                        candidate=f"{soul.identity.name} Step2",
                    )
                ]
            return []

    runner = OptimizeRunner(
        soul,
        spec,
        knobs=[FirstKnob(), SecondKnob()],
        proposer=RoundProposer(),
    )
    result = await runner.run(iterations=3, target_score=1.0, apply=True)
    kept = [s for s in result.steps if s.kept]
    entries = _optimize_chain_entries(soul)
    assert len(entries) == len(kept) == 2
