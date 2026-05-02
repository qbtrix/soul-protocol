# test_knobs.py — Tests for soul_protocol.optimize.knobs (#142).
# Created: 2026-04-29 — Covers each built-in knob: current_value/apply/revert
#   round-trip, candidates() shape and clamping, and the LLM-driven
#   PersonaTextKnob.async_candidates path. Uses an in-memory FakeEngine so the
#   suite stays offline.

from __future__ import annotations

import pytest

from soul_protocol.optimize.knobs import (
    BondThresholdKnob,
    OceanTraitKnob,
    PersonaTextKnob,
    SignificanceThresholdKnob,
    default_knobs,
)
from soul_protocol.runtime.soul import Soul


class FakeEngine:
    """Deterministic engine stand-in for persona LLM tests."""

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies) or [""]
        self._idx = 0
        self.calls: list[str] = []

    async def think(self, prompt: str) -> str:
        self.calls.append(prompt)
        out = self._replies[self._idx % len(self._replies)]
        self._idx += 1
        return out


# ---------------------------------------------------------------------------
# OceanTraitKnob
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ocean_knob_round_trip() -> None:
    soul = await Soul.birth("Tester", ocean={"openness": 0.5})
    knob = OceanTraitKnob("openness")
    assert knob.name == "ocean.openness"
    original = await knob.current_value(soul)
    assert original == pytest.approx(0.5)
    await knob.apply(soul, 0.8)
    assert soul._dna.personality.openness == pytest.approx(0.8)
    await knob.revert(soul, original)
    assert soul._dna.personality.openness == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_ocean_knob_candidates_clamped_at_bounds() -> None:
    # candidates() doesn't read soul state — exercise the pure logic path.
    knob = OceanTraitKnob("openness")
    cand = knob.candidates(0.95)
    # All candidates must stay in [0, 1]; +0.1 -> 1.0, +0.2 -> 1.0 dedup,
    # -0.1 -> 0.85, -0.2 -> 0.75.
    assert all(0.0 <= v <= 1.0 for v in cand)
    assert 0.85 in cand
    assert 0.75 in cand
    # Above-bounds clamp produces 1.0 once (deduped from +0.1 / +0.2)
    assert cand.count(1.0) <= 1


@pytest.mark.asyncio
async def test_ocean_knob_candidates_excludes_current() -> None:
    knob = OceanTraitKnob("agreeableness")
    cand = knob.candidates(0.5)
    assert 0.5 not in cand


def test_ocean_knob_rejects_unknown_trait() -> None:
    with pytest.raises(ValueError):
        OceanTraitKnob("not_a_trait")


# ---------------------------------------------------------------------------
# PersonaTextKnob
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persona_knob_round_trip() -> None:
    soul = await Soul.birth("Aurora")
    soul._memory.set_core(persona="Aurora is a curious researcher.", human="")
    knob = PersonaTextKnob()
    original = await knob.current_value(soul)
    assert "curious researcher" in original
    await knob.apply(soul, "Aurora is a meticulous archivist.")
    assert "meticulous archivist" in soul.get_core_memory().persona
    await knob.revert(soul, original)
    assert soul.get_core_memory().persona == original


@pytest.mark.asyncio
async def test_persona_knob_heuristic_returns_empty_without_engine() -> None:
    soul = await Soul.birth("Aurora")
    soul._memory.set_core(persona="Aurora is a curious researcher.", human="")
    knob = PersonaTextKnob()
    # No engine, no override -> empty heuristic candidates.
    assert knob.candidates(await knob.current_value(soul)) == []


@pytest.mark.asyncio
async def test_persona_knob_async_candidates_uses_engine() -> None:
    soul = await Soul.birth("Aurora")
    soul._memory.set_core(persona="Aurora is curious.", human="")
    engine = FakeEngine("Aurora is a thoughtful explorer who looks for novel angles.")
    knob = PersonaTextKnob(engine=engine)
    knob.set_failing_cases(["judge_creative_framing scored 0.30"])
    candidates = await knob.async_candidates(await knob.current_value(soul))
    assert len(candidates) == 1
    assert "thoughtful explorer" in candidates[0]
    # The prompt should mention the failing case so the LLM can ground its
    # suggestion.
    assert any("judge_creative_framing" in c for c in engine.calls)


@pytest.mark.asyncio
async def test_persona_knob_async_candidates_strips_quotes_and_dedup() -> None:
    soul = await Soul.birth("Aurora")
    soul._memory.set_core(persona="Aurora is curious.", human="")
    engine = FakeEngine('"Aurora is curious."')
    knob = PersonaTextKnob(engine=engine)
    # Engine returns the same persona quoted — the knob should strip the
    # quotes and detect the no-op, returning [].
    out = await knob.async_candidates(await knob.current_value(soul))
    assert out == []


@pytest.mark.asyncio
async def test_persona_knob_override_path() -> None:
    soul = await Soul.birth("Aurora")
    soul._memory.set_core(persona="A.", human="")
    knob = PersonaTextKnob(candidates_override=["B.", "C."])
    cand = knob.candidates("A.")
    assert cand == ["B.", "C."]


# ---------------------------------------------------------------------------
# SignificanceThresholdKnob
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_significance_knob_round_trip() -> None:
    soul = await Soul.birth("Tester")
    soul._memory.settings.importance_threshold = 5
    soul._memory.settings.skip_deep_processing_on_low_significance = True
    knob = SignificanceThresholdKnob()
    original = await knob.current_value(soul)
    assert original == (5, True)
    await knob.apply(soul, (3, False))
    assert soul._memory.settings.importance_threshold == 3
    assert soul._memory.settings.skip_deep_processing_on_low_significance is False
    await knob.revert(soul, original)
    assert soul._memory.settings.importance_threshold == 5
    assert soul._memory.settings.skip_deep_processing_on_low_significance is True


@pytest.mark.asyncio
async def test_significance_knob_candidates_walk_threshold_then_flip() -> None:
    knob = SignificanceThresholdKnob()
    cand = knob.candidates((5, True))
    # First two: ±step on threshold with bool unchanged.
    assert cand[0] == (6, True) or cand[0] == (4, True)
    # Last: bool flipped, threshold unchanged.
    assert (5, False) in cand


@pytest.mark.asyncio
async def test_significance_knob_threshold_clamped() -> None:
    soul = await Soul.birth("Tester")
    soul._memory.settings.importance_threshold = 1
    knob = SignificanceThresholdKnob()
    await knob.apply(soul, (0, True))
    # Lo bound is 1 — apply should clamp.
    assert soul._memory.settings.importance_threshold == 1


# ---------------------------------------------------------------------------
# BondThresholdKnob
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bond_threshold_knob_round_trip() -> None:
    soul = await Soul.birth("Tester")
    soul.bond._default.bond_strength = 50.0
    knob = BondThresholdKnob()
    original = await knob.current_value(soul)
    assert original == pytest.approx(50.0)
    await knob.apply(soul, 70.0)
    assert soul.bond.bond_strength == pytest.approx(70.0)
    await knob.revert(soul, original)
    assert soul.bond.bond_strength == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_bond_threshold_knob_clamps_to_bounds() -> None:
    soul = await Soul.birth("Tester")
    soul.bond._default.bond_strength = 95.0
    knob = BondThresholdKnob()
    cand = knob.candidates(95.0)
    assert all(0.0 <= v <= 100.0 for v in cand)
    # Up-step from 95 lands at 100 (capped); down-step lands at 90 / 85.
    assert 90.0 in cand
    assert 85.0 in cand


@pytest.mark.asyncio
async def test_bond_threshold_apply_does_not_write_chain() -> None:
    """Direct mutation must bypass the bond on_change callback so probe
    cycles never pollute the trust chain."""
    soul = await Soul.birth("Tester")
    chain_len_before = len(soul.trust_chain.entries)
    knob = BondThresholdKnob()
    await knob.apply(soul, 80.0)
    chain_len_after = len(soul.trust_chain.entries)
    assert chain_len_after == chain_len_before, "bond knob apply should not append a chain entry"


# ---------------------------------------------------------------------------
# default_knobs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_knobs_includes_all_builtins() -> None:
    knobs = default_knobs()
    names = {k.name for k in knobs}
    assert "ocean.openness" in names
    assert "ocean.conscientiousness" in names
    assert "ocean.extraversion" in names
    assert "ocean.agreeableness" in names
    assert "ocean.neuroticism" in names
    assert "core.persona" in names
    assert "memory.significance" in names
    assert "bond.default_strength" in names
