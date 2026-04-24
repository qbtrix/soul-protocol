---
{
  "title": "Ollama Embedding Provider: Local Semantic Embeddings",
  "summary": "The `OllamaEmbeddingProvider` generates real semantic embeddings by calling a locally-running Ollama server, requiring no API key and keeping data on-device. It lazily initializes the Ollama client on first use and auto-detects vector dimensionality from the first embedding call.",
  "concepts": [
    "OllamaEmbeddingProvider",
    "Ollama",
    "local embeddings",
    "nomic-embed-text",
    "lazy imports",
    "dimension auto-detection",
    "batch embedding",
    "L2 normalization",
    "semantic embeddings",
    "privacy"
  ],
  "categories": [
    "embeddings",
    "local AI",
    "memory search"
  ],
  "source_docs": [
    "35ada577817e9b6a"
  ],
  "backlinks": null,
  "word_count": 453,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Not every soul deployment wants to send memory data to a cloud API. `OllamaEmbeddingProvider` addresses this by routing embedding requests to a locally-running Ollama instance — the same tool many developers already use for local LLM inference. This provides real semantic embeddings (where similar texts yield similar vectors) without API keys, rate limits, or data leaving the machine.

## Configuration

```python
provider = OllamaEmbeddingProvider(
    model="nomic-embed-text",       # default — good general-purpose embedder
    base_url="http://localhost:11434",  # Ollama's default port
    dimensions=768,                 # optional, auto-detected if omitted
)
```

The `base_url` is configurable to support non-default Ollama installations, Docker-based setups, or remote Ollama servers.

## Lazy Client Initialization

```python
def _get_client(self) -> object:
    if self._client is not None:
        return self._client
    try:
        from ollama import Client
    except ImportError:
        raise ImportError(
            "ollama is required ... Install: pip install 'soul-protocol[embeddings-ollama]'"
        ) from None
    self._client = Client(host=self._base_url)
    return self._client
```

The `ollama` Python library is only imported when the provider is first used. This prevents `ImportError` at module import time for users who don't have the library installed — the error surfaces at the point of actual use with a clear install instruction.

## Dimension Auto-Detection

Different Ollama models produce different vector sizes (e.g., `nomic-embed-text` produces 768-dim vectors). Rather than maintaining a hardcoded lookup table (which would go stale as new models are released), `OllamaEmbeddingProvider` learns the dimension from the first embedding call:

```python
@property
def dimensions(self) -> int:
    if self._dimensions is not None:
        return self._dimensions
    vec = self._embed_single("probe")   # triggers first real embed
    self._dimensions = len(vec)
    return self._dimensions
```

Callers can short-circuit this probe by passing `dimensions` to the constructor if they know their model's output size.

## Batch Handling

Ollama's API accepts a list of inputs in a single call. `embed_batch()` tries the native batch path first, falling back to sequential calls if the batch format is not supported:

```python
try:
    response = client.embed(model=self._model, input=texts)
    embeddings = response["embeddings"]
    return [list(e) for e in embeddings]
except (TypeError, KeyError):
    return [self._embed_single(t) for t in texts]  # fallback
```

The fallback protects against older Ollama versions or models that don't support batch input.

## L2 Normalization

The `_normalize()` helper L2-normalizes vectors. However, `embed()` calls `_embed_single()` directly without normalization — normalization is available but not currently applied in the main embedding path. Whether Ollama models return normalized vectors by default depends on the model.

## Known Gaps

- `embed()` does not call `_normalize()`. The `_normalize` method is defined but unused in the main code path. Depending on the model, raw Ollama embeddings may or may not be unit-normalized — this inconsistency could affect cosine similarity accuracy.
- No connection error handling: if the Ollama server is not running, the client will raise a network error with no custom message or retry logic.