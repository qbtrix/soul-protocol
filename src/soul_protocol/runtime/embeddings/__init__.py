# embeddings/__init__.py — Embedding subsystem for vector-based memory search.
# Updated: 2026-03-22 — Added get_embedding_provider() factory function and exports
#   for SentenceTransformerProvider, OpenAIEmbeddingProvider, OllamaEmbeddingProvider.
#   All new providers use lazy imports to avoid pulling in heavy deps at module level.
# Created: 2026-03-06 — Exports EmbeddingProvider protocol, built-in embedders,
# similarity functions, and VectorSearchStrategy.

from __future__ import annotations

from soul_protocol.runtime.embeddings.hash_embedder import HashEmbedder
from soul_protocol.runtime.embeddings.protocol import EmbeddingProvider
from soul_protocol.runtime.embeddings.similarity import (
    cosine_similarity,
    dot_product,
    euclidean_distance,
)
from soul_protocol.runtime.embeddings.tfidf_embedder import TFIDFEmbedder
from soul_protocol.runtime.embeddings.vector_strategy import VectorSearchStrategy


def get_embedding_provider(name: str = "hash", **kwargs: object) -> EmbeddingProvider:
    """Factory that returns the requested embedding provider with lazy imports.

    Built-in providers (no extra dependencies):
        - ``hash``  — Deterministic hash-based embedder (testing only).
        - ``tfidf`` — TF-IDF based embedder (basic similarity).

    Optional providers (require extras):
        - ``sentence-transformer`` — sentence-transformers library.
          Install: ``pip install 'soul-protocol[embeddings-st]'``
        - ``openai`` — OpenAI embedding API.
          Install: ``pip install 'soul-protocol[embeddings-openai]'``
        - ``ollama`` — Local Ollama server.
          Install: ``pip install 'soul-protocol[embeddings-ollama]'``

    Args:
        name: Provider identifier string.
        **kwargs: Passed through to the provider constructor.

    Returns:
        An instance satisfying the EmbeddingProvider protocol.

    Raises:
        ValueError: If the provider name is not recognized.
        ImportError: If the required library is not installed.
    """
    if name == "hash":
        return HashEmbedder(**kwargs)  # type: ignore[arg-type]
    elif name == "tfidf":
        return TFIDFEmbedder(**kwargs)  # type: ignore[arg-type]
    elif name == "sentence-transformer":
        from soul_protocol.runtime.embeddings.sentence_transformer import (
            SentenceTransformerProvider,
        )

        return SentenceTransformerProvider(**kwargs)  # type: ignore[arg-type]
    elif name == "openai":
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        return OpenAIEmbeddingProvider(**kwargs)  # type: ignore[arg-type]
    elif name == "ollama":
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        return OllamaEmbeddingProvider(**kwargs)  # type: ignore[arg-type]
    else:
        available = ["hash", "tfidf", "sentence-transformer", "openai", "ollama"]
        raise ValueError(f"Unknown embedding provider: {name!r}. Available: {', '.join(available)}")


__all__ = [
    "EmbeddingProvider",
    "HashEmbedder",
    "TFIDFEmbedder",
    "VectorSearchStrategy",
    "cosine_similarity",
    "euclidean_distance",
    "dot_product",
    "get_embedding_provider",
]
