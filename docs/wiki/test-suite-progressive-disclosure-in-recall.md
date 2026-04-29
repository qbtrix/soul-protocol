---
{
  "title": "Test Suite: Progressive Disclosure in Recall",
  "summary": "Tests for RecallEngine's progressive recall mode, which returns a primary set of full-content memories plus an overflow set of abstract-only summaries, allowing callers to receive more context without exceeding token budgets.",
  "concepts": [
    "progressive recall",
    "RecallEngine",
    "overflow entries",
    "abstract",
    "is_summarized",
    "context window",
    "progressive disclosure",
    "memory compression",
    "primary entries",
    "token budget"
  ],
  "categories": [
    "memory",
    "testing",
    "recall",
    "progressive-disclosure",
    "test"
  ],
  "source_docs": [
    "72857a2e2e2f5565"
  ],
  "backlinks": null,
  "word_count": 471,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Progressive Disclosure in Recall

`test_progressive_recall.py` (created 2026-03-29) validates `RecallEngine`'s `progressive=True` mode — a feature that expands context window utilization by returning two tiers of results: primary entries with full content, and overflow entries with content replaced by their pre-generated abstract.

### Why Progressive Recall?

A typical recall call returns `limit=N` full entries. But for agents working within a fixed context window, more shallow references are often more useful than fewer deep ones. Progressive recall doubles the information density by returning `limit` full entries plus up to `limit` additional entries in compressed form (abstract only).

### Test: Default Behavior Unchanged

```python
async def test_progressive_false_returns_limit(populated_engine):
    results = await populated_engine.recall("alpha", limit=3, progressive=False)
    assert len(results) == 3
```

`progressive=False` (the default) must return exactly `limit` entries. This test guards backwards compatibility — existing callers that don't pass `progressive=True` must see no change.

### Test: Progressive Mode Returns More

```python
async def test_progressive_true_returns_more_than_limit(populated_engine):
    results = await populated_engine.recall("alpha", limit=3, progressive=True)
    assert len(results) > 3  # primary (3) + overflow (up to 3)
```

With 5 entries in the engine and `limit=3`, progressive mode returns 3 primary + up to 2 additional overflow entries, for a total above the normal limit.

### Test: Overflow Uses Abstract

```python
async def test_overflow_uses_abstract(populated_engine):
    results = await populated_engine.recall("alpha", limit=3, progressive=True)
    overflow = results[3:]  # beyond the primary set
    for entry in overflow:
        assert entry.content == entry.abstract  # full content replaced by abstract
```

Overflow entries have their `content` field replaced with the `abstract` (the pre-computed first sentence). This keeps the overflow entries lightweight while still providing enough context to identify the memory.

### Test: Missing Abstract Falls Back to Content

```python
async def test_overflow_no_abstract_keeps_content(populated_engine):
    # The last fixture entry has abstract=None
    # Its overflow entry should keep original content
```

Not all memories have abstracts (older entries or entries with content under 400 characters skip abstract generation). When `abstract` is None, the overflow entry retains its full content. This graceful fallback prevents information loss for entries without pre-generated summaries.

### Test: Primary Entries Not Marked Summarized

```python
async def test_is_summarized_marker(populated_engine):
    results = await populated_engine.recall("alpha", limit=3, progressive=True)
    for entry in results[:3]:  # primary set
        assert not entry.is_summarized
```

The `is_summarized` flag distinguishes overflow entries from primary entries. Primary entries must not be marked as summarized regardless of progressive mode — only the overflow tier carries this marker.

### Fixture Setup

```python
@pytest.fixture
async def populated_engine(recall_engine):
    for i in range(5):
        entry = _make_entry(
            content=f"Topic alpha fact number {i}",
            importance=8 - i,
            abstract=f"Alpha fact {i}" if i < 4 else None,
        )
        await recall_engine._semantic.add(entry)
    return recall_engine
```

Five entries with decreasing importance and no abstract on the last one — specifically designed to exercise the abstract fallback.

### Known Gaps

No test verifies behavior when `limit > total_entries` in progressive mode. No test covers the interaction between progressive recall and `min_importance` filtering.
