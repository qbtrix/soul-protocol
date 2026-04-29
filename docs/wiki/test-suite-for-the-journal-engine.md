---
{
  "title": "Test Suite for the Journal Engine",
  "summary": "Comprehensive test suite for the SQLite-backed journal engine — the event-sourcing backbone of soul-protocol. Covers append/query mechanics, every filter dimension, timezone enforcement, scope wildcards, monotonic timestamps, seq assignment, concurrent WAL writes, and schema migration from zero.",
  "concepts": [
    "Journal",
    "append",
    "query",
    "SQLite",
    "WAL",
    "seq",
    "scope wildcard",
    "timezone enforcement",
    "schema migration",
    "EventEntry",
    "DataRef",
    "monotonic timestamps",
    "concurrent writes"
  ],
  "categories": [
    "testing",
    "journal-engine",
    "event sourcing",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "b4a11958cceb7c61"
  ],
  "backlinks": null,
  "word_count": 535,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_journal.py` is the primary test suite for `soul_protocol.engine.journal`, the append-only event log that records every significant state transition in a soul's life. The journal is the source of truth for replay, projection, and audit — bugs here could cause data loss, silent corruption, or replay divergence. The suite is correspondingly thorough.

## Core Contract: Append/Query Round-Trip

```python
def test_append_query_roundtrip(journal: Journal) -> None:
    entry = _make_entry()
    journal.append(entry)
    results = journal.query()
    assert results[0].id == entry.id
    assert results[0].payload == entry.payload
```

This is the baseline: every field written must be faithfully recovered. The `payload` assertion is especially important — the journal stores both inline dicts and `DataRef` pointers, and neither must lose data.

## Filter Dimensions

The suite tests every `query()` filter individually and in combination:
- **`action`** — exact action string match
- **`actor`** — match by actor identity
- **`correlation_id`** — retrieve all events in a correlated flow
- **Time window** (`since` / `until`) — returns only events within the window
- **`scope` wildcard** — `org:*` matches any sub-scope under `org:`

`test_query_combined_filters` verifies that multiple filters AND together correctly, which is the common production case (e.g., "all memory events for this actor in the last hour").

## Timezone Enforcement

The journal rejects naive (timezone-unaware) datetimes on both append and query:

```python
def test_append_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        journal.append(_make_entry(ts=datetime(2026, 1, 1)))  # no tzinfo

def test_query_rejects_naive_since(journal) -> None:
    with pytest.raises(ValueError):
        journal.query(since=datetime(2026, 1, 1))
```

This prevents the classic "timestamps look right but are actually UTC-unaware" bug that causes time-window queries to silently return wrong results in environments with non-UTC system clocks.

## Sequence Numbers

- `test_seq_auto_assigned_gap_free` — seq must be 0, 1, 2, … with no gaps, even across separate database connections.
- `test_append_first_seq_is_zero` — the first event always gets seq=0.
- `test_append_seq_is_monotonic` — each append increases seq by exactly 1.
- `test_append_returns_committed_entry_with_seq` — the return value of `append()` has `seq` populated.

## Monotonic Timestamps

`test_monotonic_ts_enforced` verifies that the journal rejects an event whose `ts` is earlier than the most recently appended event. Out-of-order timestamps would break time-window queries and replay ordering.

## Concurrent Writers (WAL Mode)

```python
def test_concurrent_writers_wal_no_data_loss(tmp_path) -> None:
    # Two threads each append 50 events. Total must be 100.
    ...
def test_concurrent_writers_real_clocks_preserve_ts_monotonicity(tmp_path) -> None:
    # Two threads using datetime.now(UTC) independently — no ts collisions.
```

SQLite's WAL (Write-Ahead Log) mode allows concurrent readers and a single writer. These tests confirm that under parallel load, no events are lost and the monotonicity invariant is preserved across threads.

## Schema Migration

`test_schema_migrates_from_zero_on_first_write` opens a brand-new SQLite file and appends one event. The journal must auto-create the schema (`v1`) without requiring any manual migration step. This is important for fresh deployments and integration tests that spin up temporary journals.

## DataRef Payload

`test_dataref_payload_roundtrip` confirms that when a payload is a `DataRef` (a pointer to external storage rather than inline data), the reference is preserved exactly through serialize/deserialize. This avoids silent data inlining that would invalidate the external reference.

## Known Gaps

No TODO markers. The concurrent-writer test notes that it tests WAL mode but does not test the non-WAL fallback. The `_scope_matches` internal function is tested via `test_scope_wildcard_matcher_unit` as a unit test, which is a good sign — internal helpers are not left untested.
