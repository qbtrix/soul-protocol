---
{
  "title": "Test Suite: Context Store -- SQLite-Backed Conversation History",
  "summary": "Tests for Soul Protocol's SQLite-backed context store, which persists conversation messages and compaction nodes with sequential ordering, full-text grep, date-range filtering, and cross-reconnect durability. Covers both in-memory (test) and file-backed (persistence) store configurations.",
  "concepts": [
    "ContextStore",
    "SQLite",
    "seq number",
    "message append",
    "grep",
    "full-text search",
    "ContextNode",
    "covered_seq_ranges",
    "compaction stats",
    "persistence",
    "reconnect durability",
    "in-memory store",
    "get_nodes_by_level",
    "date range"
  ],
  "categories": [
    "testing",
    "context management",
    "SQLite persistence",
    "context store",
    "test"
  ],
  "source_docs": [
    "13147006f1135583"
  ],
  "backlinks": null,
  "word_count": 430,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_context_store.py` validates the persistence layer for Soul Protocol's context window -- the append-only store of conversation messages and compaction artifacts. The store is implemented on SQLite and must handle sequential ordering, full-text search, and survival across process restarts.

## Test Fixtures

```python
@pytest.fixture
async def store():
    """In-memory SQLite store, initialized and ready."""

@pytest.fixture
async def persisted_store(tmp_path):
    """File-backed SQLite store for persistence tests."""
```

The two fixtures serve different purposes: `store` is used for all behavioral tests (fast, no cleanup needed), while `persisted_store` is reserved for tests that require data to survive a simulated process restart.

## Message Append and Sequential Assignment

```python
async def test_append_assigns_seq(store):
    msg = await store.append(ContextMessage(content="hello"))
    assert msg.seq == 1

async def test_sequential_seq_numbers(store):
    msgs = [await store.append(ContextMessage(content=f"msg{i}")) for i in range(5)]
    assert [m.seq for m in msgs] == [1, 2, 3, 4, 5]
```

Sequential numbers are critical for compaction: the `seq_start`/`seq_end` range in `ContextNode` uses them to identify which messages a summary covers. Gaps or duplicates in seq numbers would corrupt compaction metadata.

## Message Retrieval

`TestMessageRetrieval` covers all query patterns:

- `get_all_messages()` returns all messages ordered by seq
- `get_messages(seq_start, seq_end)` filters by range
- `get_messages(limit=N)` returns the most recent N messages
- `count_messages()` and `total_tokens()` return correct aggregates
- Empty store returns 0 for both counts

## Grep (Full-Text Search)

`TestGrep` validates the `grep()` method:

```python
async def test_regex_pattern(store):
    await store.append(ContextMessage(content="user: I love Python"))
    results = await store.grep(r"I love \w+")
    assert len(results) == 1

async def test_ordered_by_recency(store):
    # Most recent matches first
```

Case-insensitive search is tested explicitly because LLM output is inconsistently cased.

## Node Operations (Compaction Artifacts)

`TestNodeOperations` validates the compaction node subsystem:

- `insert_node` / `get_node` round-trip by node ID
- `get_nodes_by_level` filters by `CompactionLevel`
- `covered_seq_ranges()` returns seq ranges covered by non-verbatim nodes
- Verbatim nodes are NOT included in covered ranges
- `compaction_stats()` returns counts per level

The covered-ranges exclusion of verbatim nodes prevents the compaction loop from treating uncompacted messages as already-compacted.

## Persistence Tests

```python
async def test_data_survives_reconnect(persisted_store):
    await persisted_store.append(ContextMessage(content="survived"))
    await persisted_store.close()
    store2 = ContextStore(persisted_store.path)
    await store2.initialize()
    msgs = await store2.get_all_messages()
    assert msgs[0].content == "survived"

async def test_seq_continues_after_reconnect(persisted_store):
    # seq numbers do not reset to 1 after reconnect
```

The seq-continuation test prevents a regression where seq numbers restart after reconnect, which would corrupt existing compaction node ranges.

## Error Handling

```python
async def test_uninitialized_store_raises():
    store = ContextStore(":memory:")
    with pytest.raises(RuntimeError):
        await store.get_all_messages()  # used before initialize()
```

This prevents silent failures where an uninitialized store returns empty results instead of raising.

## Known Gaps

No TODOs flagged. Introduced at v0.3.0 alongside the context store implementation.