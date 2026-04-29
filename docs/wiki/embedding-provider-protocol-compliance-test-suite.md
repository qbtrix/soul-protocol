---
{
  "title": "Embedding Provider Protocol Compliance Test Suite",
  "summary": "Tests that verify `HashEmbedder` and `TFIDFEmbedder` correctly satisfy the `EmbeddingProvider` structural protocol at runtime. Also validates that partial or non-compliant implementations fail the `isinstance` check, ensuring the protocol is genuinely enforced rather than nominal.",
  "concepts": [
    "EmbeddingProvider protocol",
    "runtime_checkable",
    "isinstance check",
    "HashEmbedder",
    "TFIDFEmbedder",
    "structural subtyping",
    "protocol compliance",
    "embed_batch",
    "dimensions property",
    "partial implementation"
  ],
  "categories": [
    "testing",
    "embeddings",
    "protocol-design",
    "test"
  ],
  "source_docs": [
    "d6d66d1dcfecd76f"
  ],
  "backlinks": null,
  "word_count": 361,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `EmbeddingProvider` protocol defines the interface contract that all embedding backends must satisfy. This suite verifies that the two built-in providers (`HashEmbedder` and `TFIDFEmbedder`) comply at runtime and that non-compliant classes are correctly rejected by `isinstance(obj, EmbeddingProvider)` checks.

## Why This Exists

Python's structural protocols (via `typing.Protocol` with `@runtime_checkable`) are only enforced at runtime if `isinstance` is used — and only correctly if the protocol is defined with `@runtime_checkable`. This test suite serves as proof that the protocol is both correctly defined and actually checked. Without these tests, a future developer could accidentally rename a method and break all provider substitutability without a failing test.

## Compliance Tests

```python
class TestProtocolCompliance:
    def test_hash_embedder_is_embedding_provider(self):
        embedder = HashEmbedder()
        assert isinstance(embedder, EmbeddingProvider)

    def test_tfidf_embedder_is_embedding_provider(self):
        embedder = TFIDFEmbedder()
        assert isinstance(embedder, EmbeddingProvider)
```

These tests confirm that the concrete implementations satisfy the protocol. A failure here means either the protocol was changed (new required method added) or the implementation was changed (method renamed or removed).

## Property Tests

```python
    def test_hash_embedder_has_dimensions(self):
        embedder = HashEmbedder(dimensions=32)
        assert embedder.dimensions == 32

    def test_hash_embedder_embed_returns_correct_length(self):
        # embed() returns a list of floats with length == dimensions

    def test_hash_embedder_embed_batch_returns_correct_count(self):
        # embed_batch([t1, t2, t3]) returns 3 vectors
```

Beyond `isinstance`, the tests verify that the protocol's behavioral contract is met: `dimensions` is readable, `embed()` returns a correctly-sized list, and `embed_batch()` returns one vector per input.

## Non-Compliance Tests

```python
    def test_non_compliant_class_fails_isinstance(self):
        # A class with no embed() fails isinstance check

    def test_partial_implementation_fails_isinstance(self):
        class PartialEmbedder:
            def dimensions(self) -> int: return 64
            def embed(self, text) -> list[float]: return []
            # Missing embed_batch — should fail
```

The partial implementation test is particularly important: it verifies that the protocol requires all three methods (`dimensions`, `embed`, `embed_batch`). If `embed_batch` is omitted from the protocol definition, this test would fail and catch the gap.

## Data Flow

The `EmbeddingProvider` protocol requires:
1. `dimensions: int` — readable property returning vector size
2. `embed(text: str) -> list[float]` — single text embedding
3. `embed_batch(texts: list[str]) -> list[list[float]]` — batch embedding

## Known Gaps

The suite only tests the two built-in providers. External providers (OpenAI, Ollama, SentenceTransformer) are tested for protocol compliance in their own test files but not here.