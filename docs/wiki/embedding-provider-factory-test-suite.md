---
{
  "title": "Embedding Provider Factory Test Suite",
  "summary": "Tests for `get_embedding_provider()`, the factory function that instantiates embedding backends by name. Covers all built-in providers (hash, TF-IDF), external providers with lazy imports (sentence-transformers, OpenAI, Ollama), kwargs passthrough, unknown provider errors, and import failure handling.",
  "concepts": [
    "get_embedding_provider",
    "factory pattern",
    "lazy import",
    "HashEmbedder",
    "TFIDFEmbedder",
    "EmbeddingProvider protocol",
    "kwargs passthrough",
    "unknown provider",
    "optional dependencies",
    "provider registry"
  ],
  "categories": [
    "testing",
    "embeddings",
    "factory-pattern",
    "test"
  ],
  "source_docs": [
    "547a9d15936b5363"
  ],
  "backlinks": null,
  "word_count": 382,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The embedding provider factory is the single entry point for selecting and instantiating an embedding backend. This test suite validates that the factory correctly maps provider names to implementations, passes configuration kwargs, handles unknown names gracefully, and degrades cleanly when optional dependencies are missing.

## Why This Exists

The factory is used by soul-protocol's memory layer to swap embedding backends at runtime. If the factory returns the wrong type, passes kwargs incorrectly, or silently falls back to a wrong provider, semantic search breaks — often in a way that's hard to diagnose because recall still returns results, just wrong ones.

## Built-In Providers

```python
class TestFactoryBuiltinProviders:
    def test_hash_provider(self):
        provider = get_embedding_provider("hash")
        assert isinstance(provider, HashEmbedder)

    def test_default_is_hash(self):
        # No name argument returns hash provider
        provider = get_embedding_provider()
        assert isinstance(provider, HashEmbedder)

    def test_builtin_providers_satisfy_protocol(self):
        # Both hash and tfidf pass isinstance(p, EmbeddingProvider)
```

`HashEmbedder` is the default because it has no dependencies and requires no fitting — it works out-of-the-box for any deployment. The protocol compliance check ensures both built-ins can be used interchangeably anywhere an `EmbeddingProvider` is expected.

## External Providers (Lazy Imports)

```python
class TestFactoryExternalProviders:
    def test_sentence_transformer_provider()
    def test_openai_provider()
    def test_ollama_provider()
    def test_ollama_provider_with_custom_url()
    def test_openai_provider_with_custom_model()
```

External providers are imported lazily — the factory only imports `sentence_transformers` or `openai` when those providers are explicitly requested. Tests mock the imports to avoid requiring the packages in CI. This validates that the lazy import pattern is implemented correctly and that kwargs (model names, base URLs) are forwarded to the provider constructors.

## Error Handling

```python
class TestFactoryErrors:
    def test_unknown_provider_raises_value_error()
    def test_unknown_provider_lists_available()
    def test_sentence_transformer_import_error()
```

Unknown provider names must raise `ValueError` with a helpful message listing available providers. This prevents silent typos — `get_embedding_provider("sentencetransformer")` should fail loudly, not return a hash embedder. The import error test verifies that missing optional dependencies produce an actionable install hint rather than a raw `ModuleNotFoundError`.

## Data Flow

```python
provider = get_embedding_provider("ollama", base_url="http://localhost:11434", model="nomic-embed-text")
```

1. Factory matches the name against a registry
2. For built-ins: instantiates directly with kwargs
3. For externals: performs lazy import, then instantiates with kwargs
4. Returns an `EmbeddingProvider`-compliant object

## Known Gaps

No test covers thread safety — if two threads call the factory simultaneously for an external provider, the lazy import could race. This is unlikely in practice but worth noting.