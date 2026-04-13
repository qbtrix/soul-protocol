# backend.py — Journal backend Protocol.
# Created: feat/journal-engine — Workstream A slice 2 of Org Architecture RFC (#164).
# The Journal class delegates persistence to a JournalBackend. v1 ships a
# single SQLite implementation; future backends (LMDB, Postgres, pluggable
# remote) implement the same Protocol.

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from soul_protocol.spec.journal import Actor, EventEntry


@runtime_checkable
class JournalBackend(Protocol):
    """Storage contract for journal events. All methods are synchronous."""

    def append(self, entry: EventEntry) -> int:
        """Persist `entry`, assigning and returning its monotonic seq atomically."""

    def query(
        self,
        *,
        action: str | None = None,
        actor: Actor | None = None,
        scope: list[str] | None = None,
        correlation_id: UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventEntry]:
        """Return events matching the conjunction of filters."""

    def replay_from(self, seq: int = 0) -> Iterator[EventEntry]:
        """Yield events with seq >= given value in ascending seq order."""

    def last_entry(self) -> tuple[EventEntry, int] | None:
        """Return (last_entry, last_seq) or None if journal is empty."""

    def close(self) -> None:
        """Release any resources. Idempotent."""
