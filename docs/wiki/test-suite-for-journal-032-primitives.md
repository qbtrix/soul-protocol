---
{
  "title": "Test Suite for Journal 0.3.2 Primitives",
  "summary": "Smoke, end-to-end, and real-world simulation tests for the primitives introduced in soul-protocol v0.3.2, specifically the append-returns-committed-entry contract and action prefix querying. Tests mirror realistic consumer patterns from the PocketPaw widget store.",
  "concepts": [
    "Journal",
    "seq",
    "append returns entry",
    "action prefix",
    "client sync",
    "event sourcing",
    "0.3.2 primitives",
    "EventEntry",
    "widget store",
    "correlated events"
  ],
  "categories": [
    "testing",
    "journal-engine",
    "event sourcing",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "b4bbf67a11c0ea31"
  ],
  "backlinks": null,
  "word_count": 419,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_0_3_2_primitives.py` tests the new capabilities added to the `Journal` class in v0.3.2: (1) `append()` now returns the committed `EventEntry` with a populated `seq` field, and (2) `query(action_prefix=...)` lets consumers filter events by action family. These two primitives unlock efficient client synchronization patterns that were previously impossible.

## The Seq-Return Contract (Primitive #1)

Before 0.3.2, `journal.append(entry)` returned `None`. Callers that needed to know the assigned sequence number had to query back — a race-prone extra round-trip. Now `append()` returns the committed entry with `seq` set.

### Why This Matters

The PocketPaw widget store (`ee/widget/store.py`) needs to "ack with seq": after writing an event, it records the highest sequence number it has processed so it can resume from the right point on reconnect. Without the return value, this required a follow-up `query()` call.

```python
def test_e2e_seq_drives_client_sync(journal: Journal) -> None:
    last_seen = -1
    for i in range(10):
        committed = journal.append(_entry("widget.interaction.recorded", {"i": i}))
        assert committed.seq > last_seen
        last_seen = committed.seq
    # After 10 gap-free events starting at 0:
    assert last_seen == 9
```

### Persistence Across Reopen

`test_e2e_seq_survives_reopen` verifies that `seq` is not an in-memory counter that resets when the journal is closed and reopened — it must persist in the SQLite database and continue monotonically from where it left off.

### Backward Compatibility

`test_smoke_append_none_caller_still_works` confirms that code that discards the return value (i.e., `journal.append(entry)` without assignment) still works. This is important for pre-0.3.2 callers that were never expecting a return value.

## Real-World Simulations

Two tests simulate realistic consumer patterns:
- **`test_realworld_widget_store_ack_with_seq`** — replays the widget store's client-sync pattern directly, verifying that the journal's append contract matches what the consumer actually needs.
- **`test_realworld_correlated_flow_uses_seq_for_ordering`** — shows that in a correlated multi-event flow, `seq` provides stable ordering that wall-clock timestamps cannot guarantee (two events at the same millisecond have different `seq` values).

## Action Prefix Querying (Primitive #2)

`query(action_prefix="widget.interaction")` returns all events whose `action` string starts with the given prefix, enabling "event family" queries:

```python
def test_e2e_prefix_filters_across_mixed_corpus(journal) -> None:
    # Corpus: "memory.remembered", "widget.interaction.recorded",
    #         "widget.interaction.dismissed", "session.started"
    results = journal.query(action_prefix="widget.interaction")
    assert len(results) == 2
```

`test_e2e_prefix_combines_with_other_filters` confirms that `action_prefix` composes with `actor` and `since` filters — it is not a standalone mode but a first-class filter dimension.

## Known Gaps

The file header explicitly marks three primitives as **TODO for next slice**:
- Primitive #2: `Journal.query(action_prefix=...)` — partially covered here, full spec TBD
- Primitive #3: Async `SourceAdapter.aquery`
- Primitive #4: `DataRef` Pydantic discrimination
- Primitive #5: `RetrievalRequest.point_in_time`

These represent planned work from the 0.3.2 feature spike that has not yet landed.
