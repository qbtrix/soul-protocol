---
{
  "title": "Test Suite for VectorSearchStrategy",
  "summary": "Tests the VectorSearchStrategy class, which wraps an embedder to perform similarity-based memory search with configurable threshold filtering and pre-built index support. Covers both the deterministic HashEmbedder path and the semantic TFIDFEmbedder path.",
  "concepts": [
    "VectorSearchStrategy",
    "memory search",
    "threshold filtering",
    "pre-built index",
    "HashEmbedder",
    "TFIDFEmbedder",
    "MemoryEntry",
    "cosine similarity",
    "recall ranking",
    "embedder-agnostic"
  ],
  "categories": [
    "testing",
    "embeddings",
    "memory retrieval",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "7929dc7567758d85"
  ],
  "backlinks": null,
  "word_count": 486,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_vector_strategy.py` validates `VectorSearchStrategy` — the bridge between embedders and the memory retrieval pipeline. The strategy is responsible for converting a query string and a list of `MemoryEntry` objects into a ranked, threshold-filtered list of relevant memories. This test file sits at the integration boundary: it tests how the embedder, similarity function, and memory types cooperate, not just individual functions.

## Design Intent

`VectorSearchStrategy` is intentionally embedder-agnostic. It accepts any object with an `embed(text) -> list[float]` interface. This lets the system swap between:
- **`HashEmbedder`** — fast, deterministic, non-semantic. Used for tests that need predictable vector output.
- **`TFIDFEmbedder`** — slower, corpus-fitted, semantically meaningful. Used in production recall.

The tests cover both paths explicitly.

## Test Groups

### `TestVectorSearchStrategyBasics`
Establishes the constructor contract:
- Default `threshold=0.3` — memories with cosine similarity below this are excluded from results.
- The threshold is mutable via a setter, which allows the recall layer to tune precision vs. recall at runtime.
- An empty candidate list must return `[]` without attempting any embedding computation.

### `TestVectorSearchStrategyWithHashEmbedder`
Uses `HashEmbedder` (deterministic, threshold=0.0) to validate mechanics without semantic sensitivity:
- At least some results are returned for any non-empty candidate list.
- The `limit` parameter caps results at the requested count.

```python
def test_limit_respected(self) -> None:
    entries = [_make_entry(f"entry number {i}") for i in range(20)]
    results = strategy.search("entry", entries, limit=5)
    assert len(results) <= 5
```

### `TestVectorSearchStrategyWithTFIDF`
The semantic path tests use a `strategy_with_corpus` fixture that pre-fits the TFIDFEmbedder on a training corpus:
- **Similar topics** should rank above the threshold; **different topics** should fall below it.
- `test_threshold_filters_results` verifies that raising the threshold actually removes results, preventing the silent vacuous-assertion bug that was previously present (noted in the file header).

### `TestVectorSearchStrategyIndexing`
For large memory sets, the strategy supports a pre-built index to avoid re-embedding every candidate on each query:
- **`index(entries)`** pre-embeds all candidates and stores their vectors.
- **`search_indexed(query)`** searches only the pre-built index.
- **`clear_index()`** discards the pre-built vectors (used when memory contents change).
- Searching an empty index returns `[]`.

This pattern mirrors common vector database designs: embed once, query many times.

### `TestVectorSearchStrategyWithMemoryEntries`
Confirms that the strategy correctly reads the `.content` attribute from `MemoryEntry` objects, and also handles plain strings as candidates for simpler use cases.

## Helper: `_make_entry`

```python
def _make_entry(content: str, importance: int = 5) -> MemoryEntry:
    return MemoryEntry(
        type=MemoryType.SEMANTIC,
        content=content,
        importance=importance,
        created_at=datetime.now(),
    )
```

Centralizes fixture creation to avoid repetitive boilerplate and to ensure all test entries have valid Pydantic fields.

## Data Flow

```
query string
    → strategy.search(query, candidates)
        → embedder.embed(query)        # query vector
        → for each candidate:
            → embedder.embed(content)  # candidate vector
            → cosine_similarity(q, c)  # score
            → filter by threshold
        → sort by score descending
        → return top-N
```

## Known Gaps

The file header notes a previous vacuous assertion bug in `test_threshold_filters_results` that was fixed. No remaining TODOs. Thread-safety of the index (concurrent writes + reads) is not tested.
