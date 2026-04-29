---
{
  "title": "Test Suite for JournalBackedMemoryStore: Unit, Smoke, E2E, and Real-World Scenarios",
  "summary": "This comprehensive test suite for `JournalBackedMemoryStore` follows a four-tier discipline — unit, smoke, E2E, and real-world simulations — covering every public method and the failure modes that motivated the journal architecture. Special attention is given to disaster recovery (the April 2026 cleanup incident), GDPR-compliant tombstone deletion, idempotent rebuild, and latency budgets.",
  "concepts": [
    "JournalBackedMemoryStore",
    "append-only journal",
    "rebuild",
    "audit trail",
    "GDPR tombstone",
    "memory promotion",
    "BM25 search",
    "SQLite FTS5",
    "cleanup incident",
    "session persistence"
  ],
  "categories": [
    "testing",
    "memory-system",
    "spike",
    "disaster-recovery",
    "test"
  ],
  "source_docs": [
    "e0e9a164ae11b38e"
  ],
  "backlinks": null,
  "word_count": 574,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`JournalBackedMemoryStore` is the spike replacement for `DictMemoryStore`. Unlike the dict store, it writes every mutation to an append-only SQLite journal before updating projection tables. This means the store can always rebuild its queryable state by replaying the journal — the projection is disposable, the journal is truth.

The test file is organized into four explicit layers matching the captain's testing discipline.

## Unit Tests — Method Isolation

### Store and Recall

```python
def test_unit_store_returns_stable_id(store):
    mem_id = store.store("episodic", _make_entry("hello"))
    assert isinstance(mem_id, str) and len(mem_id) > 0
```

Stable IDs are critical: the same memory ID must be usable across rebuilds to associate audit trail entries.

### BM25 Search Ranking

```python
results = store.search("python programming", limit=5)
assert "python" in results[0].content.lower()
assert "programming" in results[0].content.lower()
```

The top result must contain both query terms — testing that FTS5 relevance ranking works, not just token presence.

### Empty Query Guard

```python
assert store.search("") == []
assert store.search("   ") == []
```

Empty queries must return empty, not crash or return all memories. This prevents accidental full-corpus dumps when a UI sends a blank search.

### Promotion Between Tiers

`promote(memory_id, new_tier)` moves a memory from its current tier to a different one as a single atomic operation. The unit test confirms the memory disappears from `episodic` and appears in `semantic` with the same content:

```python
assert store.promote(mem_id, "semantic") is True
assert store.recall("episodic") == []
assert len(store.recall("semantic")) == 1
```

Same-tier promotion returns `False` (a no-op, not an error).

### Audit Trail

Every store/promote/delete emits an event to the journal. The audit trail test confirms the complete event sequence:

```python
actions = [e.action for e in store.audit_trail(mem_id)]
assert actions == ["memory.remembered", "memory.graduated", "memory.forgotten"]
```

## Smoke Tests — Basic Sanity

A delete must make the memory invisible to search immediately:

```python
store.delete(mem_id)
assert store.search("temporary") == []
```

## E2E Tests — Full Flow

### Rebuild from Journal

The defining property of the journal architecture:

```python
store._db.execute("DROP TABLE memory_tier")  # simulate data loss
count = store.rebuild()
assert {m.id for m in store.recall("episodic")} == pre_rebuild_episodic
```

The rebuild replays all journal events in order. The test verifies that the full memory set is restored identically, not approximately.

### Session Persistence

Close and reopen the store. The new session sees the previous session's writes:

```python
store1._journal.close(); store1._db.close()
store2 = open_memory_store(base, actor=actor)
results = store2.recall("semantic", limit=10)
assert results[0].id == mem_id
```

## Real-World Simulations

### Cleanup Incident Recovery

Simulates the April 2026 incident: projection tables are deleted, then `rebuild()` is called:

```python
store._db.execute("DELETE FROM memory_tier")
store._db.execute("DELETE FROM fts_memories")
events_replayed = store.rebuild()
assert post_recovery_count == pre_incident_count
```

### GDPR Tombstone

Deleting a memory must remove its content from projections but leave a tombstone in the audit journal:

```python
tombstone_payload = trail[1].payload
assert "memory_id" in tombstone_payload
assert "content" not in tombstone_payload  # no PII in tombstone
```

### Idempotent Rebuild

Calling `rebuild()` twice must produce the same state both times — no accidental duplication on repeated upgrade dances.

### Latency Budgets

- 100 writes: under 2 seconds on a cold store.
- 50 recalls on 500 memories: under 1 second.
- 6 BM25 searches on 500 memories: under 1 second.

## Known Gaps

- The `MemoryVisibility` import is present in the file but no tests exercise it — visibility-scoped recall is not yet tested.
- Concurrent write safety (two actors writing simultaneously) is not tested.
- The audit trail ordering test assumes events arrive in insertion order, which may not hold under concurrent writes.