---
{
  "title": "Test Suite for the Archival Memory Store",
  "summary": "This test suite validates `ArchivalMemoryStore` — the fifth memory tier that stores compressed conversation summaries as `ConversationArchive` objects. It covers creation, keyword search with overlap-based ranking, date-range overlap queries, count tracking, and get-by-id retrieval.",
  "concepts": [
    "ArchivalMemoryStore",
    "ConversationArchive",
    "memory compression",
    "archival tier",
    "keyword search",
    "date-range queries",
    "token overlap ranking",
    "memory tiers"
  ],
  "categories": [
    "testing",
    "memory",
    "archival",
    "test"
  ],
  "source_docs": [
    "c52a7f7f334290bc"
  ],
  "backlinks": null,
  "word_count": 443,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`ArchivalMemoryStore` is the long-term, compressed memory tier. Rather than storing individual episodic entries indefinitely, the system periodically sweeps old episodics and compresses them into `ConversationArchive` objects. The store holds these archives and provides search and date-range access.

The test suite was created on 2026-03-06 to lock the store's contract before the archival pipeline was wired into `MemoryManager`.

## Test Structure

### `store` Fixture

A bare `ArchivalMemoryStore()` is constructed fresh for each test. This keeps tests independent — no shared state between test methods.

### Helper: `_make_archive()`

```python
_make_archive(
    id="arc-001",
    summary="A conversation about Python",
    key_moments=["User mentioned Rust"],
    start_offset_hours=0,
    duration_hours=1,
)
```

The helper uses a fixed base timestamp (`datetime(2026, 3, 1, 10, 0, 0)`) so date-range tests are deterministic. `start_offset_hours` lets tests place multiple archives at controlled positions along a timeline.

## Creation Tests (`TestArchiveCreation`)

- `archive_conversation()` returns the archive's `id` string
- `count()` increments correctly after each store call
- `all_archives()` returns copies of stored archives (not mutable references)

## Search Tests (`TestArchiveSearch`)

Search matches against both `summary` and `key_moments` fields:

```python
# Summary match
store.search_archives("Python")   # matches arc-001 with "Discussed Python..."

# Key moment match
store.search_archives("Rust")     # matches arc with key_moment "User mentioned...Rust"
```

Ranking is by token overlap — an archive with `"Python web frameworks and Python testing tools"` ranks above `"Python is great"` for query `"Python web"` because it contains more matching tokens. This prevents relevant archives from being buried by recency or insertion order.

The `limit` parameter is respected, and an empty query returns an empty list (rather than returning all archives, which could be expensive).

## Date-Range Tests (`TestDateRangeQueries`)

`get_by_date_range(start, end)` uses overlap semantics: an archive matches if its time window intersects the query window at any point. This is the correct semantic for conversational archives, which are durations rather than point-in-time events.

```
Archive spans hours 0-2.
Query window: hours 1-3.
Result: match (overlap at hour 1-2).
```

Results are sorted by `start_time` ascending, giving callers a chronological view regardless of insertion order.

## Get-by-ID Tests (`TestGetById`)

- Existing ID → returns the archive
- Non-existent ID → returns `None` (not an exception)

The `None` return on miss is important for the archival pipeline: the pipeline needs to check whether a specific archive exists before deciding whether to create a new one, and an exception-based API would require wrapping every lookup in a try/except.

## Known Gaps

- Search ranking is based on token overlap count; there are no tests for exact tie-breaking behavior when two archives have equal overlap scores.
- There are no tests for archives that span very long durations (e.g., multi-day) and whether date-range queries handle them correctly at timezone boundaries.