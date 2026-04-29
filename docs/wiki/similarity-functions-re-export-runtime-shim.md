---
{
  "title": "Similarity Functions Re-export (Runtime Shim)",
  "summary": "This shim re-exports the three vector similarity functions (`cosine_similarity`, `dot_product`, `euclidean_distance`) from their canonical spec-layer location into the runtime embeddings namespace. It provides a stable import path for runtime code without creating a direct dependency on the spec layer's internal structure.",
  "concepts": [
    "cosine_similarity",
    "dot_product",
    "euclidean_distance",
    "similarity functions",
    "vector comparison",
    "semantic search",
    "spec layer",
    "re-export",
    "L2 normalization"
  ],
  "categories": [
    "embeddings",
    "memory search",
    "package structure"
  ],
  "source_docs": [
    "5e5a3b9373ee2e3a"
  ],
  "backlinks": null,
  "word_count": 258,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Vector similarity functions are foundational to semantic memory search — they determine how "close" two embedding vectors are to each other. The authoritative implementations live in `soul_protocol.spec.embeddings.similarity`, consistent with Soul Protocol's spec/runtime separation.

This file provides the runtime-facing import path:

```python
from soul_protocol.spec.embeddings.similarity import (
    cosine_similarity,
    dot_product,
    euclidean_distance,
)

__all__ = ["cosine_similarity", "euclidean_distance", "dot_product"]
```

## The Three Similarity Metrics

**Cosine similarity** — the primary metric used in `VectorSearchStrategy`. Measures the angle between two vectors, ignoring magnitude. Ranges from -1 (opposite) to 1 (identical). Most appropriate when vectors are L2-normalized (as all Soul Protocol embedders produce).

**Dot product** — equivalent to cosine similarity when vectors are unit-normalized, but faster to compute (no magnitude division). Used when you can guarantee normalization.

**Euclidean distance** — measures straight-line distance between two points in vector space. Less commonly used for text similarity; included for completeness and potential use in clustering.

## Why This Pattern?

The same rationale as `embeddings/protocol.py`: the spec layer owns the canonical definitions, but runtime consumers shouldn't need to import from `spec` directly. This shim absorbs refactor changes in the spec layer without breaking runtime callers.

The module comment records two refactor events that this shim insulated downstream code from:
- **v0.4.0**: Definitions moved to `spec/embeddings/similarity.py`
- **Runtime restructure**: Import path changed from `core` to `spec`

## Usage

```python
from soul_protocol.runtime.embeddings.similarity import cosine_similarity

score = cosine_similarity(query_vec, candidate_vec)  # float in [-1, 1]
```

Or via the top-level embeddings package:

```python
from soul_protocol.runtime.embeddings import cosine_similarity
```

## Known Gaps

No TODOs or FIXMEs. The module is intentionally minimal.