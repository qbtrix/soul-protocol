# decisions.py — Decision trace payload types and helpers for the Org Journal.
# Created: feat/decision-traces — Workstream D of the Org Architecture RFC (PR #164).
#
# Every agent proposal a human edits or rejects becomes a structured, auditable
# pair of events in the journal:
#   - ``agent.proposed``   : the agent's proposed action with a structured payload.
#   - ``human.corrected``  : the human's disposition (accepted / edited / rejected /
#                            deferred) linked back via ``causation_id``.
#   - ``decision.graduated``: a pattern of recurring corrections promoted from
#                            episodic to semantic memory (promotion logic ships
#                            in a later slice; this module only carries the
#                            payload type and a candidate-surfacing helper).
#
# The Paw OS gaps analysis names "Decisions" as one of the four compounding
# data types that differentiate it from generic stack-of-record systems. This
# module is the spec side of that story. The pocketpaw-side emit points
# (tool-call preview, draft-approval UI hooks, etc.) land in a follow-up PR in
# that repo.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .journal import Actor, EventEntry


# ----- Payload models ------------------------------------------------------


class AgentProposal(BaseModel):
    """Payload for an ``agent.proposed`` :class:`EventEntry`.

    An agent's proposed action awaiting human review, edit, or acceptance.
    The proposal is structured (not just a blob) so that the matching
    ``human.corrected`` event can be aligned field-for-field when a reviewer
    edits the output. See :func:`build_proposal_event`.

    Fields:
        proposal_kind: One of ``"tool_call"``, ``"message_draft"``,
            ``"decision"``, or ``"custom:<namespace>"`` for domain extensions.
            Free-form string — the catalog is a convention, not an enum.
        summary: One to three sentences that a human can skim in a queue.
        proposal: The structured proposal payload — tool arguments, draft
            body, decision options, etc. Shape is kind-dependent.
        confidence: The agent's self-reported confidence in the proposal,
            in ``[0.0, 1.0]``. ``None`` when the agent does not emit one.
        alternatives: Alternative proposals the agent considered but did
            not surface as the primary. Useful when the human prefers an
            already-explored option.
        context_refs: Prior ``EventEntry`` ids the agent consulted when
            drafting the proposal (retrievals, prior proposals, prior
            corrections). Grounds the proposal in the journal.
    """

    proposal_kind: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    proposal: dict
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    alternatives: list[dict] = Field(default_factory=list)
    context_refs: list[UUID] = Field(default_factory=list)


Disposition = Literal["accepted", "edited", "rejected", "deferred"]


class HumanCorrection(BaseModel):
    """Payload for a ``human.corrected`` :class:`EventEntry`.

    A human's edit, rejection, acceptance, or deferral of an agent
    proposal. The matching event's ``causation_id`` must point to the
    ``agent.proposed`` event this correction responds to — that link is
    what makes the proposal/correction pair queryable and graduatable.

    Fields:
        disposition: ``"accepted"``, ``"edited"``, ``"rejected"``, or
            ``"deferred"``. Enforced as a Literal — unknown values raise.
        corrected_value: The final value when edited or accepted; ``None``
            when rejected or deferred. Shape mirrors ``AgentProposal.proposal``.
        correction_reason: Optional free-text reason the reviewer provided.
        structured_reason_tags: Machine-readable tags, e.g.
            ``["tone_too_formal", "wrong_recipient", "missed_context"]``.
            Powers :func:`cluster_correction_patterns` — pick a small
            stable tag vocabulary per pocket.
        edit_distance: Optional similarity score in ``[0.0, 1.0]`` between
            the proposal and the corrected value. ``None`` when not scored.
    """

    disposition: Disposition
    corrected_value: dict | None = None
    correction_reason: str | None = None
    structured_reason_tags: list[str] = Field(default_factory=list)
    edit_distance: float | None = Field(default=None, ge=0.0, le=1.0)


class DecisionGraduation(BaseModel):
    """Payload for a ``decision.graduated`` :class:`EventEntry`.

    A pattern of recurring corrections has been promoted from episodic to
    semantic (or core) memory. Once graduated, the agent should load the
    pattern as standing guidance — so the same correction does not have to
    be made again.

    Fields:
        pattern_summary: Human-readable summary of the learned pattern
            (e.g. "Use first names, not titles, for internal replies").
        supporting_correction_ids: Ids of ``human.corrected`` events that
            this pattern is drawn from. Provides auditability — a reviewer
            can inspect the raw corrections behind any graduated rule.
        graduated_to_tier: ``"semantic"`` for general-purpose facts,
            ``"core"`` for load-on-startup identity-grade guidance.
        confidence: Confidence in the pattern, in ``[0.0, 1.0]``.
        applies_to: Scope / context where the pattern applies, e.g.
            ``{"channel": "email", "recipients": "internal"}``. Opaque
            to the spec; consumer subsystems interpret the shape.
    """

    pattern_summary: str = Field(min_length=1)
    supporting_correction_ids: list[UUID] = Field(min_length=1)
    graduated_to_tier: Literal["semantic", "core"]
    confidence: float = Field(ge=0.0, le=1.0)
    applies_to: dict = Field(default_factory=dict)


# ----- Builder helpers -----------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def build_proposal_event(
    *,
    actor: Actor,
    scope: list[str],
    correlation_id: UUID,
    proposal: AgentProposal,
    ts: datetime | None = None,
    event_id: UUID | None = None,
) -> EventEntry:
    """Build an ``agent.proposed`` :class:`EventEntry` from a proposal.

    The payload is wrapped via ``AgentProposal.model_dump(mode="json")`` so
    nested UUIDs serialize cleanly through the journal's JSON transport.
    """
    return EventEntry(
        id=event_id or uuid4(),
        ts=ts or _now_utc(),
        actor=actor,
        action="agent.proposed",
        scope=scope,
        correlation_id=correlation_id,
        causation_id=None,
        payload=proposal.model_dump(mode="json"),
    )


def build_correction_event(
    *,
    actor: Actor,
    scope: list[str],
    correlation_id: UUID,
    causation_id: UUID,
    correction: HumanCorrection,
    ts: datetime | None = None,
    event_id: UUID | None = None,
) -> EventEntry:
    """Build a ``human.corrected`` :class:`EventEntry` linked to a proposal.

    ``causation_id`` is required and must point to the ``agent.proposed``
    event this correction responds to.
    """
    return EventEntry(
        id=event_id or uuid4(),
        ts=ts or _now_utc(),
        actor=actor,
        action="human.corrected",
        scope=scope,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=correction.model_dump(mode="json"),
    )


# ----- Journal queries -----------------------------------------------------


def find_corrections_for(journal, proposal_id: UUID) -> list[EventEntry]:
    """Return every ``human.corrected`` event whose ``causation_id`` is
    ``proposal_id``.

    A proposal may have more than one correction in practice (e.g. a
    deferral followed by an eventual accept), so this returns a list. The
    backend query filters by action; we filter by ``causation_id`` here
    because not every backend indexes it as a first-class column.
    """
    # Pull a generous window — callers with very busy journals should
    # query the backend directly with a narrower scope / since filter.
    candidates = journal.query(action="human.corrected", limit=10_000)
    return [e for e in candidates if e.causation_id == proposal_id]


def trace_decision_chain(journal, correlation_id: UUID) -> list[EventEntry]:
    """Return the ordered proposal/correction events for a given
    ``correlation_id``.

    Events are ordered by ``ts`` — the journal engine enforces monotonic
    timestamps, so this is stable across replays. Non-decision events on
    the same correlation_id are filtered out.
    """
    events = journal.query(correlation_id=correlation_id, limit=10_000)
    decision_actions = {"agent.proposed", "human.corrected", "decision.graduated"}
    chain = [e for e in events if e.action in decision_actions]
    chain.sort(key=lambda e: e.ts)
    return chain


# ----- Pattern detection (graduation seed) ---------------------------------


def cluster_correction_patterns(
    journal,
    *,
    since: datetime | None = None,
    min_occurrences: int = 3,
) -> list[dict]:
    """Surface candidate graduation patterns by tag co-occurrence.

    Scans ``human.corrected`` events, groups by the sorted tuple of
    ``structured_reason_tags``, and returns clusters that meet the
    ``min_occurrences`` threshold. This is the *candidate-surfacing* step
    only — the actual promotion to semantic/core memory ships in a later
    slice. Keep the heuristic simple; richer clustering (embedding-based,
    tag-hierarchy-aware) is a deliberate future enhancement.

    Return shape:
        ``[{"tags": [...], "count": N,
           "example_correction_ids": [UUID, ...],
           "recent_ts": datetime}, ...]``
    """
    events = journal.query(action="human.corrected", since=since, limit=10_000)

    buckets: dict[tuple[str, ...], list[EventEntry]] = {}
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        tags = payload.get("structured_reason_tags") or []
        if not tags:
            continue
        key = tuple(sorted(tags))
        buckets.setdefault(key, []).append(event)

    clusters: list[dict] = []
    for key, bucket in buckets.items():
        if len(bucket) < min_occurrences:
            continue
        bucket_sorted = sorted(bucket, key=lambda e: e.ts)
        clusters.append(
            {
                "tags": list(key),
                "count": len(bucket),
                "example_correction_ids": [e.id for e in bucket_sorted[-5:]],
                "recent_ts": bucket_sorted[-1].ts,
            }
        )
    clusters.sort(key=lambda c: (-c["count"], c["recent_ts"]))
    return clusters


__all__ = [
    "AgentProposal",
    "HumanCorrection",
    "DecisionGraduation",
    "Disposition",
    "build_proposal_event",
    "build_correction_event",
    "find_corrections_for",
    "trace_decision_chain",
    "cluster_correction_patterns",
]
