---
{
  "title": "VectorSearchStrategy: Embedding-Based Semantic Memory Search",
  "summary": "The `VectorSearchStrategy` wraps any `EmbeddingProvider` to implement semantic similarity search over memory entries. It maintains a pre-built index for performance, falls back to on-the-fly embedding for un-indexed candidates, and uses cosine similarity with a configurable threshold to rank and filter results.",
  "concepts": [
    "VectorSearchStrategy",
    "semantic search",
    "cosine similarity",
    "pre-built index",
    "EmbeddingProvider",
    "memory search",
    "threshold filtering",
    "embed_batch",
    "on-the-fly embedding",
    "MemoryEntry"
  ],
  "categories": [
    "embeddings",
    "memory search",
    "semantic retrieval"
  ],
  "source_docs": [
    "3e8e4966bdf03117"
  ],
  "backlinks": null,
  "word_count": 448,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Keyword-based memory search misses semantically related memories that don't share exact words (e.g., searching "dog" won't find a memory about "canine companions"). `VectorSearchStrategy` enables meaning-based retrieval by embedding both the query and candidates into vector space and scoring by cosine similarity.

It plugs into Soul Protocol's memory search architecture as an alternative or complement to BM25/keyword search.

## Pre-built Index vs On-the-Fly

The strategy supports two usage modes:

### Mode 1: Pre-built Index
```python
strategy = VectorSearchStrategy(embedder)
strategy.index_batch([entry.content for entry in memory_entries])
results = strategy.search_indexed("emotional support", limit=5)
```

Content is embedded once and stored. Subsequent searches only embed the query, not all candidates — O(1) embeddings per search instead of O(n).

### Mode 2: On-the-fly (no index)
```python
results = strategy.search("emotional support", memory_entries, limit=5)
```

The `search()` method consults the pre-built index for cached vectors, and falls back to live embedding for any candidate not in the index:

```python
vec = index_map.get(content) or self._embedder.embed(content)
```

This hybrid approach means search works correctly even if only some candidates were pre-indexed.

## Threshold Filtering

```python
if sim >= self._threshold:  # default 0.3
    scored.append((sim, candidate))
```

The threshold prevents low-relevance noise from appearing in results. At 0.3 cosine similarity (with normalized vectors), results must be meaningfully related to the query — not just sharing a few incidental tokens.

The threshold is a property with a setter, allowing dynamic adjustment at runtime:

```python
strategy.threshold = 0.5  # tighten for precision-focused recall
```

## Input Contract

`search()` accepts any objects with a `.content` attribute (like `MemoryEntry`) and handles the fallback gracefully:

```python
content = candidate.content if hasattr(candidate, "content") else str(candidate)
```

This defensive check prevents `AttributeError` if non-standard objects are passed.

## search() vs search_indexed()

| Method | Input | Returns | Use case |
|--------|-------|---------|----------|
| `search()` | candidate objects | ranked objects | MemoryEntry search |
| `search_indexed()` | (none, uses index) | (content, score) tuples | Raw similarity lookup |

`search_indexed()` is useful when the caller wants scores alongside content, not wrapped objects.

## Index Management

```python
strategy.index(content)           # add one content string
strategy.index_batch(contents)    # add many (uses embedder's batch API)
strategy.clear_index()            # reset for a fresh corpus
```

`index_batch()` is preferred for initial population — it invokes `embed_batch()` which is significantly faster for providers like sentence-transformers that do true batch inference.

## Known Gaps

- The index grows unbounded — there is no eviction policy or max-size limit. For souls with large episodic stores, the index could consume significant memory.
- The index is an in-memory list of `(content, vector)` tuples with O(n) lookup via `index_map` construction on every `search()` call. For large corpora, this should be replaced with a proper ANN index (e.g., FAISS or hnswlib).