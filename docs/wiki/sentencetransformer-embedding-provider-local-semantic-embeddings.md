---
{
  "title": "SentenceTransformer Embedding Provider: Local Semantic Embeddings",
  "summary": "The `SentenceTransformerProvider` generates real semantic embeddings using the `sentence-transformers` library, with lazy model loading to defer the heavy import until first use. The default model `all-MiniLM-L6-v2` balances quality and speed with 384-dimensional normalized vectors, and supports GPU acceleration via configurable device selection.",
  "concepts": [
    "SentenceTransformerProvider",
    "sentence-transformers",
    "lazy model loading",
    "all-MiniLM-L6-v2",
    "semantic embeddings",
    "normalized embeddings",
    "batch embedding",
    "GPU acceleration",
    "device selection",
    "local embeddings"
  ],
  "categories": [
    "embeddings",
    "local AI",
    "memory search"
  ],
  "source_docs": [
    "a698adfd8bf2047f"
  ],
  "backlinks": null,
  "word_count": 420,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

For soul deployments that want high-quality local semantic embeddings without a cloud API, `SentenceTransformerProvider` wraps the `sentence-transformers` library. Unlike `HashEmbedder` (which is non-semantic) or `TFIDFEmbedder` (which requires a fit step), this provider produces vectors where semantically similar texts cluster together — enabling meaningful memory recall.

## Lazy Model Loading

The `sentence-transformers` library is large (pulls in PyTorch, transformers, etc.). Loading it at module import time would make even a simple `import soul_protocol` noticeably slow and would fail for users who haven't installed the extra.

```python
def _load_model(self) -> None:
    if self._model is not None:
        return  # idempotency guard — load exactly once
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError(
            "sentence-transformers is required ... "
            "Install: pip install 'soul-protocol[embeddings-st]'"
        ) from None
    self._model = SentenceTransformer(self._model_name, **kwargs)
    probe = self._model.encode(["probe"], convert_to_numpy=True)
    self._dimensions = int(probe.shape[1])
```

The idempotency guard (`if self._model is not None: return`) prevents double-loading on concurrent calls. After loading, a probe embedding determines the vector dimensionality — necessary because different sentence-transformer models produce different sizes (384 for MiniLM, 768 for larger models, etc.).

## Default Model: all-MiniLM-L6-v2

This model is a widely-used benchmark choice:
- **384 dimensions** — compact, fast to store and compare
- **Pre-trained on NLI and semantic similarity datasets** — good general-purpose quality
- **Runs on CPU** — no GPU required for reasonable throughput

Larger models (e.g., `all-mpnet-base-v2`) produce higher-quality embeddings at the cost of slower inference and larger vectors.

## Device Selection

```python
if self._device is not None:
    kwargs["device"] = self._device
```

Passing `device="cuda"` or `device="mps"` (Apple Silicon) routes computation to the GPU, dramatically accelerating batch embedding for large memory stores. Omitting it lets sentence-transformers auto-detect.

## Normalized Embeddings

Both `embed()` and `embed_batch()` pass `normalize_embeddings=True` to the model:

```python
vector = self._model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
```

Unit-normalized vectors make cosine similarity equivalent to dot product, which is faster to compute. All vectors have magnitude 1, so magnitude differences don't affect similarity scores.

## Batch Efficiency

```python
def embed_batch(self, texts: list[str]) -> list[list[float]]:
    vectors = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return [row.tolist() for row in vectors]
```

The model encodes all texts in a single forward pass. This is significantly faster than calling `embed()` in a loop, especially on GPU where batching amortizes data transfer overhead.

## Known Gaps

No TODOs or FIXMEs. One architectural note: `_load_model()` is not thread-safe — if two threads call `embed()` simultaneously before the model is loaded, both may enter the load path. In practice this is unlikely since soul agents are typically single-threaded, but it is a latent race condition.