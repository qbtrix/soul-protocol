---
{
  "title": "Journal Backend Protocol — Storage Contract for Event Journals",
  "summary": "Defines `JournalBackend` as a `runtime_checkable` Protocol (structural interface) that any storage backend must satisfy. Specifies four operations — append, query, replay, and close — with precise filter semantics for the query method.",
  "concepts": [
    "JournalBackend",
    "Protocol",
    "runtime_checkable",
    "append",
    "query",
    "replay_from",
    "EventEntry",
    "action_prefix",
    "monotonic sequence",
    "structural subtyping",
    "journal storage contract",
    "WAL"
  ],
  "categories": [
    "journal-engine",
    "architecture",
    "storage"
  ],
  "source_docs": [
    "74d41b8907bae6c3"
  ],
  "backlinks": null,
  "word_count": 460,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`backend.py` defines the storage contract for the journal engine. `JournalBackend` is a Python `Protocol`, meaning any class that implements its four methods qualifies as a backend without inheriting from it. The `@runtime_checkable` decorator allows `isinstance(obj, JournalBackend)` checks at runtime.

## Why a Protocol Instead of an Abstract Base Class

Using `Protocol` (structural subtyping) rather than `ABC` (nominal subtyping) means:

1. Third-party backends can satisfy the contract without importing `soul_protocol` at all
2. The in-memory test double used in tests does not need to be declared as a `JournalBackend` subclass
3. The contract is expressed entirely by the method signatures, which tools like mypy can verify statically

## The Four Methods

### `append(entry: EventEntry) -> int`
Persists a single event and returns its assigned monotonic sequence number atomically. The atomicity guarantee is critical: if `append` returned `None` and the caller had to read `MAX(seq)` afterward, a concurrent writer could steal the sequence number, causing a race condition in pagination and replay.

### `query(*, ...) -> list[EventEntry]`
Returns events matching the conjunction (AND) of all supplied filters. Key filter options:

| Filter | Type | Notes |
|--------|------|-------|
| `action` | `str \| None` | Exact match |
| `action_prefix` | `str \| None` | Prefix match (mutually exclusive with `action`) |
| `actor` | `Actor \| None` | Filter by event author |
| `scope` | `list[str] \| None` | Scope membership filter |
| `correlation_id` | `UUID \| None` | Group related events |
| `since` / `until` | `datetime \| None` | Time range |
| `limit` / `offset` | `int` | Pagination |

`action` and `action_prefix` are **mutually exclusive**. The `action_prefix` filter was added (feat/0.3.2-spike) to support namespace-family queries like `"org."` without pulling all events into Python and filtering in a loop — the filter is pushed into SQL.

### `replay_from(seq: int = 0) -> Iterator[EventEntry]`
Yields all events with `seq >= seq` in ascending order. This is the recovery/migration path: a new backend can be populated by replaying from seq 0.

### `close() -> None`
Releases any held resources (file handles, connection pools). Called by the `Journal` context manager's `__exit__`.

## Additional Method: `last_entry()`

Not listed in the primary AST summary but present in the source:

```python
def last_entry(self) -> tuple[EventEntry, int] | None:
    """Return (last_entry, last_seq) or None if empty."""
```

Used by `Journal.append()` to compute the hash-chain link for the next event.

## Known Gaps

- The Protocol does not specify whether `append` must be thread-safe. The `SQLiteJournalBackend` uses WAL mode which provides some concurrency, but the contract itself is silent on this.
- `last_entry()` appears in the source but may not be included in the formal `__all__` of `backend.py`, creating a gap between what implementations must provide and what the Protocol declares.
