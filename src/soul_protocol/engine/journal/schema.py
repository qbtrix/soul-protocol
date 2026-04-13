# schema.py — SQLite schema + migration helper for the journal engine.
# Created: feat/journal-engine — Workstream A slice 2 of Org Architecture RFC (#164).
# Schema v1 ships with this slice. Future versions bump SCHEMA_VERSION and add a
# migration branch in `migrate()` — we never drop or rewrite history.

from __future__ import annotations

import sqlite3

from .exceptions import SchemaError

SCHEMA_VERSION = 1

CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    actor_kind TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    scope TEXT NOT NULL,
    causation_id TEXT,
    correlation_id TEXT,
    payload TEXT NOT NULL,
    prev_hash BLOB,
    sig BLOB,
    seq INTEGER NOT NULL UNIQUE
);
"""

CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);",
    "CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);",
    "CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor_kind, actor_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_seq ON events(seq);",
)

CREATE_META = """
CREATE TABLE IF NOT EXISTS journal_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def migrate(conn: sqlite3.Connection) -> None:
    """Bring a connection's database up to SCHEMA_VERSION.

    Idempotent — safe to call on every open. Raises SchemaError if the
    on-disk version is newer than what this engine understands.
    """
    cur = conn.cursor()
    cur.execute(CREATE_META)
    cur.execute("SELECT value FROM journal_meta WHERE key = 'schema_version'")
    row = cur.fetchone()
    current = int(row[0]) if row else 0

    if current > SCHEMA_VERSION:
        raise SchemaError(
            f"journal schema v{current} is newer than engine v{SCHEMA_VERSION}; "
            "upgrade soul-protocol"
        )

    if current < 1:
        cur.execute(CREATE_EVENTS)
        for stmt in CREATE_INDEXES:
            cur.execute(stmt)
        cur.execute(
            "INSERT OR REPLACE INTO journal_meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
    conn.commit()
