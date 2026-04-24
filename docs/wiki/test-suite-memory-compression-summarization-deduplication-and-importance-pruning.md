---
{
  "title": "Test Suite: Memory Compression -- Summarization, Deduplication, and Importance Pruning",
  "summary": "Tests for `MemoryCompressor`, which reduces the size of a soul's long-term memory store through four strategies: text summarization, near-duplicate removal, importance-based pruning, and export splitting. Covers edge cases like empty inputs, threshold tuning, and the rule that high-importance memories are never pruned regardless of age.",
  "concepts": [
    "MemoryCompressor",
    "memory compression",
    "summarization",
    "deduplication",
    "importance pruning",
    "export splitting",
    "MemoryEntry",
    "MemoryType",
    "near-duplicate detection",
    "similarity threshold",
    "importance threshold",
    "memory retention",
    "soul export"
  ],
  "categories": [
    "testing",
    "memory management",
    "compression",
    "soul lifecycle",
    "test"
  ],
  "source_docs": [
    "828f1a630c2cad30"
  ],
  "backlinks": null,
  "word_count": 391,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_compression.py` validates `MemoryCompressor`, the component responsible for keeping a soul's memory store manageable over months of use. Unlike context compaction (which manages the active conversation window), memory compression operates on the long-term memory tiers -- semantic, episodic, and procedural entries accumulated across sessions.

## Test Fixture

```python
@pytest.fixture
def compressor() -> MemoryCompressor:
    return MemoryCompressor()
```

A single shared fixture provides a default-configured compressor. The `_mem()` helper creates test `MemoryEntry` objects with configurable content, importance (1-10), memory type, and age:

```python
def _mem(content, importance=5, type=MemoryType.SEMANTIC, age_days=0) -> MemoryEntry:
    return MemoryEntry(
        type=type,
        content=content,
        importance=importance,
        created_at=datetime.now() - timedelta(days=age_days),
    )
```

## Summarization

`TestSummarize` covers the text-based summary generation:

- **Empty input**: empty string returned, no crash
- **Deduplication in summary**: near-duplicate memories appear only once
- **Max tokens respected**: summary is truncated to fit within a token limit
- **Type grouping**: memories are grouped by type in the summary
- **Higher importance first**: within each group, higher-importance memories appear earlier

The importance ordering ensures that if a summary must be truncated, the most significant memories survive.

## Deduplication

`TestDeduplicate` validates the near-duplicate removal algorithm:

```python
def test_removes_near_duplicates(compressor):
    mems = [
        _mem("User prefers dark mode"),
        _mem("User likes dark mode"),  # near-duplicate
        _mem("User enjoys running"),    # distinct
    ]
    result = compressor.deduplicate(mems)
    assert len(result) == 2
```

Near-duplicate detection uses string similarity (not exact match) to catch rephrased versions of the same fact. The default threshold is tunable via `test_custom_threshold`.

## Importance-Based Pruning

`TestPruneByImportance` is the most policy-critical class:

```python
class TestPruneByImportance:
    """Old memories with importance >= 7 are always kept."""

    def test_keeps_high_importance(compressor):
        # importance=9, age=365 days -> kept

    def test_keeps_old_high_importance(compressor):
        # importance=7, age=1000 days -> still kept (age does not override importance)

    def test_prunes_old_medium_importance(compressor):
        # importance=4, age=365 days -> removed
```

The `importance >= 7` permanent retention rule is a core product decision: users should never lose high-importance memories (preferences, key facts, significant events) to routine maintenance.

## Export Compression Splitting

`TestCompressForExport` covers the export path where a soul's memory must fit within a size limit:

- **Under limit**: all memories inline, no splitting
- **Over limit**: high-importance memories stay inline, low-importance overflow to an external reference
- **Empty input**: returns empty result without error

This is used when exporting souls to the `.soul` ZIP format or transferring to Arweave/IPFS.

## Known Gaps

No TODOs flagged. Suite was created 2026-03-06 alongside the compression module.