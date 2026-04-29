---
{
  "title": "Embeddings Subsystem: Factory and Public API",
  "summary": "The embeddings `__init__.py` provides the `get_embedding_provider()` factory function and re-exports all public types from the embedding subsystem. The factory uses lazy imports for optional providers (sentence-transformers, OpenAI, Ollama) so that users without those dependencies installed do not pay an import cost or receive confusing `ImportError` on module load.",
  "concepts": [
    "embedding provider",
    "get_embedding_provider",
    "lazy imports",
    "factory function",
    "EmbeddingProvider",
    "VectorSearchStrategy",
    "cosine_similarity",
    "HashEmbedder",
    "TFIDFEmbedder",
    "optional extras"
  ],
  "categories": [
    "embeddings",
    "memory search",
    "package structure"
  ],
  "source_docs": [
    "29c4dcae448d7437"
  ],
  "backlinks": null,
  "word_count": 352,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The embedding subsystem powers vector-based semantic memory search in Soul Protocol. Multiple backends are supported — from zero-dependency hash-based and TF-IDF embedders for testing/lightweight use, to full semantic embedders backed by sentence-transformers, OpenAI, or a local Ollama instance.

This `__init__.py` is the single entry point: it exports all public types and provides `get_embedding_provider()` as a factory that abstracts away backend selection and lazy loading.

## Why Lazy Imports?

Optional providers like `sentence-transformers` and `openai` are large dependencies that many soul-protocol users will never need. If they were imported at module load time, any `import soul_protocol.runtime.embeddings` would fail with `ImportError` unless all optional extras were installed.

The factory defers these imports to call time:

```python
def get_embedding_provider(name: str = "hash", **kwargs) -> EmbeddingProvider:
    if name == "hash":
        return HashEmbedder(**kwargs)
    elif name == "tfidf":
        return TFIDFEmbedder(**kwargs)
    elif name == "sentence-transformer":
        from soul_protocol.runtime.embeddings.sentence_transformer import SentenceTransformerProvider
        return SentenceTransformerProvider(**kwargs)
    elif name == "openai":
        from soul_protocol.runtime.embeddings.openai_embeddings import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(**kwargs)
    elif name == "ollama":
        from soul_protocol.runtime.embeddings.ollama_embeddings import OllamaEmbeddingProvider
        return OllamaEmbeddingProvider(**kwargs)
    else:
        raise ValueError(f"Unknown embedding provider: {name!r}. Available: ...")
```

This way, installing `soul-protocol` without any extras still lets you use `hash` and `tfidf` providers. The `ImportError` only surfaces when you actually try to use an optional provider without its extra installed.

## Provider Lineup

| Name | Extra | Use Case |
|------|-------|----------|
| `hash` | none | Testing — deterministic, no semantics |
| `tfidf` | none | Lightweight similarity, needs `fit()` |
| `sentence-transformer` | `embeddings-st` | Local semantic embeddings |
| `openai` | `embeddings-openai` | Hosted high-quality embeddings |
| `ollama` | `embeddings-ollama` | Local LLM-backed embeddings |

## Public API

```python
from soul_protocol.runtime.embeddings import (
    EmbeddingProvider,      # Protocol / interface
    HashEmbedder,
    TFIDFEmbedder,
    VectorSearchStrategy,
    cosine_similarity,
    euclidean_distance,
    dot_product,
    get_embedding_provider,
)
```

All similarity functions and the `VectorSearchStrategy` are also re-exported here for convenience — callers don't need to know the internal module layout.

## Known Gaps

No TODOs or FIXMEs. The provider list is hardcoded in `get_embedding_provider()` — adding a new provider requires editing this function and `__all__`. A plugin registry pattern could make this extensible without source changes, but is not currently implemented.