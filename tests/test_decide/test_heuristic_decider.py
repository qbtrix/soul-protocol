# test_decide/test_heuristic_decider.py — Parity tests for HeuristicDecider.
# Created: feat/soul-instinct — HeuristicDecider must return exactly what the
#   underlying rule functions return (attention, sentiment, contradiction, dedup),
#   so wrapping them behind the Decider protocol changes no behaviour.

from __future__ import annotations

import pytest

from soul_protocol.runtime.decide import (
    ContradictionRequest,
    Decider,
    DecisionKind,
    DedupRequest,
    HeuristicDecider,
    SentimentRequest,
    SignificanceRequest,
)
from soul_protocol.runtime.memory.attention import (
    compute_significance,
    is_significant,
    overall_significance,
)
from soul_protocol.runtime.memory.contradiction import ContradictionDetector
from soul_protocol.runtime.memory.dedup import reconcile_fact
from soul_protocol.runtime.memory.search import tokenize
from soul_protocol.runtime.memory.sentiment import detect_sentiment
from soul_protocol.runtime.types import Interaction, MemoryEntry, MemoryType


def _memory(content: str, mem_id: str) -> MemoryEntry:
    return MemoryEntry(id=mem_id, type=MemoryType.SEMANTIC, content=content)


def test_satisfies_decider_protocol():
    assert isinstance(HeuristicDecider(), Decider)


@pytest.mark.parametrize("kind", list(DecisionKind))
def test_supports_every_kind(kind):
    assert HeuristicDecider().supports(kind)


@pytest.mark.parametrize(
    ("user_input", "agent_output"),
    [
        ("hi", "hello!"),
        ("I just got promoted to senior engineer at Stripe!", "Congratulations!"),
        ("My dog Bruno turned 5 today", "Happy birthday Bruno!"),
    ],
)
async def test_significance_matches_attention_rules(user_input, agent_output):
    interaction = Interaction(user_input=user_input, agent_output=agent_output)
    values = ["curiosity", "kindness"]
    recent = ["User talked about the weather"]

    decision = await HeuristicDecider().decide(
        SignificanceRequest(interaction=interaction, core_values=values, recent_contents=recent)
    )

    expected = compute_significance(interaction, values, recent)
    tokens = len(tokenize(f"{user_input} {agent_output}"))
    assert decision.kind == DecisionKind.SIGNIFICANCE
    assert decision.value.score == expected
    assert decision.value.overall == overall_significance(expected, token_count=tokens)
    assert decision.value.significant == is_significant(expected, token_count=tokens)
    assert decision.confidence is None
    assert decision.source == "heuristic"


async def test_significance_threshold_is_configurable():
    request = SignificanceRequest(
        interaction=Interaction(user_input="I just got promoted at Stripe!", agent_output="Wow!")
    )
    always = await HeuristicDecider(significance_threshold=0.0).decide(request)
    never = await HeuristicDecider(significance_threshold=1.01).decide(request)
    assert always.value.significant is True
    assert never.value.significant is False


@pytest.mark.parametrize("text", ["I GOT PROMOTED!!!", "I'm so sad today", "ok", ""])
async def test_sentiment_matches_word_list_rules(text):
    decision = await HeuristicDecider().decide(SentimentRequest(text=text))
    assert decision.kind == DecisionKind.SENTIMENT
    assert decision.value == detect_sentiment(text)
    assert decision.confidence is None


async def test_contradiction_matches_detector():
    old = _memory("User likes Python programming", "old1")
    unrelated = _memory("User has a cat", "old2")
    new = "User dislikes Python programming"

    decision = await HeuristicDecider().decide(
        ContradictionRequest(new_content=new, existing=[old, unrelated])
    )

    expected = await ContradictionDetector().detect_heuristic(new, [old, unrelated])
    assert decision.kind == DecisionKind.CONTRADICTION
    assert [f.old_memory_id for f in decision.value.findings] == [r.old_memory_id for r in expected]
    assert [f.confidence for f in decision.value.findings] == [r.confidence for r in expected]
    assert decision.value.findings[0].old_memory_id == "old1"


async def test_no_contradiction_returns_empty_findings():
    decision = await HeuristicDecider().decide(
        ContradictionRequest(new_content="anything new", existing=[])
    )
    assert decision.value.findings == []


@pytest.mark.parametrize(
    ("new_fact", "existing", "expected_action"),
    [
        ("User knows Python", [], "CREATE"),
        (
            "User likes working with Python",
            [_memory("User likes working with Python", "f1")],
            "SKIP",
        ),
        ("User has a cat named Milo", [_memory("User works at Stripe", "f1")], "CREATE"),
    ],
)
async def test_dedup_matches_reconcile_fact(new_fact, existing, expected_action):
    decision = await HeuristicDecider().decide(
        DedupRequest(new_fact=new_fact, existing_facts=existing)
    )
    action, target = reconcile_fact(new_fact, existing)
    assert decision.kind == DecisionKind.DEDUP
    assert decision.value.action == action == expected_action
    assert decision.value.target_id == target
