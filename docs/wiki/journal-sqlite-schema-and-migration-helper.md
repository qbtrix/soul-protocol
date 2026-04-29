---
{
  "title": "Journal SQLite Schema and Migration Helper",
  "summary": "Defines the SQLite schema for the soul-protocol journal engine and provides an idempotent migration function. Ensures the on-disk database is always brought up to the current schema version before use, preventing schema drift between engine upgrades.",
  "concepts": [
    "SQLite schema",
    "journal engine",
    "migration",
    "schema version",
    "event table",
    "idempotent migration",
    "seq monotonicity",
    "hash chaining",
    "causation_id",
    "correlation_id",
    "SchemaError",
    "WAL mode",
    "DDL"
  ],
  "categories": [
    "database",
    "journal",
    "persistence",
    "schema"
  ],
  "source_docs": [
    "b709d8ada819f996"
  ],
  "backlinks": null,
  "word_count": 576,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The journal engine persists all soul events to a local SQLite database. `schema.py` owns two concerns: the DDL that describes the database structure, and the `migrate()` function that applies it safely every time a connection is opened.

## Schema Design

### `events` Table

The core table stores every event the journal records:

```python
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
```

Key design decisions:
- `seq` is a strictly monotonic integer that defines event ordering, independent of wall-clock time. This handles clock skew and concurrent writers correctly.
- `prev_hash` and `sig` fields exist to support hash-chaining and cryptographic signing — enabling tamper-evident audit logs in the future.
- `causation_id` and `correlation_id` link events together into causal chains and distributed traces. `causation_id` points to the single event that caused this one; `correlation_id` groups a whole workflow.
- All IDs are TEXT (UUIDs stored as strings) for maximum portability across SQLite versions.

### Indexes

Five indexes cover the most common read patterns:

```python
CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);",
    "CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);",
    "CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor_kind, actor_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_seq ON events(seq);",
)
```

Without these, time-range queries (`since`/`until`), action-prefix filters, and correlation lookups would require full table scans, becoming impractical as event counts grow.

### `journal_meta` Table

A simple key-value store used to track the schema version number. This is the minimum metadata needed to make migration decisions without adding a migration-tracking library.

## Migration Logic

The `migrate()` function is the critical bridge between schema definition and runtime use:

```python
def migrate(conn: sqlite3.Connection) -> None:
    """Bring a connection's database up to SCHEMA_VERSION. Idempotent."""
```

**Idempotency**: The function uses `CREATE TABLE IF NOT EXISTS` for all DDL statements. Calling it on an already-initialized database is a no-op, so it can safely be called on every connection open without checking first.

**Forward-compatibility guard**: If the on-disk `schema_version` is *newer* than `SCHEMA_VERSION`, the engine raises `SchemaError` immediately. This prevents a downgraded engine from silently corrupting a database that was written by a newer version — a failure mode that would be difficult to debug and potentially unrecoverable.

**Version-gated DDL**: Migration branches are additive only (`current < 1` applies version 1 DDL, future versions will add `elif current < 2` branches, etc.). This ensures history is never dropped or rewritten, honoring the project's append-only event log contract.

## Data Flow

1. `SQLiteJournalBackend.__init__()` calls `migrate(conn)` immediately after opening the connection.
2. `migrate()` reads or bootstraps the `journal_meta` version row.
3. If the version is current, `migrate()` returns immediately.
4. If migration is needed, DDL runs inside the same implicit transaction as the `INSERT OR REPLACE` that updates the version.

## Known Gaps

- No rollback mechanism: if a future migration step fails partway, the version row may not be updated, but partial DDL changes could be committed. The current v1 schema is simple enough that this is not a concern, but multi-step migrations would need explicit transaction wrapping.
- Schema currently at `SCHEMA_VERSION = 1`. Future work (cryptographic signing, multi-participant scopes) will require bumping this and adding migration branches.