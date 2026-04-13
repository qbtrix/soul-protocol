# test_spec/test_decisions.py — Tests for the decision-trace spec.
# Created: feat/decision-traces — Workstream D of Org Architecture RFC (PR #164).
# Covers: JSON round-trips, disposition Literal enforcement, builder helpers
# emit the right actions + payload shapes, find_corrections_for filters on
# causation_id (not correlation_id), trace_decision_chain returns ordered
# pairs, cluster_correction_patterns respects min_occurrences, optional
# edit_distance is allowed to be None, empty context_refs is allowed.

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from soul_protocol.engine.journal import Journal, open_journal
from soul_protocol.spec import (
    ACTION_NAMESPACES,
    Actor,
    AgentProposal,
    DecisionGraduation,
    HumanCorrection,
    build_correction_event,
    build_proposal_event,
    cluster_correction_patterns,
    find_corrections_for,
    trace_decision_chain,
)


# ---------- fixtures -------------------------------------------------------


@pytest.fixture
def journal(tmp_path: Path) -> Journal:
    j = open_journal(tmp_path / "journal.db")
    yield j
    j.close()


@pytest.fixture
def reviewer() -> Actor:
    return Actor(kind="user", id="user:alice", scope_context=["org:sales"])


@pytest.fixture
def drafter() -> Actor:
    return Actor(kind="agent", id="did:soul:sales-lead", scope_context=["org:sales"])


# ---------- payload round-trips -------------------------------------------


def test_agent_proposal_round_trips_json():
    proposal = AgentProposal(
        proposal_kind="message_draft",
        summary="Draft reply to Acme's pricing question.",
        proposal={"to": "buyer@acme.com", "body": "Thanks for reaching out..."},
        confidence=0.72,
        alternatives=[{"body": "Shorter variant."}],
        context_refs=[uuid4(), uuid4()],
    )
    restored = AgentProposal.model_validate_json(proposal.model_dump_json())
    assert restored == proposal


def test_agent_proposal_allows_empty_context_refs_and_no_confidence():
    proposal = AgentProposal(
        proposal_kind="tool_call",
        summary="Call the pricing tool.",
        proposal={"name": "get_price", "args": {"sku": "X-1"}},
    )
    assert proposal.context_refs == []
    assert proposal.alternatives == []
    assert proposal.confidence is None


def test_agent_proposal_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        AgentProposal(
            proposal_kind="decision",
            summary="Pick a plan.",
            proposal={},
            confidence=1.5,
        )


def test_human_correction_round_trips_json():
    correction = HumanCorrection(
        disposition="edited",
        corrected_value={"body": "Thanks — here's pricing."},
        correction_reason="too formal",
        structured_reason_tags=["tone_too_formal", "wrong_length"],
        edit_distance=0.34,
    )
    restored = HumanCorrection.model_validate_json(correction.model_dump_json())
    assert restored == correction


def test_human_correction_edit_distance_is_optional():
    correction = HumanCorrection(
        disposition="accepted",
        corrected_value={"body": "ok"},
        structured_reason_tags=[],
    )
    assert correction.edit_distance is None


def test_human_correction_rejects_unknown_disposition():
    with pytest.raises(ValidationError):
        HumanCorrection(disposition="mangled")  # type: ignore[arg-type]


def test_human_correction_rejected_allows_null_corrected_value():
    correction = HumanCorrection(
        disposition="rejected",
        corrected_value=None,
        correction_reason="off-brand",
        structured_reason_tags=["off_brand"],
    )
    restored = HumanCorrection.model_validate_json(correction.model_dump_json())
    assert restored.corrected_value is None


def test_decision_graduation_round_trips_json():
    grad = DecisionGraduation(
        pattern_summary="Use first names, not titles, for internal replies.",
        supporting_correction_ids=[uuid4(), uuid4(), uuid4()],
        graduated_to_tier="semantic",
        confidence=0.88,
        applies_to={"channel": "email", "recipients": "internal"},
    )
    restored = DecisionGraduation.model_validate_json(grad.model_dump_json())
    assert restored == grad


def test_decision_graduation_requires_supporting_ids():
    with pytest.raises(ValidationError):
        DecisionGraduation(
            pattern_summary="x",
            supporting_correction_ids=[],
            graduated_to_tier="semantic",
            confidence=0.9,
        )


# ---------- builders -------------------------------------------------------


def test_namespaces_include_decision_actions():
    assert "agent.proposed" in ACTION_NAMESPACES
    assert "human.corrected" in ACTION_NAMESPACES
    assert "decision.graduated" in ACTION_NAMESPACES


def test_build_proposal_event_shape(drafter: Actor):
    correlation_id = uuid4()
    proposal = AgentProposal(
        proposal_kind="message_draft",
        summary="Draft reply.",
        proposal={"body": "Hi."},
        confidence=0.5,
    )
    event = build_proposal_event(
        actor=drafter,
        scope=["org:sales:pocket:acme"],
        correlation_id=correlation_id,
        proposal=proposal,
    )
    assert event.action == "agent.proposed"
    assert event.correlation_id == correlation_id
    assert event.causation_id is None
    assert isinstance(event.payload, dict)
    assert event.payload["summary"] == "Draft reply."
    assert event.ts.tzinfo is not None


def test_build_correction_event_shape(reviewer: Actor):
    proposal_id = uuid4()
    correlation_id = uuid4()
    correction = HumanCorrection(
        disposition="edited",
        corrected_value={"body": "Hi Alice."},
        structured_reason_tags=["tone_too_formal"],
    )
    event = build_correction_event(
        actor=reviewer,
        scope=["org:sales:pocket:acme"],
        correlation_id=correlation_id,
        causation_id=proposal_id,
        correction=correction,
    )
    assert event.action == "human.corrected"
    assert event.causation_id == proposal_id
    assert event.correlation_id == correlation_id
    assert isinstance(event.payload, dict)
    assert event.payload["disposition"] == "edited"


# ---------- journal queries -----------------------------------------------


def _seed_proposal_and_correction(
    journal: Journal,
    *,
    drafter: Actor,
    reviewer: Actor,
    tags: list[str] | None = None,
    correlation_id=None,
    proposal_ts: datetime | None = None,
    correction_ts: datetime | None = None,
):
    correlation_id = correlation_id or uuid4()
    proposal = AgentProposal(
        proposal_kind="message_draft",
        summary="s",
        proposal={"body": "draft"},
    )
    p_event = build_proposal_event(
        actor=drafter,
        scope=["org:sales"],
        correlation_id=correlation_id,
        proposal=proposal,
        ts=proposal_ts,
    )
    journal.append(p_event)
    correction = HumanCorrection(
        disposition="edited",
        corrected_value={"body": "edited"},
        structured_reason_tags=tags or [],
    )
    c_event = build_correction_event(
        actor=reviewer,
        scope=["org:sales"],
        correlation_id=correlation_id,
        causation_id=p_event.id,
        correction=correction,
        ts=correction_ts,
    )
    journal.append(c_event)
    return p_event, c_event


def test_find_corrections_for_matches_only_causation_id(
    journal: Journal, drafter: Actor, reviewer: Actor
):
    p1, c1 = _seed_proposal_and_correction(journal, drafter=drafter, reviewer=reviewer)
    p2, c2 = _seed_proposal_and_correction(journal, drafter=drafter, reviewer=reviewer)

    hits_for_p1 = find_corrections_for(journal, p1.id)
    assert [e.id for e in hits_for_p1] == [c1.id]

    hits_for_p2 = find_corrections_for(journal, p2.id)
    assert [e.id for e in hits_for_p2] == [c2.id]


def test_find_corrections_for_ignores_same_correlation_id(
    journal: Journal, drafter: Actor, reviewer: Actor
):
    # Two proposals share one correlation_id (same session) — their
    # corrections must not cross-pollinate.
    correlation_id = uuid4()
    base = datetime.now(UTC)
    p1, c1 = _seed_proposal_and_correction(
        journal,
        drafter=drafter,
        reviewer=reviewer,
        correlation_id=correlation_id,
        proposal_ts=base,
        correction_ts=base + timedelta(seconds=1),
    )
    p2, c2 = _seed_proposal_and_correction(
        journal,
        drafter=drafter,
        reviewer=reviewer,
        correlation_id=correlation_id,
        proposal_ts=base + timedelta(seconds=2),
        correction_ts=base + timedelta(seconds=3),
    )

    hits = find_corrections_for(journal, p1.id)
    assert {e.id for e in hits} == {c1.id}
    assert c2.id not in {e.id for e in hits}


def test_trace_decision_chain_orders_by_timestamp(
    journal: Journal, drafter: Actor, reviewer: Actor
):
    correlation_id = uuid4()
    base = datetime.now(UTC)
    p1, c1 = _seed_proposal_and_correction(
        journal,
        drafter=drafter,
        reviewer=reviewer,
        correlation_id=correlation_id,
        proposal_ts=base,
        correction_ts=base + timedelta(seconds=1),
    )
    p2, c2 = _seed_proposal_and_correction(
        journal,
        drafter=drafter,
        reviewer=reviewer,
        correlation_id=correlation_id,
        proposal_ts=base + timedelta(seconds=2),
        correction_ts=base + timedelta(seconds=3),
    )

    chain = trace_decision_chain(journal, correlation_id)
    assert [e.id for e in chain] == [p1.id, c1.id, p2.id, c2.id]


def test_trace_decision_chain_filters_non_decision_events(
    journal: Journal, drafter: Actor, reviewer: Actor
):
    from soul_protocol.spec.journal import EventEntry

    correlation_id = uuid4()
    base = datetime.now(UTC)
    # Append a non-decision event on the same correlation_id in the middle
    # of the decision chain — trace_decision_chain should filter it out.
    p1_proposal = AgentProposal(
        proposal_kind="message_draft", summary="s", proposal={"body": "draft"}
    )
    p1 = build_proposal_event(
        actor=drafter,
        scope=["org:sales"],
        correlation_id=correlation_id,
        proposal=p1_proposal,
        ts=base,
    )
    journal.append(p1)
    journal.append(
        EventEntry(
            id=uuid4(),
            ts=base + timedelta(seconds=1),
            actor=drafter,
            action="retrieval.query",
            scope=["org:sales"],
            correlation_id=correlation_id,
            payload={"q": "..."},
        )
    )
    c1 = build_correction_event(
        actor=reviewer,
        scope=["org:sales"],
        correlation_id=correlation_id,
        causation_id=p1.id,
        correction=HumanCorrection(
            disposition="edited",
            corrected_value={"body": "edited"},
            structured_reason_tags=[],
        ),
        ts=base + timedelta(seconds=2),
    )
    journal.append(c1)

    chain = trace_decision_chain(journal, correlation_id)
    actions = [e.action for e in chain]
    assert actions == ["agent.proposed", "human.corrected"]


# ---------- pattern clustering --------------------------------------------


def test_cluster_correction_patterns_meets_threshold(
    journal: Journal, drafter: Actor, reviewer: Actor
):
    # Seed 3 corrections with the same tag combo, 1 with a different combo.
    for _ in range(3):
        _seed_proposal_and_correction(
            journal,
            drafter=drafter,
            reviewer=reviewer,
            tags=["tone_too_formal", "wrong_length"],
        )
    _seed_proposal_and_correction(
        journal,
        drafter=drafter,
        reviewer=reviewer,
        tags=["off_brand"],
    )

    clusters = cluster_correction_patterns(journal, min_occurrences=3)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert sorted(cluster["tags"]) == ["tone_too_formal", "wrong_length"]
    assert cluster["count"] == 3
    assert len(cluster["example_correction_ids"]) == 3
    assert cluster["recent_ts"].tzinfo is not None


def test_cluster_correction_patterns_skips_untagged(
    journal: Journal, drafter: Actor, reviewer: Actor
):
    # 5 untagged corrections — should not produce a cluster keyed on ().
    for _ in range(5):
        _seed_proposal_and_correction(journal, drafter=drafter, reviewer=reviewer, tags=[])
    clusters = cluster_correction_patterns(journal, min_occurrences=3)
    assert clusters == []


def test_cluster_correction_patterns_respects_since(
    journal: Journal, drafter: Actor, reviewer: Actor
):
    old_base = datetime.now(UTC) - timedelta(days=30)
    # Old corrections: will be filtered out by since=.
    for i in range(3):
        _seed_proposal_and_correction(
            journal,
            drafter=drafter,
            reviewer=reviewer,
            tags=["stale_tag"],
            proposal_ts=old_base + timedelta(seconds=2 * i),
            correction_ts=old_base + timedelta(seconds=2 * i + 1),
        )
    # Recent corrections: should count.
    for _ in range(3):
        _seed_proposal_and_correction(
            journal,
            drafter=drafter,
            reviewer=reviewer,
            tags=["fresh_tag"],
        )

    clusters = cluster_correction_patterns(
        journal,
        since=datetime.now(UTC) - timedelta(days=1),
        min_occurrences=3,
    )
    assert len(clusters) == 1
    assert clusters[0]["tags"] == ["fresh_tag"]
