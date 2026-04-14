# journal.py — Org Journal primitives (Actor, DataRef, EventEntry).
# Updated: feat/journal-spec — tighten DataRef.point_in_time to UTC-only
# (non-UTC tz-aware datetimes now raise instead of being silently accepted),
# add a __dataref__ marker so the `DataRef | dict` payload union on
# EventEntry round-trips without silent misdeserialization, and drop the
# fabric.* namespaces from ACTION_NAMESPACES (runtime-specific, not protocol).
# The journal is the append-only, UTC-stamped, scope-tagged source of truth
# for an org instance. This module ships the spec models only — the SQLite WAL
# engine and the `soul org init` CLI land in follow-up PRs.
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
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_serializer, model_validator
from pydantic.functional_serializers import PlainSerializer
from pydantic.functional_validators import BeforeValidator

# Marker written on JSON-serialized DataRef payloads so the `DataRef | dict`
# union in EventEntry.payload can be disambiguated on the way back in.
# A plain dict payload that happens to carry DataRef-shaped keys (e.g. a user
# query dict with a "source" field) would otherwise get silently coerced into
# a DataRef on deserialization — and that silent coercion is the bug this
# discriminator closes.
_DATAREF_MARKER = "__dataref__"


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
    "org.destroyed",
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
    # Retrieval & scope
    "retrieval.query",
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

    @model_serializer(mode="wrap", when_used="json")
    def _serialize_with_marker(self, handler: Any) -> dict[str, Any]:
        """Stamp ``__dataref__: true`` on every JSON dump so a
        ``DataRef | dict`` union can disambiguate on the way back in.
        """
        data = handler(self)
        data[_DATAREF_MARKER] = True
        return data

    @model_validator(mode="before")
    @classmethod
    def _strip_marker(cls, data: Any) -> Any:
        """Strip the ``__dataref__`` marker before field validation so
        round-tripped JSON payloads don't trip extra-fields checks."""
        if isinstance(data, dict) and _DATAREF_MARKER in data:
            data = {k: v for k, v in data.items() if k != _DATAREF_MARKER}
        return data

    @field_validator("point_in_time")
    @classmethod
    def _point_in_time_must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("DataRef.point_in_time must be timezone-aware (UTC)")
        offset = v.tzinfo.utcoffset(v)
        if offset is None:
            raise ValueError("DataRef.point_in_time must be timezone-aware (UTC)")
        if offset != timedelta(0):
            raise ValueError(
                "DataRef.point_in_time must be UTC — got offset "
                f"{offset}. Normalize at the source."
            )
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
    payload: dict | DataRef = Field(default_factory=dict)
    prev_hash: JournalBytes = None
    sig: JournalBytes = None

    @field_validator("payload", mode="before")
    @classmethod
    def _disambiguate_payload(cls, v: Any) -> Any:
        """Use the ``__dataref__`` marker to tell a DataRef payload apart
        from a plain dict that happens to share DataRef field names.

        A ``DataRef | dict`` union would otherwise greedily coerce any
        dict carrying the right shape (``source``, ``query``,
        ``point_in_time``) into a DataRef on deserialization. By round-
        tripping DataRef with an explicit marker, we can keep dicts as
        dicts unless the caller opted into DataRef semantics, and
        promote marked dicts to a concrete DataRef before the union sees
        them so the choice is unambiguous.
        """
        if isinstance(v, DataRef):
            return v
        if isinstance(v, dict):
            if v.get(_DATAREF_MARKER) is True:
                inner = {k: val for k, val in v.items() if k != _DATAREF_MARKER}
                return DataRef.model_validate(inner)
            # No marker — keep as a plain dict. Return a fresh dict so
            # pydantic's union resolver sees a clean shape (not a
            # DataRef-lookalike that would otherwise match first).
            return dict(v)
        return v

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
