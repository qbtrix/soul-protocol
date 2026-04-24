---
{
  "title": "OpenAI Embedding Provider with Retry Backoff",
  "summary": "The `OpenAIEmbeddingProvider` produces high-quality semantic embeddings via the OpenAI API, with built-in exponential backoff for rate limits and transient server errors. It lazily initializes the OpenAI client, pre-knows dimensions for standard models to avoid a probe call, and guarantees input ordering even when the API returns results out of order.",
  "concepts": [
    "OpenAIEmbeddingProvider",
    "text-embedding-3-small",
    "exponential backoff",
    "retry logic",
    "rate limiting",
    "input order",
    "lazy client",
    "batch embedding",
    "API key",
    "semantic embeddings"
  ],
  "categories": [
    "embeddings",
    "OpenAI",
    "memory search",
    "resilience"
  ],
  "source_docs": [
    "12a43626f1f08c73"
  ],
  "backlinks": null,
  "word_count": 419,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

OpenAI's embedding API (`text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`) produces state-of-the-art semantic vectors. This provider wraps that API with production-quality resilience: retry logic, lazy client creation, and input-order guarantees.

## Known Dimensions Table

```python
_KNOWN_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}
```

This avoids making a "probe" API call just to learn the vector size for well-known models. For unknown models, the dimensions are learned from the first actual embedding response.

## Retry with Exponential Backoff

OpenAI's API can return rate-limit errors (HTTP 429) or transient server errors (5xx). Without retry logic, a brief rate-limit burst would cause memory search to fail completely.

```python
for attempt in range(self._max_retries):
    try:
        response = client.embeddings.create(input=texts, model=self._model)
        ...
        return vectors
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if status is not None and status not in (429, 500, 502, 503, 504):
            raise  # non-retryable (e.g., 400 bad request, 401 auth)
        if attempt < self._max_retries - 1:
            delay = self._base_delay * (2 ** attempt)  # 1s, 2s, 4s
            time.sleep(delay)
raise last_error
```

Only specific HTTP status codes trigger retry — authentication errors (401), bad requests (400), and other non-transient errors are re-raised immediately to avoid wasting retry budget on unrecoverable failures.

## Input Order Guarantee

The OpenAI embeddings API returns results with an `index` field but does not guarantee they arrive in input order. The implementation sorts by index before returning:

```python
data = sorted(response.data, key=lambda d: d.index)
vectors = [d.embedding for d in data]
```

Without this sort, batch embedding results could be matched to the wrong input texts, corrupting memory search.

## Lazy Client Creation

The OpenAI client is only instantiated on first use, deferring the API key validation and library import. If no API key is set, a clear `ValueError` is raised at use time rather than at import time:

```python
if not self._api_key:
    raise ValueError(
        "OpenAI API key is required. Set OPENAI_API_KEY or pass api_key=..."
    )
```

## Batch Efficiency

`embed_batch()` sends all texts in a single API call, which is more efficient than calling `embed()` in a loop. OpenAI charges per token and batching avoids HTTP overhead per request.

## Known Gaps

- `time.sleep()` is used for retry delays, which blocks the event loop if called from an async context. The provider is not `async`-native — callers in async code should run it in a thread pool executor.
- The retry delay is not jittered (no random offset), which means multiple concurrent retry loops could synchronize and hammer the API together ("thundering herd").