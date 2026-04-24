---
{
  "title": "Journal High-Level Class — Invariant Enforcement and Hash Chaining",
  "summary": "The `Journal` class wraps a `JournalBackend` to enforce append invariants (timezone-aware timestamps, monotonic ordering) and maintain an opportunistic SHA-256 hash chain linking each event to the previous one. `open_journal()` is the factory for production use.",
  "concepts": [
    "Journal",
    "JournalBackend",
    "hash chain",
    "SHA-256",
    "append invariants",
    "monotonic timestamps",
    "timezone-aware UTC",
    "open_journal",
    "EventEntry",
    "seq",
    "tamper-evident",
    "context manager",
    "SQLite journal"
  ],
  "categories": [
    "journal-engine",
    "architecture",
    "storage"
  ],
  "source_docs": [
    "1cc6bfcb022a5ec2"
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

## Overview

`journal.py` is the heart of the journal engine. The `Journal` class sits between callers and the storage backend, enforcing correctness guarantees that the backend cannot or should not know about, and computing hash-chain links that enable tamper detection.

## Invariants Enforced at This Layer

The `Journal` class (not the backend) owns these invariants:

| Invariant | What breaks if violated |
|-----------|------------------------|
| `entry.ts` must be timezone-aware UTC | Timestamp comparisons across time zones produce wrong ordering |
| `entry.ts >= prior event's ts` | Monotonic ordering breaks replay and time-range queries |
| `entry.scope` must be non-empty | Scope-based access control cannot function on unscoped events |
| `entry.actor.id` must be non-empty | Audit trail becomes unreliable |

The first two are checked explicitly in `Journal.append()`; the latter two are delegated to Pydantic model validation in `EventEntry`.

## Hash-Chain Design

Each event carries a `prev_hash` field that links it to the previous event:

```python
def _hash_link(prev: EventEntry, prev_seq: int) -> bytes:
    material = f"{prev.id}|{prev.ts.isoformat()}|{prev.action}|{prev_seq}".encode()
    return hashlib.sha256(material).digest()
```

The hash is computed over the previous event's `id`, `ts`, `action`, and `seq`. This creates a tamper-evident chain: modifying any past event changes its hash, which invalidates the link in the next event.

The hash linkage is **opportunistic**: if hashing fails (e.g., the previous event cannot be retrieved), the append still proceeds. This is noted in the source as a temporary design; a future slice will make signing and full hash-chain integrity mandatory.

Pre-signed events (from a future signing slice) can supply their own `prev_hash`, which `Journal.append()` will not overwrite.

## `append()` Return Value Change

As of feat/0.3.2-spike, `Journal.append()` returns the committed `EventEntry` with its assigned `seq` populated:

```python
committed: EventEntry = journal.append(entry)
print(committed.seq)  # available immediately, no second query needed
```

Before this change, callers had to call `backend.query(...)` or `MAX(seq)` after appending to discover the assigned sequence number. This was a race condition: between the append and the seq read, another writer could insert an event and the caller would read the wrong seq.

## `open_journal()` Factory

```python
def open_journal(path: str | Path) -> Journal:
    """Open (and migrate on first write) a SQLite-backed journal at path."""
```

This is the only intended way to get a `Journal` instance in production. It:
1. Creates a `SQLiteJournalBackend` at the given path
2. Wraps it in a `Journal`
3. Triggers schema migration on first write (lazy migration avoids blocking read-only opens)

## Context Manager Protocol

`Journal` implements `__enter__` / `__exit__`, so it can be used with `with`:

```python
with open_journal("/path/to/journal.db") as j:
    j.append(entry)
```

`__exit__` calls `close()`, which calls `backend.close()`.

## Known Gaps

- Hash-chain verification (`replay_from` with integrity checking) is not yet implemented. The chain is written but nothing verifies it on read.
- The hash function (`sha256` over a string) is described in source as "deliberately simple" — a placeholder until a proper signing scheme (ed25519 or similar) is introduced.
- `open_journal()` creates `SQLiteJournalBackend` directly, hardcoding the backend. There is no way to inject a different backend via `open_journal()` without modifying source.
