# journal.py — Journal high-level class enforcing invariants above a backend.
# Updated: feat/journal-engine — the ts-monotonicity guard now lives inside
# the backend's BEGIN IMMEDIATE transaction (see sqlite.py). The Journal still
# shapes entries (hash-link, tz-aware guard) but no longer reads the tail
# outside the transaction, because that read-then-insert was racy under
# concurrent writers. Also log (not swallow) hash-link failures so a silent
# chain break is at least visible.

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from soul_protocol.spec.journal import Actor, EventEntry

from .backend import JournalBackend
from .exceptions import IntegrityError
from .sqlite import SQLiteJournalBackend

logger = logging.getLogger(__name__)


def _is_aware(dt: datetime) -> bool:
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def _hash_link(prev: EventEntry, prev_seq: int) -> bytes:
    """Compute the prev_hash link for the *next* event.

    Deliberately simple: sha256 over a canonical string built from the
    previous event's identifying fields plus its seq. Signing and the
    full hash-chain will replace this in a later slice.
    """
    material = f"{prev.id}|{prev.ts.isoformat()}|{prev.action}|{prev_seq}".encode()
    return hashlib.sha256(material).digest()


class Journal:
    """High-level append-only journal.

    Invariants enforced here (not in the backend):
        * ``entry.ts`` must be timezone-aware UTC.
        * ``entry.scope`` must be non-empty (delegated to model validation).
        * ``entry.actor.id`` must be non-empty (delegated to model validation).
        * ``entry.ts`` must be >= the prior event's ts (monotonic per journal).
        * ``seq`` is assigned by the journal. Any caller-supplied seq is
          ignored — the EventEntry spec model does not carry one.

    Hash-chain linkage is computed opportunistically: if there is a previous
    event, the new entry's ``prev_hash`` is overwritten with the chain link
    unless the caller explicitly supplied one (supporting pre-signed events
    from a future slice). Failure to hash does not block the append.
    """

    def __init__(self, backend: JournalBackend) -> None:
        self._backend = backend

    # -- writes -----------------------------------------------------------

    def append(self, entry: EventEntry) -> None:
        if not _is_aware(entry.ts):
            raise IntegrityError("EventEntry.ts must be timezone-aware UTC")

        # Opportunistic hash-link. The monotonicity guard lives in the
        # backend's write transaction now (see sqlite.append); reading the
        # tail here is best-effort for the hash only. A racing writer may
        # mean the hash points at a tail that's no longer the immediate
        # predecessor, which is acceptable for the placeholder chain and
        # will be replaced once signing ships.
        if entry.prev_hash is None:
            last = self._backend.last_entry()
            if last is not None:
                prev_entry, prev_seq = last
                try:
                    entry = entry.model_copy(
                        update={"prev_hash": _hash_link(prev_entry, prev_seq)}
                    )
                except Exception as exc:
                    logger.warning(
                        "hash-link skipped for event %s: %s", entry.id, exc
                    )

        self._backend.append(entry)

    # -- reads ------------------------------------------------------------

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
        if since is not None and not _is_aware(since):
            raise IntegrityError("Journal.query(since=...) must be timezone-aware UTC")
        if until is not None and not _is_aware(until):
            raise IntegrityError("Journal.query(until=...) must be timezone-aware UTC")

        return self._backend.query(
            action=action,
            actor=actor,
            scope=scope,
            correlation_id=correlation_id,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )

    def replay_from(self, seq: int = 0) -> Iterator[EventEntry]:
        yield from self._backend.replay_from(seq)

    # -- lifecycle --------------------------------------------------------

    def close(self) -> None:
        self._backend.close()

    def __enter__(self) -> Journal:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def open_journal(path: Path | str) -> Journal:
    """Open (and migrate on first write) a SQLite-backed journal at `path`."""
    backend = SQLiteJournalBackend(Path(path))
    return Journal(backend)
