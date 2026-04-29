---
{
  "title": "Sentence Transformer Embedding Provider Test Suite — Lazy Loading and Mock-Based Validation",
  "summary": "Test suite for `SentenceTransformerProvider`, which wraps the `sentence-transformers` library for high-quality local embedding generation. Tests mock the heavy ML dependency to run in CI, covering protocol compliance, lazy model loading, batch embedding, custom model and device configuration, and import error handling.",
  "concepts": [
    "SentenceTransformerProvider",
    "lazy model loading",
    "sentence-transformers",
    "mock ML dependency",
    "numpy",
    "batch encoding",
    "device configuration",
    "all-MiniLM-L6-v2",
    "importorskip",
    "protocol compliance",
    "normalize embeddings"
  ],
  "categories": [
    "testing",
    "embeddings",
    "sentence-transformers",
    "test"
  ],
  "source_docs": [
    "0f56f445ce46d4bb"
  ],
  "backlinks": null,
  "word_count": 405,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`SentenceTransformerProvider` bridges soul-protocol to the `sentence-transformers` library, enabling high-quality local embeddings without requiring an external API. Since the library is a heavy ML dependency (hundreds of megabytes), the test suite uses mocks throughout to keep CI fast.

## Why This Exists

Sentence transformers produce significantly better embeddings than hash or TF-IDF approaches, making them the preferred local option for deployments that can tolerate the dependency. The tests validate that the provider correctly wraps the library's API without requiring it at test time.

## Numpy Dependency

```python
np = pytest.importorskip("numpy", reason="numpy required for sentence-transformer tests")
```

`pytest.importorskip` skips the entire test module if numpy is unavailable. This is correct behavior: sentence-transformers returns numpy arrays, and testing without numpy would require additional mocking that obscures the actual provider behavior.

## Mock Infrastructure

```python
def _make_mock_st_module(dim: int = 384):
    mock_model = MagicMock()
    def _encode(texts, convert_to_numpy=True, normalize_embeddings=False):
        vecs = np.random.default_rng(42).random((len(texts), dim))
        return vecs
    mock_model.encode.side_effect = _encode
```

The mock uses `numpy.random.default_rng(42)` with a fixed seed, so encode results are deterministic. This matters for tests that compare batch vs. individual output — the same seed produces the same vectors.

## Lazy Loading

```python
def test_lazy_loading_no_import_on_init()
```

The `SentenceTransformer` model is not loaded until the first `embed()` call. Loading a sentence-transformer model can take several seconds and requires downloading weights. Deferring this prevents slow startup and allows the provider to be configured without immediately paying the load cost.

## Protocol Compliance

```python
def test_is_embedding_provider()
```

Verifies structural protocol satisfaction, enabling interchangeable use with other embedding backends.

## Dimension Configuration

```python
def test_dimensions()
def test_dimensions_custom()
```

The default model (`all-MiniLM-L6-v2`) produces 384-dimensional vectors. Custom dimensions allow using different models with different output sizes.

## Batch Embedding

```python
def test_embed_batch_returns_correct_count()
def test_embed_batch_correct_dimensions()
def test_embed_batch_empty_list()
```

The sentence-transformers `encode()` method natively handles batches — the provider passes the full list rather than calling encode in a loop. The empty batch test ensures `encode([])` returns an empty list rather than raising.

## Device Configuration

```python
def test_custom_device()
```

Supports specifying the compute device (`cpu`, `cuda`, `mps`) at construction time, enabling GPU acceleration on Apple Silicon or CUDA-equipped machines.

## Import Error Handling

```python
class TestSentenceTransformerImportError:
    def test_import_error_on_embed()
    def test_import_error_message_includes_install_hint()
```

Missing `sentence-transformers` raises with an actionable install hint rather than a bare `ModuleNotFoundError`.

## Known Gaps

No test covers the `normalize_embeddings=True` path — the provider may or may not normalize output, and the behavior is not asserted. Normalization affects cosine similarity scores significantly.