---
{
  "title": "Embeddings Spec Package — Public API Surface",
  "summary": "The `spec/embeddings` package defines the protocol-level public interface for all embedding operations in Soul Protocol. It re-exports the `EmbeddingProvider` protocol and three vector math primitives so consumers import from a single stable namespace.",
  "concepts": [
    "EmbeddingProvider",
    "cosine_similarity",
    "euclidean_distance",
    "dot_product",
    "spec layer",
    "vector math",
    "embedding protocol",
    "namespace re-export",
    "soul protocol spec",
    "pluggable backend"
  ],
  "categories": [
    "embeddings",
    "spec layer",
    "vector search",
    "protocol interfaces"
  ],
  "source_docs": [
    "77be261186378f9c"
  ],
  "backlinks": null,
  "word_count": 327,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `spec/embeddings/__init__.py` file is the public entry point for Soul Protocol's embedding layer. Its sole job is to gather the two modules that make up this sub-package — `protocol` and `similarity` — and expose their exports under a clean, stable namespace.

This design follows the "spec layer" principle used throughout Soul Protocol: the `spec/` tree contains only portable, opinion-free interfaces. No ML framework, no network calls, and no opinionated default implementation lives here.

## What Gets Re-exported

```python
from .protocol import EmbeddingProvider
from .similarity import cosine_similarity, dot_product, euclidean_distance

__all__ = [
    "EmbeddingProvider",
    "cosine_similarity",
    "euclidean_distance",
    "dot_product",
]
```

- **`EmbeddingProvider`** — the structural `Protocol` class that any embedding backend must satisfy. Consumers check compliance via `isinstance(obj, EmbeddingProvider)` without importing the concrete provider.
- **`cosine_similarity`**, **`euclidean_distance`**, **`dot_product`** — pure-Python vector math functions that work with any `list[float]` vector, regardless of which backend produced it.

## Why a Dedicated Package Init?

### Stable import surface
Downstream code (`VectorSearchStrategy`, retrieval adapters, the PocketPaw runtime) imports from `soul_protocol.spec.embeddings`, not from the inner modules. If the internal split between `protocol.py` and `similarity.py` changes in the future, consumers don't break.

### Namespace isolation
The `spec/` layer is the canonical definition. An `engine/`-level `embeddings/` package exists in the runtime, but it re-exports from here. Keeping the authoritative definitions in `spec/` means any third-party runtime can depend on `soul_protocol.spec.embeddings` without pulling in engine-specific dependencies.

### Version tracking
The module header records when each symbol was introduced (`v0.4.0`) and the rename from `core/` to `spec/`. This ties the exported API surface to protocol versioning, making it easier to deprecate or add symbols in a structured way.

## Data Flow

```
Consumer
  └─ import soul_protocol.spec.embeddings
        ├─ EmbeddingProvider  ←  spec/embeddings/protocol.py
        └─ cosine_similarity  ←  spec/embeddings/similarity.py
             euclidean_distance
             dot_product
```

Providers (sentence-transformers, OpenAI, local ONNX) implement `EmbeddingProvider`. The similarity functions are then used by retrieval strategies to rank candidates.

## Known Gaps

None flagged in this file. The init is intentionally minimal — it is a pass-through, not an implementation.