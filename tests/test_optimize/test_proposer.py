# test_proposer.py — Tests for soul_protocol.optimize.proposer (#142).
# Created: 2026-04-29 — Heuristic ranking, LLM parsing, fallback on engine
#   error, persona-knob plumbing.

from __future__ import annotations

import json

import pytest

from soul_protocol.eval.runner import CaseResult, EvalResult
from soul_protocol.optimize.knobs import (
    BondThresholdKnob,
    OceanTraitKnob,
    PersonaTextKnob,
    SignificanceThresholdKnob,
)
from soul_protocol.optimize.proposer import Proposer
from soul_protocol.runtime.soul import Soul


class FakeEngine:
    def __init__(self, *replies: str, raise_on: int | None = None) -> None:
        self._replies = list(replies) or [""]
        self._idx = 0
        self._raise_on = raise_on
        self.calls: list[str] = []

    async def think(self, prompt: str) -> str:
        if self._raise_on is not None and self._idx == self._raise_on:
            self._idx += 1
            raise RuntimeError("boom")
        self.calls.append(prompt)
        out = self._replies[self._idx % len(self._replies)]
        self._idx += 1
        return out


def _failing_eval() -> EvalResult:
    return EvalResult(
        spec_name="t",
        cases=[
            CaseResult(
                name="creative_response",
                passed=False,
                score=0.2,
                output="boring response",
                details={"missing": ["novel"]},
            ),
            CaseResult(
                name="recall_diversity",
                passed=False,
                score=0.4,
                output="only one memory surfaced",
                details={"reasoning": "did not return multiple matches"},
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Heuristic path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heuristic_proposer_orders_ocean_first() -> None:
    soul = await Soul.birth("Tester", ocean={"openness": 0.5})
    soul._memory.set_core(persona="P", human="")
    knobs = [
        BondThresholdKnob(),
        OceanTraitKnob("openness"),
        SignificanceThresholdKnob(),
    ]
    proposer = Proposer()
    proposals = await proposer.propose(soul, _failing_eval(), knobs, engine=None)
    # OCEAN should come before significance / bond.
    assert proposals[0].knob_name.startswith("ocean.")
    names_in_order = [p.knob_name for p in proposals]
    ocean_idx = names_in_order.index("ocean.openness")
    sig_idx = names_in_order.index("memory.significance")
    bond_idx = names_in_order.index("bond.default_strength")
    assert ocean_idx < sig_idx < bond_idx


@pytest.mark.asyncio
async def test_heuristic_proposer_skips_persona_without_engine() -> None:
    soul = await Soul.birth("Tester")
    soul._memory.set_core(persona="P", human="")
    knobs = [
        OceanTraitKnob("openness"),
        PersonaTextKnob(),  # no engine → no candidates
    ]
    proposer = Proposer()
    proposals = await proposer.propose(soul, _failing_eval(), knobs, engine=None)
    names = [p.knob_name for p in proposals]
    assert "core.persona" not in names
    assert "ocean.openness" in names


@pytest.mark.asyncio
async def test_heuristic_proposer_emits_first_candidate_per_knob() -> None:
    soul = await Soul.birth("Tester", ocean={"openness": 0.5})
    knob = OceanTraitKnob("openness")
    expected_first = knob.candidates(0.5)[0]
    proposer = Proposer()
    proposals = await proposer.propose(soul, _failing_eval(), [knob], engine=None)
    assert proposals[0].candidate == expected_first


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_proposer_parses_ranked_response() -> None:
    soul = await Soul.birth("Tester", ocean={"openness": 0.5})
    soul._memory.set_core(persona="P", human="")
    knobs = [
        OceanTraitKnob("openness"),
        BondThresholdKnob(),
        SignificanceThresholdKnob(),
    ]
    reply = json.dumps(
        {
            "proposals": [
                {"knob": "bond.default_strength", "reason": "raise visibility"},
                {"knob": "ocean.openness", "reason": "encourage novelty"},
            ]
        }
    )
    engine = FakeEngine(reply)
    proposer = Proposer()
    proposals = await proposer.propose(soul, _failing_eval(), knobs, engine=engine)
    # LLM proposals come first (in the LLM's ranking order), then the
    # heuristic-explored candidates fill in below for fallback. We verify
    # the LLM ordering is the prefix of the result.
    names_prefix = [p.knob_name for p in proposals[:2]]
    assert names_prefix == [
        "bond.default_strength",
        "ocean.openness",
    ]
    assert "raise visibility" in proposals[0].reason


@pytest.mark.asyncio
async def test_llm_proposer_falls_back_on_unparseable_response() -> None:
    soul = await Soul.birth("Tester", ocean={"openness": 0.5})
    knobs = [OceanTraitKnob("openness")]
    engine = FakeEngine("not json at all")
    proposer = Proposer()
    proposals = await proposer.propose(soul, _failing_eval(), knobs, engine=engine)
    # Falls back to heuristic — still produces an OCEAN proposal.
    assert proposals
    assert proposals[0].knob_name == "ocean.openness"


@pytest.mark.asyncio
async def test_llm_proposer_falls_back_on_engine_error() -> None:
    soul = await Soul.birth("Tester", ocean={"openness": 0.5})
    knobs = [OceanTraitKnob("openness")]
    # raise on first call → proposer falls back to heuristic.
    engine = FakeEngine("ignored", raise_on=0)
    proposer = Proposer()
    proposals = await proposer.propose(soul, _failing_eval(), knobs, engine=engine)
    assert proposals
    assert proposals[0].knob_name == "ocean.openness"


@pytest.mark.asyncio
async def test_llm_proposer_drops_unknown_knob_names() -> None:
    soul = await Soul.birth("Tester", ocean={"openness": 0.5})
    knobs = [OceanTraitKnob("openness")]
    reply = json.dumps(
        {
            "proposals": [
                {"knob": "bond.default_strength", "reason": "doesn't exist here"},
                {"knob": "ocean.openness", "reason": "valid"},
            ]
        }
    )
    engine = FakeEngine(reply)
    proposer = Proposer()
    proposals = await proposer.propose(soul, _failing_eval(), knobs, engine=engine)
    # The LLM-named "bond.default_strength" knob isn't registered → dropped.
    # The valid LLM proposal is at index 0; heuristic exploration fills the
    # remaining ranks with other ocean.openness candidates.
    assert proposals[0].knob_name == "ocean.openness"
    # No bond.default_strength proposal because the knob isn't registered.
    assert all(p.knob_name != "bond.default_strength" for p in proposals)


@pytest.mark.asyncio
async def test_llm_proposer_handles_persona_knob_async_candidates() -> None:
    soul = await Soul.birth("Tester")
    soul._memory.set_core(persona="P.", human="")
    persona_knob = PersonaTextKnob(engine=None)  # engine wired by proposer
    knobs = [persona_knob]
    proposal_reply = json.dumps(
        {"proposals": [{"knob": "core.persona", "reason": "tighten persona"}]}
    )
    persona_reply = "Aurora is a meticulous researcher with a creative streak."
    engine = FakeEngine(proposal_reply, persona_reply)
    proposer = Proposer()
    proposals = await proposer.propose(soul, _failing_eval(), knobs, engine=engine)
    assert len(proposals) == 1
    assert proposals[0].knob_name == "core.persona"
    assert proposals[0].candidate == persona_reply


@pytest.mark.asyncio
async def test_llm_proposer_failing_cases_passed_to_persona_knob() -> None:
    """The proposer wires failing-case strings into the persona knob so its
    own LLM prompt can ground on real failures."""
    soul = await Soul.birth("Tester")
    soul._memory.set_core(persona="P.", human="")
    persona_knob = PersonaTextKnob(engine=None)
    proposer = Proposer()
    await proposer.propose(soul, _failing_eval(), [persona_knob], engine=None)
    # No engine → heuristic skips persona, but failing cases were still set.
    assert persona_knob._failing_cases  # populated
    assert any("creative_response" in c for c in persona_knob._failing_cases)
