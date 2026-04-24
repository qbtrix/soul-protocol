---
{
  "title": "Test Suite for Archival Memory Integration: Compression Pipeline and Persistence",
  "summary": "This integration test suite validates the full archival pipeline in `MemoryManager`: how old episodic entries are compressed into `ConversationArchive` objects, how high-importance entries become key moments, how archived entries are excluded from recall, and how archives survive serialization round-trips through `to_dict()` / `from_dict()`.",
  "concepts": [
    "archive_old_memories",
    "episodic compression",
    "key moments",
    "archival pipeline",
    "importance threshold",
    "recall filtering",
    "to_dict serialization",
    "from_dict restoration",
    "MemoryManager",
    "idempotency"
  ],
  "categories": [
    "testing",
    "memory",
    "archival",
    "test"
  ],
  "source_docs": [
    "0ed7790bd5b7795d"
  ],
  "backlinks": null,
  "word_count": 498,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The archival pipeline was introduced as Feature F2. This test suite validates the wiring between `MemoryManager`, `ArchivalMemoryStore`, and the episodic memory layer — it tests behavior that only emerges when components work together, not individual store operations.

Created 2026-03-29.

## Fixtures and Helpers

```python
@pytest.fixture
def manager() -> MemoryManager:
    return MemoryManager(core=CoreMemory(), settings=MemorySettings())

def _make_old_entry(content, hours_ago, importance=5) -> MemoryEntry:
    # Returns an EPISODIC entry backdated by hours_ago
```

The `_make_old_entry()` helper bypasses the normal `observe()` path and injects entries directly into `manager._episodic._memories`. This is necessary because backdated timestamps cannot be set through the public API — `observe()` always uses `datetime.now()`. Direct injection lets tests simulate the passage of time without actual sleeps.

## Compression Tests (`TestArchiveOldMemories`)

### Minimum Entry Threshold

```python
# 1 old entry → archive is None (skipped)
archive = await manager.archive_old_memories(max_age_hours=48.0)
assert archive is None
```

The pipeline requires at least 3 old entries before creating an archive. This prevents trivially small archives from accumulating — a single old memory is better left in the episodic tier where it can still be individually recalled.

### Idempotency Guard

```python
await manager.archive_old_memories()  # archives 4 entries, marks archived=True
await manager.archive_old_memories()  # sees 0 unarchived → returns None
assert manager.archival.count() == 1  # only one archive was created
```

The `archived` flag on each `MemoryEntry` prevents double-archiving. Without this guard, a second consolidation call would create a duplicate archive from the same entries.

### Recency Filtering

Entries newer than `max_age_hours` are never archived. The test verifies that mixing 2 old entries and 3 recent entries still yields `None` (2 < 3 minimum threshold), confirming that recent entries are correctly excluded from the age filter before the threshold check.

### Key Moments from High-Importance Entries

```python
_make_old_entry("Critical discovery. Big impact.", hours_ago=72, importance=9)
# → archive.key_moments == ["Critical discovery. Big impact."]
```

Entries with `importance >= 7` are extracted as key moments in the resulting archive. This preserves salient information in a queryable form even after the raw episodic entry is no longer directly recalled.

## Recall Filtering (`TestArchivalRecallFiltering`)

```python
pre_results = await manager.recall("alpha")   # 4 results
await manager.archive_old_memories()
post_results = await manager.recall("alpha")  # 0 results
```

Once entries are archived (`archived=True`), they must not appear in normal `recall()` results. This ensures that the episodic tier stays bounded — without this filter, the episodic store would grow forever even after archival.

## Serialization Persistence (`TestArchivalPersistence`)

```python
data = manager.to_dict()
assert "archives" in data
assert len(data["archives"]) == 1

restored = MemoryManager.from_dict(data, settings=MemorySettings())
assert restored.archival.count() == 1
```

Archives must survive `to_dict()` / `from_dict()` to persist across soul export/awaken cycles. Without this, a soul would lose all its archived conversation history every time it was exported and re-loaded.

## Known Gaps

- The archival pipeline produces a summary from old entries but the tests only check that the summary contains a snippet of the content. The exact summarization algorithm is not locked by these tests.
- There are no tests for what happens when archival is triggered mid-recall (concurrent access scenario).