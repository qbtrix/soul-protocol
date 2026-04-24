---
{
  "title": "SQLite WAL-Mode Journal Backend",
  "summary": "Implements `JournalBackend` using SQLite with WAL mode, providing append-only event storage with strict sequential ordering and monotonic timestamp enforcement. A single threading lock serializes all writes while allowing concurrent readers through WAL isolation.",
  "concepts": [
    "SQLite backend",
    "WAL mode",
    "journal",
    "append-only",
    "seq monotonicity",
    "timestamp monotonicity",
    "DataRef",
    "payload encoding",
    "query filtering",
    "scope matching",
    "replay",
    "threading lock",
    "BEGIN IMMEDIATE"
  ],
  "categories": [
    "database",
    "journal",
    "persistence",
    "concurrency"
  ],
  "source_docs": [
    "14361e8d598e972f"
  ],
  "backlinks": null,
  "word_count": 503,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`SQLiteJournalBackend` is the production storage engine for the journal. It stores events in an append-only SQLite database, provides rich query capabilities, and enforces two invariants that make the journal reliable as an event source: strictly monotonic `seq` and approximately monotonic `ts`.

## Connection Setup

```python
self._conn = sqlite3.connect(
    str(path),
    check_same_thread=False,
    isolation_level=None,  # autocommit; explicit transactions
    timeout=30.0,
)
self._conn.execute("PRAGMA journal_mode=WAL")
self._conn.execute("PRAGMA synchronous=NORMAL")
```

- **WAL mode** allows readers to proceed while a write is in progress, preventing reader starvation under write load.
- `check_same_thread=False` lets the backend be shared across threads; the write lock makes this safe.
- `isolation_level=None` disables SQLite's implicit transaction wrapping so explicit `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` give full control.

## Append Path and Monotonicity Policy

The `append()` method runs under `self._lock` and inside `BEGIN IMMEDIATE`, so two concurrent writers are serialized at the database level:

```python
with self._lock:
    self._conn.execute("BEGIN IMMEDIATE")
    # read tail, check ts, assign seq, INSERT, COMMIT
```

**Why `BEGIN IMMEDIATE`?** SQLite's default deferred transactions allow two writers to both pass a pre-transaction read before either commits. Moving the monotonicity check inside `BEGIN IMMEDIATE` closes this race window.

**Timestamp policy**:
- Events with `ts >= tail.ts` are accepted as-is.
- Events with `ts < tail.ts` by more than 100ms raise `IntegrityError` — this catches real clock errors (wall-clock jumps, stale timestamps from callers).
- Events with `ts < tail.ts` by 100ms or less get their `ts` bumped to `tail.ts`. This tolerates sub-100ms clock races between concurrent threads calling `datetime.now()` and then racing into `BEGIN IMMEDIATE`.

Net result: `seq` is strictly monotonic; `ts` is monotonic within 100ms tolerance.

## Payload Encoding

Payloads are JSON-serialized strings. A `DataRef` (pointer to external blob storage) is distinguished from a plain dict using a sentinel tag:

```python
DATAREF_TAG = "__dataref__"

def _encode_payload(payload: DataRef | dict[str, Any]) -> str:
    if isinstance(payload, DataRef):
        body = payload.model_dump(mode="json")
        return json.dumps({DATAREF_TAG: True, **body})
    return json.dumps(payload)
```

On read, `_decode_payload()` checks for the tag and reconstructs the `DataRef` model. This avoids a separate column or table for large payloads while keeping the type round-trippable.

## Query Interface

`query()` accepts a rich set of filters:
- `action` — exact match
- `action_prefix` — dotted namespace prefix (`fabric` matches `fabric`, `fabric.x`, `fabric.x.y`). LIKE wildcards are escaped to prevent injection.
- `actor` — `(actor_kind, actor_id)` pair
- `correlation_id` — UUID
- `since` / `until` — ISO timestamp range
- `scope` — post-filter using `scope_matches()` from the public scope module

Scope filtering happens in Python after the SQL query because SQLite cannot index into JSON arrays. This is a deliberate trade-off: scope cardinality is usually low and the post-filter is fast.

## Replay

`replay_from(seq)` yields events starting from a given sequence number as a lazy iterator. This powers event replay for new subscribers and recovery scenarios.

## Known Gaps

- Scope filtering is post-SQL Python, not database-side — may become a bottleneck if scope cardinality grows large.
- `_scope_matches` is re-exported under its old private name for backward compatibility with legacy imports. New callers should import from `soul_protocol.engine.journal` directly.