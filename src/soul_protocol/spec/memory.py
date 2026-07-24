# memory.py — Memory primitives for the core layer.
# Updated: 2026-07-18 (#285) — Consolidated MemoryEntry from runtime/types.py
#   into spec layer as the single source of truth. Added strict model_validator
#   requiring at least one of ``type`` or non-empty ``layer``. ``id`` defaults
#   to a random uuid hex (was ``""``). Removed duplicate MemoryVisibility.
# Updated: v0.4.0 (#41) — Open layer namespaces + domain isolation. Added
#   LAYER_* string constants (LAYER_CORE, LAYER_EPISODIC, LAYER_SEMANTIC,
#   LAYER_PROCEDURAL, LAYER_SOCIAL) so runtimes have well-known names without
#   freezing them into an enum. Added ``MemoryEntry.domain: str = "default"``
#   for sub-namespacing inside a layer (e.g. "finance" vs "legal" facts).
#   ``MemoryStore`` protocol grew optional ``domain`` filters on ``recall``
#   and ``search`` so callers can scope queries without iterating all layers.
# Updated: v0.4.0 — Added ingested_at and superseded fields to MemoryEntry
#   for bi-temporal timestamps and contradiction detection support.
# Updated: feat/spec-multi-participant — Added Participant model and Interaction model
#   for multi-participant interactions. Interaction supports N participants with
#   backward-compatible user_input/agent_output properties and from_pair() factory.
# Created: v0.4.0 — MemoryEntry (atomic unit), MemoryStore (protocol),
# and DictMemoryStore (in-memory reference implementation).
# Layers are free-form strings, NOT enums — runtimes define their own namespaces.

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, Self, runtime_checkable

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Standard layer names. These are conventions, not constraints — runtimes are
# free to define any layer string they want. The constants exist so callers
# don't have to spell the strings literally.
# ---------------------------------------------------------------------------

LAYER_CORE: str = "core"
LAYER_EPISODIC: str = "episodic"
LAYER_SEMANTIC: str = "semantic"
LAYER_PROCEDURAL: str = "procedural"
LAYER_SOCIAL: str = "social"

# ---------------------------------------------------------------------------
# Default domain. Domains are sub-namespaces inside a layer — "finance" vs.
# "legal" inside the same layer of facts. Entries without an explicit domain
# get this value so legacy data round-trips with no migration step.
# ---------------------------------------------------------------------------

DEFAULT_DOMAIN: str = "default"


class MemoryVisibility(StrEnum):
    """Visibility tier for memory entries in public channel contexts."""

    PUBLIC = "public"
    BONDED = "bonded"
    PRIVATE = "private"


class Participant(BaseModel):
    """A participant in an interaction.

    Role is a free-form string — runtimes define their own roles.
    Common roles: "user", "agent", "soul", "system", "observer".
    """

    role: str  # "user", "agent", "soul", "system", etc.
    id: str | None = None  # DID or identifier
    content: str


class Interaction(BaseModel):
    """A multi-participant interaction.

    Generalizes the 2-party (user/agent) interaction model to support
    N participants. Backward compatible: ``user_input`` and ``agent_output``
    properties return the first "user" and "agent" participant content.

    Use ``from_pair()`` for the common 2-party case.
    """

    participants: list[Participant]
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def user_input(self) -> str:
        """Content from the first 'user' participant (backward compat)."""
        for p in self.participants:
            if p.role == "user":
                return p.content
        return ""

    @property
    def agent_output(self) -> str:
        """Content from the first 'agent' participant (backward compat)."""
        for p in self.participants:
            if p.role == "agent":
                return p.content
        return ""

    @classmethod
    def from_pair(
        cls,
        user_input: str,
        agent_output: str,
        *,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Interaction:
        """Create a 2-party interaction from user input and agent output.

        This is the common case — most interactions are simple request/response.
        """
        return cls(
            participants=[
                Participant(role="user", content=user_input),
                Participant(role="agent", content=agent_output),
            ],
            timestamp=timestamp or datetime.now(),
            metadata=metadata or {},
        )


class SomaticMarker(BaseModel):
    """Emotional context tagged onto a memory (Damasio's Somatic Marker Hypothesis).

    Emotions are not separate from cognition — they guide recall and decision-making.
    """

    valence: float = Field(default=0.0, ge=-1.0, le=1.0)  # negative to positive
    arousal: float = Field(default=0.0, ge=0.0, le=1.0)  # calm to intense
    label: str = "neutral"  # joy, frustration, curiosity, etc.


class MemoryProvenance(StrEnum):
    """Who authored a memory entry.

    Distinguishes human-authored memories from those written autonomously
    by an agent (e.g. PocketPaw's self-improving skills loop, where a forked
    write-only reviewer learns a procedure from a session transcript). The
    curator only ever consolidates / archives ``AGENT`` entries — human-authored
    procedures are never touched. Defaults to ``HUMAN`` so pre-provenance souls
    round-trip without migration.
    """

    HUMAN = "human"
    AGENT = "agent"


class MemoryType(StrEnum):
    """Built-in memory tiers. v0.4.0 (#41) treats these as ergonomic
    constants for layer names — runtimes can use any string layer they
    want via :class:`soul_protocol.runtime.memory.manager.LayerView`."""

    CORE = "core"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    SOCIAL = "social"  # v0.4.0 (#41) — relationship memory tier


class MemoryCategory(StrEnum):
    """Structured extraction taxonomy for memory classification.

    User-facing categories (about the bonded entity):
    - PROFILE: Static identity attributes (name, role, location)
    - PREFERENCE: Choices and habits (one facet per memory)
    - ENTITY: Named things with attributes (projects, people, tools)
    - EVENT: Time-bound activities (always absolute timestamps)

    Agent-facing categories (about what the soul learned):
    - CASE: Problem + cause + solution + outcome
    - PATTERN: Reusable processes across scenarios
    - SKILL: Skill execution strategies and tool usage knowledge
    """

    # User-facing (feed the bond system / human profile)
    PROFILE = "profile"
    PREFERENCE = "preference"
    ENTITY = "entity"
    EVENT = "event"
    # Agent-facing (feed the self-model)
    CASE = "case"
    PATTERN = "pattern"
    SKILL = "skill"


class MemoryEntry(BaseModel):
    """A single memory with metadata.

    v0.4.0 (#41) additions: ``layer`` is the canonical going-forward layer
    name (free-form string). Defaults to the ``type`` value when not given,
    so legacy callers using ``MemoryEntry(type=MemoryType.SEMANTIC)`` get
    ``layer="semantic"`` for free. ``domain`` is a sub-namespace inside the
    layer (``"finance"``, ``"legal"``, ``"default"``); defaults to
    ``"default"`` so 0.3.x entries round-trip without migration.

    v0.3.4 additions: category (extraction taxonomy), abstract (L0 ~100 tokens),
    overview (L1 ~1K tokens) for progressive content loading, salience (retrieval
    weight). All new fields default to None for backwards compatibility.

    v0.2.0 additions: somatic markers (emotional context), access_timestamps
    (full history for ACT-R decay), significance score, and general_event_id
    (Conway hierarchy link). All new fields default to None/empty for
    backwards compatibility with v0.1.0 data.
    """

    model_config = {
        "json_schema_extra": {
            "anyOf": [
                {"required": ["type"], "properties": {"type": {"not": {"type": "null"}}}},
                {
                    "required": ["layer"],
                    "properties": {"layer": {"type": "string", "minLength": 1}},
                },
            ]
        }
    }

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: MemoryType | None = None
    content: str
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: int = Field(default=5, ge=1, le=10)
    emotion: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    entities: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    last_accessed: datetime | None = None
    access_count: int = 0
    # v0.2.0 — Psychology-informed fields
    somatic: SomaticMarker | None = None
    access_timestamps: list[datetime] = Field(default_factory=list)
    significance: float = 0.0
    general_event_id: str | None = None
    # v0.2.2 — Fact conflict resolution
    superseded_by: str | None = None
    # v0.3.4 — Extraction taxonomy and progressive content loading
    category: MemoryCategory | None = None
    abstract: str | None = None  # L0: ~100 token semantic fingerprint
    overview: str | None = None  # L1: ~1K token structured summary
    salience: float = Field(default=0.5, ge=0.0, le=1.0)  # Retrieval weight
    # v0.4.0 — Bi-temporal ingestion timestamp
    ingested_at: datetime | None = None  # When memory entered the pipeline
    # v0.4.0 — Contradiction detection
    superseded: bool = False  # True when a newer memory contradicts this one
    visibility: MemoryVisibility = MemoryVisibility.BONDED
    # F2 archival memory — marks episodic memories that have been archived
    archived: bool = False  # True when memory has been compressed into a ConversationArchive
    # F1 progressive disclosure — runtime-only marker, never persisted
    is_summarized: bool = False  # Runtime marker: True when content replaced with abstract
    # Move 5 PR-A — RBAC/ABAC scope tags. Empty list = no scope assigned
    # (visible to any caller). Hierarchical glob: "org:sales:*" matches
    # "org:sales:leads". Filtered at retrieval time before results reach
    # the LLM.
    scope: list[str] = Field(default_factory=list)
    # v0.4.0 (#46) — Per-user attribution. None = legacy / orphan entry that
    # belongs to the soul's default bond and is visible to any user_id query.
    # When set, recall filters entries to those matching the requested
    # user_id (plus None entries for back-compat).
    user_id: str | None = None
    # v0.4.0 (#41) — Free-form layer namespace. Empty string is coerced to
    # ``type.value`` by ``_coerce_layer_domain`` so legacy callers keep
    # working. When both ``layer`` and ``type`` round-trip on disk, ``layer``
    # is the canonical field; ``type`` exists for back-compat.
    layer: str = ""
    # v0.4.0 (#41) — Domain sub-namespace inside the layer. Use to isolate
    # context like "finance" vs "legal" inside the same layer of facts.
    # Empty string is coerced to "default" by ``_coerce_layer_domain``.
    domain: str = "default"
    # v0.5.0 (#192) — Brain-aligned memory update primitives. See RFC at
    # docs/rfc-memory-update-primitives.md. Backfilled to defaults on awaken
    # for pre-0.5 souls — no migration code needed at load time.
    retrieval_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    # Inverse back-edge of ``superseded_by``. supersede() sets both sides so
    # provenance walks work in either direction. None for entries that have
    # not replaced an older entry.
    supersedes: str | None = None
    # PE score recorded when this entry was written via supersede() or
    # update(). Unset for entries from remember() / observe() — they had no
    # prior trace to predict against. Captured in the trust chain payload too,
    # so verifiers can re-derive how confident the runtime was in the change.
    prediction_error: float | None = Field(default=None, ge=0.0, le=1.0)
    # feat/soul-skills-procedural — authorship tag. HUMAN for every memory the
    # human or the standard observe/remember path writes; AGENT for memories an
    # autonomous loop authors (PocketPaw's self-improving skills reviewer). The
    # procedural curator only consolidates / archives AGENT entries; it never
    # touches HUMAN-authored procedures and never hard-deletes. Defaults to
    # HUMAN so pre-provenance souls round-trip with no migration.
    provenance: MemoryProvenance = MemoryProvenance.HUMAN

    @model_validator(mode="before")
    @classmethod
    def _coerce_layer_domain(cls, data: Any) -> Any:
        """Fill in ``layer``/``domain`` defaults from legacy fields.

        - When ``layer`` is missing or blank, derive it from ``type``.
        - When ``domain`` is missing or blank, set it to ``"default"``.

        This runs at deserialize time, so 0.3.x souls (which carry only
        ``type``) come back with a sensible layer + domain without a
        separate migration pass.
        """
        if isinstance(data, dict):
            layer_val = data.get("layer", "")
            if not layer_val:
                # Pull from type — accepts MemoryType enum or raw string.
                tval = data.get("type")
                if tval is None:
                    pass
                elif isinstance(tval, MemoryType):
                    data["layer"] = tval.value
                elif isinstance(tval, str):
                    data["layer"] = tval
            domain_val = data.get("domain", "")
            if not domain_val:
                data["domain"] = "default"
        return data

    @model_validator(mode="after")
    def _validate_type_or_layer(self) -> Self:
        """Require at least one of type or a non-empty layer."""
        if self.type is None and not self.layer:
            raise ValueError("MemoryEntry must have either a 'type' or a non-empty 'layer'")
        return self

    @property
    def timestamp(self) -> datetime:
        """Backward compatibility alias for created_at."""
        return self.created_at

    @timestamp.setter
    def timestamp(self, value: datetime) -> None:
        self.created_at = value


@runtime_checkable
class MemoryStore(Protocol):
    """Interface for any memory backend.

    Implementations can be in-memory dicts, SQLite, Redis, vector DBs, etc.
    The protocol only requires these five operations.

    ``domain`` filters on ``recall`` and ``search`` are optional. When
    ``domain`` is ``None`` (the default), the store returns entries from
    every domain. When a domain is given, only entries matching it are
    returned. Stamping a domain on stored entries happens via
    ``MemoryEntry.domain`` before calling ``store()``.
    """

    def store(self, layer: str, entry: MemoryEntry) -> str:
        """Store a memory entry in the given layer. Returns the entry ID."""
        ...

    def recall(
        self,
        layer: str,
        *,
        limit: int = 10,
        domain: str | None = None,
    ) -> list[MemoryEntry]:
        """Recall recent memories from a layer, newest first.

        ``domain`` filters to entries whose ``domain`` matches when set;
        defaults to None which returns every domain.
        """
        ...

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        layer: str | None = None,
        domain: str | None = None,
    ) -> list[MemoryEntry]:
        """Search across all layers by content. Returns best matches.

        ``layer`` and ``domain`` filter the result set when set; both
        default to None (search every layer + domain).
        """
        ...

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID. Returns True if found and deleted."""
        ...

    def layers(self) -> list[str]:
        """List all layer names that contain at least one memory."""
        ...


class DictMemoryStore:
    """In-memory implementation of MemoryStore.

    Simple dict-based storage, keyed by layer name. Search uses basic
    token overlap scoring — good enough for testing and small workloads.
    """

    def __init__(self) -> None:
        self._data: dict[str, list[MemoryEntry]] = {}

    def store(self, layer: str, entry: MemoryEntry) -> str:
        """Store a memory entry. Sets entry.layer to match the target layer."""
        entry.layer = layer
        if layer not in self._data:
            self._data[layer] = []
        self._data[layer].append(entry)
        return entry.id

    def recall(
        self,
        layer: str,
        *,
        limit: int = 10,
        domain: str | None = None,
    ) -> list[MemoryEntry]:
        """Return the most recent memories from a layer.

        Filters to ``domain`` when set; otherwise returns every domain.
        """
        entries = self._data.get(layer, [])
        if domain is not None:
            entries = [e for e in entries if e.domain == domain]
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        layer: str | None = None,
        domain: str | None = None,
    ) -> list[MemoryEntry]:
        """Search layers using basic token overlap scoring.

        ``layer`` and ``domain`` narrow the search when set.
        """
        query_tokens = set(query.lower().split())
        if not query_tokens:
            return []

        scored: list[tuple[float, MemoryEntry]] = []
        layer_iter = (
            [(layer, self._data.get(layer, []))] if layer is not None else list(self._data.items())
        )
        for _, entries in layer_iter:
            for entry in entries:
                if domain is not None and entry.domain != domain:
                    continue
                entry_tokens = set(entry.content.lower().split())
                if not entry_tokens:
                    continue
                overlap = len(query_tokens & entry_tokens)
                if overlap > 0:
                    score = overlap / len(query_tokens | entry_tokens)
                    scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID from any layer."""
        for layer_entries in self._data.values():
            for i, entry in enumerate(layer_entries):
                if entry.id == memory_id:
                    layer_entries.pop(i)
                    return True
        return False

    def layers(self) -> list[str]:
        """List layers that have at least one memory."""
        return [layer for layer, entries in self._data.items() if entries]

    def count(self, layer: str | None = None) -> int:
        """Count memories, optionally filtered by layer."""
        if layer is not None:
            return len(self._data.get(layer, []))
        return sum(len(entries) for entries in self._data.values())

    def all_entries(self) -> list[MemoryEntry]:
        """Return all memories across all layers."""
        result: list[MemoryEntry] = []
        for entries in self._data.values():
            result.extend(entries)
        return result
