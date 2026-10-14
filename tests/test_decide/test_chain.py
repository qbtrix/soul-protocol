# test_decide/test_chain.py — Tests for DeciderChain confidence-gated fallback.
# Created: feat/soul-instinct — Covers: confident answers accepted, unsure /
#   abstaining / crashing / unsupported deciders skipped, ordering, the heuristic
#   fallback, custom fallbacks, typed helpers, and request validation.

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from soul_protocol.runtime.decide import (
    ContradictionFinding,
    ContradictionVerdict,
    Decider,
    DeciderChain,
    Decision,
    DecisionKind,
    DecisionRequest,
    HeuristicDecider,
)
from soul_protocol.runtime.types import Interaction, MemoryEntry, MemoryType


class FakeDecider:
    """Answers contradiction requests with a fixed verdict and confidence."""

    def __init__(
        self,
        name: str = "fake",
        *,
        confidence: float | None = 0.95,
        flag_id: str | None = "old1",
        kinds: tuple[DecisionKind, ...] = (DecisionKind.CONTRADICTION,),
        abstain: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.confidence = confidence
        self.flag_id = flag_id
        self.kinds = kinds
        self.abstain = abstain
        self.error = error
        self.calls = 0

    def supports(self, kind: DecisionKind) -> bool:
        return kind in self.kinds

    async def decide(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.abstain:
            return None
        findings = (
            [ContradictionFinding(old_memory_id=self.flag_id, confidence=self.confidence or 0.0)]
            if self.flag_id
            else []
        )
        return Decision(
            kind=DecisionKind.CONTRADICTION,
            value=ContradictionVerdict(findings=findings),
            confidence=self.confidence,
            source=self.name,
        )


@pytest.fixture
def memories() -> list[MemoryEntry]:
    return [MemoryEntry(id="old1", type=MemoryType.SEMANTIC, content="User loves steak")]


def test_chain_and_fake_satisfy_protocol():
    assert isinstance(DeciderChain(), Decider)
    assert isinstance(FakeDecider(), Decider)


async def test_confident_decider_is_used(memories):
    fake = FakeDecider(confidence=0.95)
    decision = await DeciderChain([fake]).contradictions("User is vegetarian now", memories)
    assert fake.calls == 1
    assert decision.source == "fake"
    assert decision.value.findings[0].old_memory_id == "old1"


async def test_unsure_decider_falls_back_to_heuristic(memories):
    fake = FakeDecider(confidence=0.3)
    decision = await DeciderChain([fake]).contradictions("User is vegetarian now", memories)
    assert fake.calls == 1
    assert decision.source == "heuristic"


async def test_threshold_is_inclusive(memories):
    fake = FakeDecider(confidence=0.7)
    chain = DeciderChain([fake], min_confidence=0.7)
    decision = await chain.contradictions("User is vegetarian now", memories)
    assert decision.source == "fake"


async def test_none_confidence_is_not_trusted_from_non_fallback(memories):
    fake = FakeDecider(confidence=None)
    decision = await DeciderChain([fake]).contradictions("User is vegetarian now", memories)
    assert decision.source == "heuristic"


async def test_crashing_decider_falls_back(memories, caplog):
    fake = FakeDecider(error=ConnectionError("decision API is down"))
    decision = await DeciderChain([fake]).contradictions("User is vegetarian now", memories)
    assert decision.source == "heuristic"
    assert "failed" in caplog.text


async def test_abstaining_decider_is_skipped(memories):
    fake = FakeDecider(abstain=True)
    decision = await DeciderChain([fake]).contradictions("User is vegetarian now", memories)
    assert fake.calls == 1
    assert decision.source == "heuristic"


async def test_unsupported_kind_is_not_asked():
    fake = FakeDecider(kinds=(DecisionKind.CONTRADICTION,))
    decision = await DeciderChain([fake]).sentiment("I GOT PROMOTED!!!")
    assert fake.calls == 0
    assert decision.source == "heuristic"
    assert decision.kind == DecisionKind.SENTIMENT


async def test_first_confident_decider_wins(memories):
    unsure = FakeDecider("unsure", confidence=0.2)
    sure = FakeDecider("sure", confidence=0.9)
    never = FakeDecider("never", confidence=0.99)
    decision = await DeciderChain([unsure, sure, never]).contradictions("x", memories)
    assert decision.source == "sure"
    assert (unsure.calls, sure.calls, never.calls) == (1, 1, 0)


async def test_confident_no_contradiction_is_respected(memories):
    """A confident 'no findings' answer is accepted, not overridden by rules."""
    fake = FakeDecider(confidence=0.95, flag_id=None)
    decision = await DeciderChain([fake]).contradictions(
        "User dislikes steak",  # heuristic negation rules would flag this
        memories,
    )
    assert decision.source == "fake"
    assert decision.value.findings == []


async def test_empty_chain_behaves_like_heuristic(memories):
    interaction = Interaction(user_input="My dog Bruno turned 5 today", agent_output="Yay!")
    chain = DeciderChain()
    heuristic = HeuristicDecider()

    got = await chain.significance(interaction, ["kindness"], ["weather chat"])
    want = await heuristic.decide(
        TypeAdapter(DecisionRequest).validate_python(
            {
                "kind": "significance",
                "interaction": interaction,
                "core_values": ["kindness"],
                "recent_contents": ["weather chat"],
            }
        )
    )
    assert got == want

    dedup = await chain.dedup("User loves steak", memories)
    assert dedup.value.action == "SKIP"
    assert dedup.value.target_id == "old1"


async def test_custom_fallback_is_used(memories):
    fallback = FakeDecider("custom-fallback", confidence=None)
    decision = await DeciderChain(fallback=fallback).contradictions("x", memories)
    assert decision.source == "custom-fallback"


async def test_abstaining_fallback_raises(memories):
    with pytest.raises(RuntimeError, match="abstained"):
        await DeciderChain(fallback=FakeDecider(abstain=True)).contradictions("x", memories)


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_min_confidence_is_validated(bad):
    with pytest.raises(ValueError):
        DeciderChain(min_confidence=bad)


def test_request_union_discriminates_on_kind():
    adapter = TypeAdapter(DecisionRequest)
    request = adapter.validate_python({"kind": "sentiment", "text": "hello"})
    assert request.kind == DecisionKind.SENTIMENT
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "telepathy", "text": "hello"})


def test_decision_confidence_is_bounded():
    with pytest.raises(ValidationError):
        Decision(
            kind=DecisionKind.CONTRADICTION,
            value=ContradictionVerdict(),
            confidence=1.5,
            source="x",
        )
