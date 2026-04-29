---
{
  "title": "Ollama Embedding Provider Test Suite — Local Model Integration with Lazy Loading",
  "summary": "Test suite for `OllamaEmbeddingProvider`, which connects to a locally-running Ollama server for embedding generation. Tests use a mocked `ollama` library to avoid requiring a real server in CI, covering protocol compliance, lazy client initialization, batch embedding, custom model and base URL configuration, and graceful import error handling.",
  "concepts": [
    "OllamaEmbeddingProvider",
    "lazy loading",
    "local LLM",
    "mock ollama",
    "protocol compliance",
    "batch embedding",
    "custom base URL",
    "dimension auto-detect",
    "import error",
    "privacy-preserving embeddings"
  ],
  "categories": [
    "testing",
    "embeddings",
    "ollama",
    "test"
  ],
  "source_docs": [
    "c22bc4a3c6cf97d1"
  ],
  "backlinks": null,
  "word_count": 386,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`OllamaEmbeddingProvider` enables soul-protocol to use locally-running LLM models (via Ollama) for embedding generation — a privacy-preserving alternative to cloud APIs. This test suite validates the provider without requiring an actual Ollama installation by mocking the `ollama` Python library.

## Why This Exists

Ollama is an optional, heavyweight dependency that would be impractical to run in CI. However, the provider's behavior must still be validated. The mock-based approach tests the provider's logic (lazy loading, batch handling, error propagation) independently of the Ollama server.

## Mock Infrastructure

```python
def _make_mock_ollama_module(dim: int = 768):
    mock_client = MagicMock()
    def _embed(model, input):
        if isinstance(input, list):
            embeddings = [[float(j * 0.001 + i * 0.01) for j in range(dim)]
                          for i in range(len(input))]
        else:
            embeddings = [[float(j * 0.001) for j in range(dim)]]
        return {"embeddings": embeddings}
    mock_client.embed.side_effect = _embed
    ...
```

The mock returns dimensionally-correct float vectors, making downstream type and length assertions meaningful.

## Protocol Compliance

```python
def test_is_embedding_provider()
```

Verifies that `OllamaEmbeddingProvider` satisfies `isinstance(provider, EmbeddingProvider)`. This ensures it can be used interchangeably with other providers through the common interface.

## Lazy Loading

```python
def test_lazy_loading_no_client_on_init()
```

The Ollama client is not instantiated until the first `embed()` call. This prevents import-time failures when Ollama is configured but not running — the error only surfaces when embedding is actually attempted, which is far more debuggable.

## Dimension Detection

```python
def test_dimensions_auto_detect()
def test_dimensions_explicit()
```

When no explicit dimension is set, the provider probes the model with a test embedding to detect dimensions. When set explicitly, the declared value is used without probing — useful when dimension is known in advance and probing would add latency.

## Configuration

```python
def test_default_model()
def test_custom_model()
def test_default_base_url()
def test_custom_base_url()
```

The default base URL (`http://localhost:11434`) matches the Ollama server default. Custom URLs support scenarios where Ollama runs on a different host or port (e.g., a shared server in a development team).

## Import Error Handling

```python
class TestOllamaImportError:
    def test_import_error_on_embed()
    def test_import_error_message_includes_install_hint()
```

When the `ollama` package is not installed, the error message includes an install hint (`pip install ollama`). This surfaces the actionable fix rather than a confusing `ModuleNotFoundError`.

## Known Gaps

No test covers network errors (connection refused, timeout) from the Ollama server. These are expected to propagate as-is from the underlying HTTP client, but a test would confirm the behavior.