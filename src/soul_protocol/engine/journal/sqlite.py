# sqlite.py — SQLite WAL-mode JournalBackend implementation.
# Updated: feat/retrieval-router — move the scope-matching helper out of this
# module and into the public `.scope` module. `_scope_matches` stays here as a
# re-export for now so the router's legacy import keeps working; new callers
# import `scope_matches` from `soul_protocol.engine.journal`.
# Updated: feat/journal-engine — move the ts-monotonicity check inside the
# BEGIN IMMEDIATE transaction so two concurrent writers can't both pass a
# pre-transaction read and land events with out-of-order timestamps. The
# previous check-then-insert pattern left a race window between the last_entry
# read and the INSERT.
# Uses sqlite3 stdlib only. WAL is enabled on open for concurrent-reader
# safety and durable append-only writes. Payload is stored as JSON; either a
# plain dict or a DataRef-tagged object (see _encode_payload).

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from soul_protocol.spec.journal import Actor, DataRef, EventEntry

from .backend import JournalBackend
from .exceptions import IntegrityError
from .schema import migrate

DATAREF_TAG = "__dataref__"


def _encode_payload(payload: DataRef | dict[str, Any]) -> str:
    if isinstance(payload, DataRef):
        body = payload.model_dump(mode="json")
        return json.dumps({DATAREF_TAG: True, **body})
    return json.dumps(payload)


def _decode_payload(raw: str) -> DataRef | dict[str, Any]:
    obj = json.loads(raw)
    if isinstance(obj, dict) and obj.get(DATAREF_TAG) is True:
        data = {k: v for k, v in obj.items() if k != DATAREF_TAG}
        return DataRef.model_validate(data)
    return obj


from .scope import scope_matches as _scope_matches
# Re-export under the old private name so existing imports
# (including the router's direct reach into this module) keep working
# until they're migrated over to the public path.
__all_legacy__ = ("_scope_matches",)


class SQLiteJournalBackend(JournalBackend):
    """SQLite-backed journal with WAL mode and a single serialized writer."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # check_same_thread=False so a Journal can be handed across threads;
        # we serialize writes through self._lock ourselves.
        self._conn = sqlite3.connect(
            str(path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage transactions explicitly
            timeout=30.0,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        migrate(self._conn)

    # -- writes -----------------------------------------------------------

    def append(self, entry: EventEntry) -> int:
        """Persist an event with atomic seq assignment and monotonic-ts check.

        Monotonicity policy — worth knowing before relying on exact ts ordering:

        - Events whose ts is >= the tail's ts are accepted as-is.
        - Events whose ts is LESS than tail ts by more than 100ms raise
          ``IntegrityError``. This catches real clock errors (wall clock
          jumped back, caller passed a stale ts from minutes ago, etc).
        - Events whose ts is less than tail by <= 100ms get their ts bumped
          up to the tail's ts. This tolerates the sub-100ms clock races
          that occur when two threads call ``datetime.now(UTC)`` and then
          race into ``BEGIN IMMEDIATE``. The combined log stays
          non-decreasing; seq ordering (the actual event-order invariant)
          is unaffected. Users reading journal events in seq order see
          monotonic ts without occasional flakes under concurrent load.

        Net effect: seq is strictly monotonic; ts is monotonic to within
        100ms of tolerance for concurrent writers on coarse clocks.
        """
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                # Read the current tail under the write lock so the
                # monotonicity check cannot race another writer that passed
                # its own check before the INSERT. Two concurrent writers
                # will serialize here via BEGIN IMMEDIATE.
                row = self._conn.execute(
                    "SELECT ts, seq FROM events ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                if row is not None:
                    prev_ts = datetime.fromisoformat(row[0])
                    if entry.ts < prev_ts:
                        delta = (prev_ts - entry.ts).total_seconds()
                        if delta >= 0.1:
                            # More than 100ms behind the tail: a real
                            # clock error (caller passed a stale ts, wall
                            # clock jumped backward), not a thread-race
                            # microsecond overlap. Reject it.
                            raise IntegrityError(
                                "EventEntry.ts must be >= previous event's ts "
                                f"({entry.ts.isoformat()} < {prev_ts.isoformat()})"
                            )
                        # Sub-100ms race: a concurrent writer committed
                        # between our now() read and our BEGIN IMMEDIATE.
                        # Stamp at the tail so the combined log stays
                        # non-decreasing. See docstring for the policy.
                        entry = entry.model_copy(update={"ts": prev_ts})
                    seq = int(row[1]) + 1
                else:
                    seq = 0
                self._conn.execute(
                    """
                    INSERT INTO events (
                        id, ts, actor_kind, actor_id, action, scope,
                        causation_id, correlation_id, payload,
                        prev_hash, sig, seq
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(entry.id),
                        entry.ts.isoformat(),
                        entry.actor.kind,
                        entry.actor.id,
                        entry.action,
                        json.dumps(entry.scope),
                        str(entry.causation_id) if entry.causation_id else None,
                        str(entry.correlation_id) if entry.correlation_id else None,
                        _encode_payload(entry.payload),
                        entry.prev_hash,
                        entry.sig,
                        seq,
                    ),
                )
                self._conn.execute("COMMIT")
                return seq
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def last_entry(self) -> tuple[EventEntry, int] | None:
        row = self._conn.execute(
            "SELECT * FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        entry, seq = self._row_to_entry(row)
        return entry, seq

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
        clauses: list[str] = []
        params: list[Any] = []
        if action is not None:
            clauses.append("action = ?")
            params.append(action)
        if actor is not None:
            clauses.append("actor_kind = ? AND actor_id = ?")
            params.extend([actor.kind, actor.id])
        if correlation_id is not None:
            clauses.append("correlation_id = ?")
            params.append(str(correlation_id))
        if since is not None:
            clauses.append("ts >= ?")
            params.append(since.isoformat())
        if until is not None:
            clauses.append("ts <= ?")
            params.append(until.isoformat())

        sql = "SELECT * FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY seq ASC"

        rows = self._conn.execute(sql, params).fetchall()
        results: list[EventEntry] = []
        for row in rows:
            entry, _seq = self._row_to_entry(row)
            if scope is not None and not _scope_matches(entry.scope, scope):
                continue
            results.append(entry)

        return results[offset : offset + limit]

    def replay_from(self, seq: int = 0) -> Iterator[EventEntry]:
        cur = self._conn.execute(
            "SELECT * FROM events WHERE seq >= ? ORDER BY seq ASC", (seq,)
        )
        for row in cur:
            entry, _seq = self._row_to_entry(row)
            yield entry

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.ProgrammingError:
                pass  # already closed

    # -- internals --------------------------------------------------------

    def _row_to_entry(self, row: sqlite3.Row | tuple) -> tuple[EventEntry, int]:
        # Column order matches CREATE TABLE in schema.py.
        (
            id_,
            ts,
            actor_kind,
            actor_id,
            action,
            scope_json,
            causation_id,
            correlation_id,
            payload_json,
            prev_hash,
            sig,
            seq,
        ) = row
        entry = EventEntry(
            id=UUID(id_),
            ts=datetime.fromisoformat(ts),
            actor=Actor(kind=actor_kind, id=actor_id),
            action=action,
            scope=json.loads(scope_json),
            causation_id=UUID(causation_id) if causation_id else None,
            correlation_id=UUID(correlation_id) if correlation_id else None,
            payload=_decode_payload(payload_json),
            prev_hash=prev_hash,
            sig=sig,
        )
        return entry, int(seq)
