---
{
  "title": "End-to-End Vector Search Test Suite — TF-IDF Semantic Memory Retrieval",
  "summary": "End-to-end tests for soul-protocol's semantic memory search pipeline using `TFIDFEmbedder` and `VectorSearchStrategy`. Tests create memory entries on distinct topics, fit the embedder, and verify that topical queries return relevant results in the correct order.",
  "concepts": [
    "TFIDFEmbedder",
    "VectorSearchStrategy",
    "cosine similarity",
    "semantic search",
    "vector indexing",
    "threshold filtering",
    "top-k",
    "memory recall",
    "topic clustering",
    "query expansion"
  ],
  "categories": [
    "testing",
    "embeddings",
    "vector-search",
    "test"
  ],
  "source_docs": [
    "591d6acc4929449c"
  ],
  "backlinks": null,
  "word_count": 389,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

This suite validates the complete vector search pipeline: creating memories, fitting the TF-IDF embedder, indexing memories, and querying with natural language. It serves as the behavioral specification for semantic search — the feature that allows souls to recall relevant memories from natural language queries.

## Why This Exists

Vector search is the primary recall mechanism. If it returns irrelevant results or silently skips memories, the soul's recall capability is broken. These tests verify end-to-end correctness across the full pipeline, not just individual components.

## Test Data Setup

```python
@pytest.fixture
def topic_memories() -> list[MemoryEntry]:
    # Creates memories about programming, cooking, and sports
    # Each topic has multiple entries with strong thematic vocabulary

@pytest.fixture
def vector_strategy(topic_memories) -> VectorSearchStrategy:
    # Fits TFIDFEmbedder on the topic_memories corpus
    # Returns a ready-to-query VectorSearchStrategy
```

The three-topic fixture design (programming, cooking, sports) creates maximally distinct semantic clusters. Using unambiguous vocabulary per topic ensures TF-IDF can reliably separate them without needing neural embeddings.

## Core Search Tests

```python
def test_programming_query_finds_programming_memories(vector_strategy, topic_memories)
def test_cooking_query_finds_cooking_memories(vector_strategy, topic_memories)
def test_sports_query_finds_sports_memories(vector_strategy, topic_memories)
```

Each test issues a domain-specific query and asserts that the top results are from the correct topic cluster. A failure here means TF-IDF weighting or cosine similarity scoring is broken.

## Threshold and Limit Controls

```python
def test_threshold_filtering(topic_memories)
def test_limit_parameter(vector_strategy, topic_memories)
```

Threshold filtering verifies that memories below the similarity cutoff are excluded — preventing low-relevance noise from entering the soul's context. The limit test verifies that `top_k` is respected, which matters for prompt budget management.

## Result Ordering

```python
def test_results_ordered_by_similarity(vector_strategy, topic_memories)
```

Results must be returned in descending similarity order. Out-of-order results would mean the most relevant memory is not presented first in the system prompt — a subtle but significant quality regression.

## Full Pipeline Test

`test_full_pipeline_with_index` exercises the complete flow including explicit index building, verifying that the `fit` → `build_index` → `search` sequence works correctly end-to-end.

## Data Flow

1. `_make_memory(content)` creates `MemoryEntry` objects with semantic type
2. `TFIDFEmbedder.fit(corpus)` builds the vocabulary and IDF weights
3. `VectorSearchStrategy` indexes memories using the fitted embedder
4. `cosine_similarity` scores query vectors against memory vectors
5. Results filtered by threshold, sorted by score, limited to top_k

## Known Gaps

All tests use clean, topic-distinct memories. Real-world memories have noisy, overlapping vocabulary. No test covers the case where multiple topics are mixed in a single memory entry.