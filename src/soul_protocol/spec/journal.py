# journal.py — Org Journal primitives (Actor, DataRef, EventEntry).
# Created: feat/journal-spec — Phase 1 slice of the Org Architecture RFC (PR #164).
# The journal is the append-only, UTC-stamped, scope-tagged source of truth for
# a Paw OS instance. This module ships the spec models only — the SQLite WAL
# engine and the `paw os init` CLI land in follow-up PRs.
#
# Semantics locked here:
#   - `ts` and `DataRef.point_in_time` must be timezone-aware (UTC). Naive
#     datetimes raise at validation time. The journal layer is where the
#     project's naive-datetime bugs get fixed, not per subsystem.
#   - `scope` is required and non-empty. There is no "global" write path.
#   - `action` is a free-form dot-separated string; see ACTION_NAMESPACES for
#     the initial catalog, kept as a constant (not an enum) so callers can ship
#     new action names additively without a library upgrade.
#   - `payload` is a union of `dict` or `DataRef` — inline data or an external
#     reference for Zero-Copy sources.

from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from pydantic.functional_serializers import PlainSerializer
from pydantic.functional_validators import BeforeValidator


def _decode_bytes(v: object) -> bytes | None:
    """Accept raw bytes or a base64-encoded string (JSON round-trip) or None."""
    if v is None or isinstance(v, bytes):
        return v  # type: ignore[return-value]
    if isinstance(v, str):
        return base64.b64decode(v)
    raise TypeError(f"expected bytes, str, or None — got {type(v).__name__}")


def _encode_bytes(v: bytes | None) -> str | None:
    """Serialize bytes to a base64 string for JSON transport."""
    if v is None:
        return None
    return base64.b64encode(v).decode("ascii")


JournalBytes = Annotated[
    bytes | None,
    BeforeValidator(_decode_bytes),
    PlainSerializer(_encode_bytes, return_type=str, when_used="json"),
]
"""Optional raw bytes that round-trip through JSON as base64 strings."""


ACTION_NAMESPACES: tuple[str, ...] = (
    # Governance (root-signed)
    "org.created",
    "schema.migrated",
    "user.admin_granted",
    "user.admin_revoked",
    "scope.created",
    "key.rotated",
    "paw.os.destroyed",
    # Identity
    "agent.spawned",
    "agent.retired",
    "user.joined",
    "user.left",
    "team.created",
    "team.disbanded",
    "soul.exported",
    "soul.imported",
    # Memory & Knowledge
    "memory.remembered",
    "memory.graduated",
    "memory.forgotten",
    "kb.source.ingested",
    "kb.article.compiled",
    "kb.article.revised",
    # Retrieval & Fabric
    "retrieval.query",
    "fabric.object.created",
    "fabric.object.updated",
    "fabric.object.archived",
    "scope.assigned",
    "scope.revoked",
    # Decisions
    "agent.proposed",
    "human.corrected",
    "decision.graduated",
    # Credentials & Zero-Copy
    "credential.acquired",
    "credential.used",
    "credential.expired",
    "dataref.resolved",
    # Graduation & Policy
    "graduation.applied",
    "policy.evaluated",
)
"""The initial event action catalog from the RFC Appendix.

This is a lint/discoverability aid — not enforced as an enum. Callers may
ship new action names additively; removing an action is a schema migration.
"""


ActorKind = Literal["agent", "user", "system", "root"]


class Actor(BaseModel):
    """Who performed the action that produced an event.

    There are no anonymous writes. ``system:*`` actors are reserved for
    subsystem-triggered events (kb compile cascades, graduation scheduler,
    retention policies).

    Fields:
        kind: One of ``agent``, ``user``, ``system``, ``root``.
        id: Stable identifier — ``did:soul:...``, ``user:alice``,
            ``system:kb-go``. Required; empty strings are rejected.
        scope_context: The scopes the actor held when acting. Recorded at
            write time so later scope changes don't rewrite history.
    """

    kind: ActorKind
    id: str = Field(min_length=1)
    scope_context: list[str] = Field(default_factory=list)


CachePolicy = Literal["always", "invalidate_on_event", "ttl"]


class DataRef(BaseModel):
    """A reference to data that lives outside the journal.

    Used for Zero-Copy retrieval against live systems (Salesforce, Drive,
    Snowflake, S3, ...) where freshness and data-residency matter more than
    retrieval latency. The journal records the *reference*, not the payload.

    Fields:
        source: Source adapter name (``"salesforce"``, ``"gdrive"``,
            ``"snowflake"``, ``"s3"``, ...).
        query: Source-native query recipe. Opaque to the journal.
        point_in_time: Timezone-aware UTC timestamp the reference was taken
            at. Naive datetimes raise.
        cache_policy: How downstream caches should treat this ref.
        cache_ttl_s: TTL for the ``ttl`` policy, in seconds. ``None`` when
            the policy is not ``ttl``.
    """

    source: str = Field(min_length=1)
    query: str
    point_in_time: datetime
    cache_policy: CachePolicy = "ttl"
    cache_ttl_s: int | None = None

    @field_validator("point_in_time")
    @classmethod
    def _point_in_time_must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("DataRef.point_in_time must be timezone-aware (UTC)")
        return v


class EventEntry(BaseModel):
    """A single immutable event in the org journal.

    The journal is append-only: there is no ``UPDATE`` and no ``DELETE``.
    Corrections are new events that reference the original via
    ``causation_id``. Every event carries a non-empty ``scope`` — unscoped
    writes are rejected.

    Fields:
        id: UUID for this event.
        ts: Timezone-aware UTC timestamp. Monotonic per journal (enforced
            at the engine layer, not here). Naive datetimes raise.
        actor: Who wrote this event.
        action: Dot-separated namespaced verb. Not enum-enforced — see
            :data:`ACTION_NAMESPACES` for the initial catalog.
        scope: DSP scope tags (from #162). Required and non-empty.
        causation_id: The prior event that caused this one, or ``None``
            for genesis / unsolicited events.
        correlation_id: The session or flow this event belongs to, or
            ``None`` if the event stands alone.
        payload: Either an inline dict (small structured data) or a
            :class:`DataRef` (external reference for Zero-Copy sources).
            Large binary payloads go to blob storage with a DataRef here.
        prev_hash: Optional hash-chain link to the previous event. Will
            become required once signing ships.
        sig: Optional signature over ``(id, ts, actor, action, prev_hash)``.
    """

    id: UUID
    ts: datetime
    actor: Actor
    action: str = Field(min_length=1)
    scope: list[str] = Field(min_length=1)
    causation_id: UUID | None = None
    correlation_id: UUID | None = None
    payload: DataRef | dict = Field(default_factory=dict)
    prev_hash: JournalBytes = None
    sig: JournalBytes = None

    @field_validator("ts")
    @classmethod
    def _ts_must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("EventEntry.ts must be timezone-aware (UTC)")
        return v

    @field_validator("scope")
    @classmethod
    def _scope_entries_non_empty(cls, v: list[str]) -> list[str]:
        if any(not s or not s.strip() for s in v):
            raise ValueError("EventEntry.scope entries must be non-empty strings")
        return v
