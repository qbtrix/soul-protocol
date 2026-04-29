---
{
  "title": "Vector Similarity Functions — Pure-Python Cosine, Euclidean, and Dot Product",
  "summary": "This module provides three zero-dependency vector similarity functions (`cosine_similarity`, `euclidean_distance`, `dot_product`) using only the Python standard library. All three include mismatch guards added in 2026-03-06 to catch incompatible vectors from different embedding backends before producing silent garbage results.",
  "concepts": [
    "cosine_similarity",
    "euclidean_distance",
    "dot_product",
    "vector similarity",
    "zero norm guard",
    "length mismatch guard",
    "semantic search",
    "stdlib only",
    "normalized vectors",
    "spec layer math"
  ],
  "categories": [
    "embeddings",
    "spec layer",
    "vector search",
    "math utilities"
  ],
  "source_docs": [
    "21c7f24c9ea54a05"
  ],
  "backlinks": null,
  "word_count": 505,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Vector similarity is the mathematical core of semantic search. When Soul Protocol's retrieval layer needs to rank memory entries against a query, it embeds both and computes a distance or similarity score. This module provides those three primitives in the spec layer so any runtime can use them without pulling in NumPy, SciPy, or any ML framework.

The decision to use only `math` from the standard library was deliberate: the spec layer must be embeddable in environments where scientific Python stacks are unavailable. For high-throughput production paths, the engine layer can substitute NumPy-backed implementations — but the spec provides a correct, auditable reference.

## The Three Functions

### `cosine_similarity(a, b) -> float`

```python
def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

Returns a value in `[-1.0, 1.0]`. A score of `1.0` means the vectors point in the same direction (semantically identical), `0.0` means orthogonal (unrelated), `-1.0` means opposite. This is the most common metric for semantic similarity because it is magnitude-independent — a long document and a short sentence about the same topic score similarly.

The zero-norm guard (`if norm_a == 0 or norm_b == 0: return 0.0`) handles the case where an empty or all-zero vector would cause a division-by-zero. This happens in practice when an embedding model returns a zero vector for very short or out-of-vocabulary inputs.

### `euclidean_distance(a, b) -> float`

Returns non-negative distance. Smaller values mean more similar vectors. Useful when the absolute distance between vectors matters — for example, when doing clustering or nearest-neighbor search where cluster tightness is meaningful.

### `dot_product(a, b) -> float`

For **normalized** vectors (unit norm), the dot product equals cosine similarity, making it a cheaper option when the backend pre-normalizes embeddings. The function makes no normalization assumption itself — callers are responsible for knowing whether their vectors are normalized.

## The Length Mismatch Guard

Added in 2026-03-06, all three functions now raise `ValueError` if the two input vectors differ in length:

```python
if len(a) != len(b):
    raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
```

This guard prevents a subtle silent failure: if two different embedding backends are in use (e.g., a 384-dim local model and a 1536-dim OpenAI model), `zip` would silently truncate the longer vector to the length of the shorter one. The resulting similarity score would be mathematically valid but semantically meaningless. Raising early with a clear error surfaces the backend misconfiguration at the comparison site rather than producing incorrect rankings.

## Data Flow

```
EmbeddingProvider.embed(query)   -> query_vec (list[float])
EmbeddingProvider.embed(memory)  -> memory_vec (list[float])
  └─ cosine_similarity(query_vec, memory_vec) -> float
       └─ retrieval ranking / sorting
```

## Known Gaps

None flagged. The functions are intentionally minimal. Performance optimization (NumPy dot, BLAS) is left to the engine layer.