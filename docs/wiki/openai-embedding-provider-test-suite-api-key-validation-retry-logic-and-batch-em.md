---
{
  "title": "OpenAI Embedding Provider Test Suite — API Key Validation, Retry Logic, and Batch Embedding",
  "summary": "Test suite for `OpenAIEmbeddingProvider`, which calls the OpenAI embeddings API for high-quality vector representations. Tests use a mocked `openai` library and cover protocol compliance, API key validation, exponential backoff retry logic for rate limits, model dimension detection, and graceful import error handling.",
  "concepts": [
    "OpenAIEmbeddingProvider",
    "API key validation",
    "exponential backoff",
    "rate limit retry",
    "auth error",
    "dimension detection",
    "batch embedding",
    "mock openai",
    "text-embedding-3-small",
    "OPENAI_API_KEY",
    "protocol compliance"
  ],
  "categories": [
    "testing",
    "embeddings",
    "openai",
    "test"
  ],
  "source_docs": [
    "99e7a907f4900584"
  ],
  "backlinks": null,
  "word_count": 365,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`OpenAIEmbeddingProvider` integrates soul-protocol with OpenAI's text embedding API. This suite validates all aspects of the provider without making real API calls, using mocked `openai` module objects to simulate responses and error conditions.

## Why This Exists

OpenAI embeddings are the highest-quality option available in soul-protocol, but the API introduces real-world failure modes: rate limits, authentication failures, network errors. These tests validate that the provider handles each failure mode correctly before production traffic hits them.

## Mock Infrastructure

```python
def _make_mock_response(texts: list[str], dim: int = 1536):
    # Returns a mock OpenAI embeddings response
    # with correct shape: response.data[i].embedding

def _make_mock_openai_module(dim):
    # Returns a mock openai module with a working OpenAI client
```

The response mock matches the actual OpenAI SDK response shape, so provider code that navigates `response.data[i].embedding` works correctly against the mock.

## Protocol Compliance

```python
def test_is_embedding_provider()
```

Ensures `OpenAIEmbeddingProvider` satisfies the `EmbeddingProvider` protocol for interchangeable use with other backends.

## API Key Handling

```python
def test_api_key_from_env()
def test_api_key_explicit_overrides_env()
def test_missing_api_key_raises_value_error()
```

The provider reads the API key from `OPENAI_API_KEY` environment variable by default, but an explicit constructor argument takes precedence. Missing keys raise `ValueError` at construction time — failing fast rather than at the first embed call, which would be harder to diagnose.

## Retry Logic

```python
class TestOpenAIRetryLogic:
    def test_retries_on_rate_limit()
    def test_raises_after_max_retries()
    def test_no_retry_on_auth_error()
```

Rate limit errors (`429`) trigger exponential backoff retries. After exhausting retries, the error propagates. Auth errors (`401`) are not retried — they indicate a permanent configuration failure, not a transient one. Retrying on auth errors would waste time and potentially trigger account lockout.

## Model Dimension Detection

```python
def test_dimensions_known_model()
def test_dimensions_large_model()
```

Known models (`text-embedding-3-small` → 1536, `text-embedding-3-large` → 3072) return dimensions from a lookup table without API calls. Unknown models probe the API.

## Batch Embedding

Batch tests verify that the provider correctly handles multiple texts in a single API call — the OpenAI API returns `response.data[i].embedding` for each input, and the provider must correctly map results back to input order.

## Known Gaps

No test covers the `dimensions` parameter for OpenAI's dimension reduction feature (matryoshka embeddings). Retry backoff timing is not tested — only that retries occur, not the intervals between them.