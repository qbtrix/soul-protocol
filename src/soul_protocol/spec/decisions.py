# decisions.py — Decision trace payload types and helpers for the Org Journal.
# Updated: feat/rfc-09-slice-1-decision-vocabulary — add two new builders for
# the Decision Graph projection vocabulary (RFC 09 Slice 1a):
#   - ``build_policy_event`` for the ``policy.evaluated`` chain-forming event
#     (Instinct gate evaluations) — the LAST one before chain close becomes
#     ``Decision.instinct_policy`` in the projection.
#   - ``build_completion_event`` for the ``decision.completed`` terminal
#     event — the canonical chain closer per RFC 09 with a
#     ``landed`` / ``rejected`` / ``abandoned`` status.
# Also extends ``trace_decision_chain``'s filter to follow
# ``decision.completed`` (kept ``decision.graduated`` in the filter — that
# action is a separate concept, see comment on the filter and on
# ``ACTION_NAMESPACES`` in journal.py).
# Updated: feat/rfc07-decision-outcome-attached — extend the
# ``trace_decision_chain`` decision-action filter to include
# ``decision.outcome_attached`` so post-close outcome mutations
# (introduced by RFC 07) surface in the trace alongside the chain
# proper.
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

from datetime import UTC, datetime
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
    return datetime.now(UTC)


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


CompletionStatus = Literal["landed", "rejected", "abandoned"]
"""Terminal status emitted on a ``decision.completed`` event (RFC 09).

- ``landed``: the chain reached its intended outcome (action taken, decision
  applied, draft sent).
- ``rejected``: the chain closed because a reviewer / policy rejected the
  proposal.
- ``abandoned``: the chain closed without an explicit outcome — timed out,
  superseded, or otherwise dropped.
"""


def build_policy_event(
    *,
    actor: Actor,
    scope: list[str],
    correlation_id: UUID,
    policy_name: str,
    passed: bool,
    causation_id: UUID | None = None,
    reason: str | None = None,
    payload_extras: dict | None = None,
    ts: datetime | None = None,
    event_id: UUID | None = None,
) -> EventEntry:
    """Build a ``policy.evaluated`` :class:`EventEntry` for the Decision
    Graph chain (RFC 09).

    Producer is Instinct's gate evaluator. Each policy run produces one
    event; the LAST ``policy.evaluated`` before chain close becomes the
    projection's ``Decision.instinct_policy`` field.

    ``causation_id`` typically points back at the preceding
    ``agent.proposed`` event the policy was evaluated against; it is
    optional because Instinct can also run pre-proposal sweeps that have
    no upstream cause in the chain.

    ``payload_extras`` is merged on top of the base payload
    (``{policy_name, passed, reason?}``) — use it to carry evaluator
    metadata (rule id, version, evaluator name, latency) without
    growing the public signature.
    """
    payload: dict[str, object] = {"policy_name": policy_name, "passed": passed}
    if reason is not None:
        payload["reason"] = reason
    if payload_extras:
        # Caller extras win — they're the more specific layer. The base
        # keys (``policy_name``, ``passed``, ``reason``) are conventions,
        # not invariants, so an extras dict that overrides them is a
        # legitimate (if unusual) shape.
        payload.update(payload_extras)
    return EventEntry(
        id=event_id or uuid4(),
        ts=ts or _now_utc(),
        actor=actor,
        action="policy.evaluated",
        scope=scope,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


def build_completion_event(
    *,
    actor: Actor,
    scope: list[str],
    correlation_id: UUID,
    causation_id: UUID | None = None,
    status: CompletionStatus = "landed",
    reason: str | None = None,
    payload_extras: dict | None = None,
    ts: datetime | None = None,
    event_id: UUID | None = None,
) -> EventEntry:
    """Build a ``decision.completed`` :class:`EventEntry` — the canonical
    chain terminator per RFC 09.

    Replaces ``decision.graduated`` for Decision Graph chain-close
    purposes. ``decision.graduated`` retains its original meaning
    (pattern promotion into semantic / core memory, see
    :class:`DecisionGraduation`) and is unchanged.

    ``causation_id`` typically points back at the last meaningful event in
    the chain (the accepted ``human.corrected``, the final
    ``policy.evaluated``, etc.) but is optional — abandoned / timed-out
    chains may not have a clear causal predecessor.

    ``status`` defaults to ``"landed"`` (the common happy-path); set to
    ``"rejected"`` or ``"abandoned"`` for negative closures, and populate
    ``reason`` to record why.

    ``payload_extras`` merges on top of ``{status, reason?}`` — use it to
    attach summary metadata (final outcome ref, downstream side-effect
    ids) without growing the public signature.
    """
    payload: dict[str, object] = {"status": status}
    if reason is not None:
        payload["reason"] = reason
    if payload_extras:
        payload.update(payload_extras)
    return EventEntry(
        id=event_id or uuid4(),
        ts=ts or _now_utc(),
        actor=actor,
        action="decision.completed",
        scope=scope,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
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
    decision_actions = {
        "agent.proposed",
        "human.corrected",
        # ``decision.graduated`` keeps its original (pattern-promotion)
        # meaning and stays in the filter so backward-compat chain
        # traces still surface graduation events on the same
        # correlation_id. RFC 09's chain-closing terminal is
        # ``decision.completed`` (below), not this one.
        "decision.graduated",
        # RFC 07: outcome-attachment events update an already-emitted
        # Decision's outcome and belong in the chain so traces surface
        # the full lifecycle, including post-close mutations.
        "decision.outcome_attached",
        # RFC 09: Instinct-gate evaluations are part of the chain — the
        # last ``policy.evaluated`` before close becomes the
        # projection's ``Decision.instinct_policy``.
        "policy.evaluated",
        # RFC 09: canonical chain terminator. See ``build_completion_event``.
        "decision.completed",
    }
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
    "CompletionStatus",
    "build_proposal_event",
    "build_correction_event",
    "build_policy_event",
    "build_completion_event",
    "find_corrections_for",
    "trace_decision_chain",
    "cluster_correction_patterns",
]
