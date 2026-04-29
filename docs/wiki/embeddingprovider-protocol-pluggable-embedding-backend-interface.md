---
{
  "title": "EmbeddingProvider Protocol — Pluggable Embedding Backend Interface",
  "summary": "`EmbeddingProvider` is a runtime-checkable `Protocol` class that defines the three-method contract any embedding backend must satisfy. It decouples Soul Protocol's retrieval and search features from any specific ML framework by requiring only `dimensions`, `embed`, and `embed_batch`.",
  "concepts": [
    "EmbeddingProvider",
    "runtime_checkable",
    "Protocol",
    "embed",
    "embed_batch",
    "dimensions",
    "vector search",
    "pluggable backend",
    "structural subtyping",
    "batch embedding"
  ],
  "categories": [
    "embeddings",
    "spec layer",
    "protocol interfaces",
    "vector search"
  ],
  "source_docs": [
    "5d8fa7eb11404dcc"
  ],
  "backlinks": null,
  "word_count": 451,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Embedding backends are diverse: sentence-transformers, OpenAI, local ONNX models, mock stubs for tests. Without a shared interface, every consumer that needs vector search would have to import a specific backend and depend on it directly. `EmbeddingProvider` solves this by expressing exactly what the protocol cares about — dimensionality and the ability to turn text into vectors — as a structural `Protocol`.

## Interface Definition

```python
@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

### `dimensions` property
Returns the fixed vector length for this backend. Consumers use this value to validate that two vectors are compatible before computing similarity — comparing a 384-dim and a 1536-dim vector would produce a nonsensical result (or raise a length mismatch guard, as `similarity.py` does). Exposing dimensionality as a property rather than a constant allows backends whose dimensionality is configured at runtime (e.g., truncated OpenAI embeddings) to report the correct value dynamically.

### `embed(text)`
Embeds a single string. The contract is that the returned vector's length equals `self.dimensions`. Callers that only need one vector at a time call this for simplicity.

### `embed_batch(texts)`
Embeds a list of strings in a single call. This exists because most embedding backends charge per API call or have per-request overhead. Batching amortizes that cost: instead of N network round trips, a consumer can embed an entire recall result set in one shot. The return shape is `list[list[float]]`, one vector per input text, in the same order.

## Why `runtime_checkable`?

Python's structural `Protocol` classes are not checked at runtime by default — `isinstance(obj, EmbeddingProvider)` would raise a `TypeError` unless `@runtime_checkable` is applied. Soul Protocol uses runtime checks in two places:

1. **Validation at registration** — when a consumer registers an embedding backend (e.g., `VectorSearchStrategy(provider=my_backend)`), the strategy can `assert isinstance(my_backend, EmbeddingProvider)` to catch misconfigured providers early rather than at search time.
2. **Type narrowing in tests** — test fixtures can verify that a mock properly satisfies the protocol before relying on it.

The cost is minor: `runtime_checkable` only checks that the required method names exist, not their signatures.

## Data Flow

```
Text input
  └─ EmbeddingProvider.embed(text) -> list[float]
       └─ VectorSearchStrategy.search(query)
            └─ cosine_similarity(query_vec, candidate_vec) -> float
                 └─ ranked retrieval results
```

## Placement in the Spec Layer

This is the canonical definition. The engine-level `embeddings/protocol.py` simply re-exports `EmbeddingProvider` from here, ensuring there is only one source of truth. Any third-party runtime that implements this protocol is automatically compatible with `VectorSearchStrategy` without needing a runtime dependency on PocketPaw.

## Known Gaps

None. The protocol is minimal by design — it deliberately omits lifecycle methods (model loading, warm-up, shutdown) because those are implementation concerns, not interface concerns.