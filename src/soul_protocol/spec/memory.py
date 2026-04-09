# memory.py — Memory primitives for the core layer.
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
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


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


class MemoryEntry(BaseModel):
    """The atomic unit of memory — minimal, no opinions.

    Every memory has content, a timestamp, and an optional layer namespace.
    Metadata is an open dict for runtime-specific extensions.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = ""
    layer: str = ""
    visibility: MemoryVisibility = MemoryVisibility.BONDED
    metadata: dict[str, Any] = Field(default_factory=dict)
    ingested_at: datetime | None = None  # When memory entered the pipeline
    superseded: bool = False  # True when a newer memory contradicts this one


@runtime_checkable
class MemoryStore(Protocol):
    """Interface for any memory backend.

    Implementations can be in-memory dicts, SQLite, Redis, vector DBs, etc.
    The protocol only requires these five operations.
    """

    def store(self, layer: str, entry: MemoryEntry) -> str:
        """Store a memory entry in the given layer. Returns the entry ID."""
        ...

    def recall(self, layer: str, *, limit: int = 10) -> list[MemoryEntry]:
        """Recall recent memories from a layer, newest first."""
        ...

    def search(self, query: str, *, limit: int = 10) -> list[MemoryEntry]:
        """Search across all layers by content. Returns best matches."""
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

    def recall(self, layer: str, *, limit: int = 10) -> list[MemoryEntry]:
        """Return the most recent memories from a layer."""
        entries = self._data.get(layer, [])
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def search(self, query: str, *, limit: int = 10) -> list[MemoryEntry]:
        """Search all layers using basic token overlap scoring."""
        query_tokens = set(query.lower().split())
        if not query_tokens:
            return []

        scored: list[tuple[float, MemoryEntry]] = []
        for entries in self._data.values():
            for entry in entries:
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
