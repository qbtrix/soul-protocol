---
{
  "title": "Test Suite for Vector Similarity Functions",
  "summary": "Covers the three core similarity primitives — cosine similarity, Euclidean distance, and dot product — used by soul-protocol's embedding layer. Tests enforce correct mathematical behavior, zero-vector safety, empty-vector edge cases, and dimension-mismatch guards.",
  "concepts": [
    "cosine similarity",
    "euclidean distance",
    "dot product",
    "vector similarity",
    "embedding",
    "zero vector",
    "dimension mismatch",
    "memory retrieval",
    "unit vector",
    "normalization"
  ],
  "categories": [
    "testing",
    "embeddings",
    "memory retrieval",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "0b4caf3593dab2af"
  ],
  "backlinks": null,
  "word_count": 508,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `test_similarity.py` suite validates `soul_protocol.runtime.embeddings.similarity`, which provides the three vector comparison operations the memory retrieval system depends on: **cosine similarity**, **Euclidean distance**, and **dot product**. Getting these primitives wrong would cause silent ranking errors — memories would be recalled in the wrong order, or unrelated memories would appear relevant.

## Why Three Metrics?

Each metric serves a different retrieval scenario:

- **Cosine similarity** measures directional alignment regardless of vector magnitude. A memory about "machine learning" and a query for "neural networks" may produce vectors of different lengths but similar direction — cosine catches this while Euclidean distance would not.
- **Euclidean distance** measures absolute spatial distance. Useful when magnitude carries meaning, such as in importance-weighted embeddings.
- **Dot product** is the raw inner product. Used when vectors are already unit-normalized (since it equals cosine similarity in that case), offering a cheaper computation path.

## Test Groups

### `TestCosineSimilarity`
Validates the full geometric range:
- **Identical vectors** → must return `1.0` (pure match)
- **Opposite vectors** → must return `-1.0`
- **Orthogonal vectors** → must return `0.0` (no semantic overlap)
- **Zero vectors** (either or both) → must return `0.0` without raising a division-by-zero error. This is the most important defensive test: un-embedded or empty memories produce zero vectors, and the system must not crash when comparing them.
- **Parallel vectors of different magnitude** → must still return `1.0`, confirming the normalization step works correctly.
- **Known value** — `[1,0]` vs `[1,1]` → expected `1/sqrt(2) ≈ 0.707`, providing a concrete numerical regression anchor.

```python
def test_known_value(self) -> None:
    a = [1.0, 0.0]
    b = [1.0, 1.0]
    expected = 1.0 / math.sqrt(2)
    assert abs(cosine_similarity(a, b) - expected) < 1e-6
```

### `TestEuclideanDistance`
Focuses on correctness and symmetry:
- **Known distance** — `[0,0]` to `[3,4]` must equal `5.0` (3-4-5 triangle). This is a minimal regression test that catches sign or squaring bugs.
- **Symmetry** — `d(a,b) == d(b,a)`. Required because the implementation uses subtraction; a naive bug could produce asymmetric results.
- **Empty vectors** — must return `0.0` without raising.

### `TestDotProduct`
- Confirms `dot([1,0], [0,1]) == 0` for orthogonal unit vectors.
- Verifies that `dot_product` on normalized vectors equals `cosine_similarity`, giving a cross-metric consistency check.

### `TestVectorLengthMismatch`
All three functions must raise `ValueError` when inputs have different lengths. Without this guard, NumPy-style broadcasting might silently produce a wrong result; this suite forces an explicit contract.

```python
def test_cosine_similarity_mismatch(self) -> None:
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0])
```

## Data Flow Context

These functions sit at the bottom of the embedding stack:

```
MemoryEntry.content
    → embedder.embed()     # HashEmbedder or TFIDFEmbedder
    → [float, ...]         # fixed-length vector
    → cosine_similarity()  # compared against query vector
    → float score          # used to rank recall results
```

Any bug in similarity would propagate upward invisibly — wrong recall order, missed memories, or system crashes on edge-case inputs.

## Known Gaps

No known gaps flagged. The suite is comprehensive for the numeric contract. However, there are no property-based (hypothesis) tests for randomly generated vectors, which could catch floating-point edge cases not covered by hand-crafted examples.
