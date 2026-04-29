---
{
  "title": "Hash Embedder Test Suite — Determinism, Normalization, and Batch Embedding",
  "summary": "Test suite for `HashEmbedder`, soul-protocol's zero-dependency embedding backend that converts text to L2-normalized vectors via hashing. Covers dimensionality configuration, deterministic output, L2 normalization, edge cases (empty strings, whitespace), and batch embedding consistency.",
  "concepts": [
    "HashEmbedder",
    "L2 normalization",
    "deterministic hashing",
    "zero vector",
    "batch embedding",
    "dimensions",
    "case insensitive",
    "cosine similarity",
    "zero-dependency embedder",
    "vector length"
  ],
  "categories": [
    "testing",
    "embeddings",
    "hash-embedder",
    "test"
  ],
  "source_docs": [
    "1a9e0062b5b0c88e"
  ],
  "backlinks": null,
  "word_count": 348,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`HashEmbedder` is the default, always-available embedding backend. It uses hash functions to map text to fixed-dimension float vectors without any machine learning or external dependencies. This suite validates its correctness guarantees: same input always produces same output, vectors are L2-normalized, and batch results match individual results.

## Why This Exists

`HashEmbedder` is the fallback for all deployments — it must be correct because it's always used when no other provider is configured. Subtle bugs here would affect every soul that hasn't opted into a neural embedder.

## Dimensionality Tests

```python
class TestHashEmbedderDimensions:
    def test_default_dimensions(self):
        embedder = HashEmbedder()
        assert embedder.dimensions == 64

    def test_output_matches_dimensions(self):
        for dim in [16, 32, 64, 128, 256]:
            embedder = HashEmbedder(dimensions=dim)
            vec = embedder.embed("test text")
            assert len(vec) == dim
```

The dimension test loop validates that the configured dimension is actually honored — not just stored as an attribute but reflected in output vector length.

## Determinism Tests

```python
class TestHashEmbedderDeterminism:
    def test_same_input_same_output()
    def test_different_instances_same_output()
    def test_different_input_different_output()
    def test_case_insensitive()
```

Determinism is non-negotiable: the embedder must produce identical vectors for the same text across instances, processes, and restarts. `test_different_instances_same_output` specifically guards against state leakage between embedder instances. `test_case_insensitive` verifies that "Python" and "python" hash to the same vector — important for entity matching in the knowledge graph.

## Normalization Tests

```python
class TestHashEmbedderNormalization:
    def test_unit_norm()
    def test_empty_string_zero_vector()
    def test_whitespace_only_zero_vector()
```

L2 normalization ensures cosine similarity calculations are meaningful — unnormalized vectors would make similarity scores depend on vector magnitude rather than direction. The empty string and whitespace tests catch the edge case where normalization would divide by zero; returning a zero vector is the correct safe behavior.

## Batch Embedding

```python
class TestHashEmbedderBatch:
    def test_batch_matches_individual()
    def test_empty_batch()
    def test_single_item_batch()
```

`test_batch_matches_individual` verifies that `embed_batch([text])` returns the same result as calling `embed(text)` individually — preventing an optimization in the batch path from diverging from the single-item path.

## Known Gaps

No test covers hash collision behavior — two different texts that hash to the same position in the vector. In low-dimension configurations (e.g., 16 dimensions), collisions are more frequent and could degrade search quality.