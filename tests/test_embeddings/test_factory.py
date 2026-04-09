# test_embeddings/test_factory.py — Tests for get_embedding_provider() factory.
# Created: 2026-03-22 — Covers all provider names, unknown names, kwargs passthrough,
# lazy import behavior, and graceful degradation for missing dependencies.

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from soul_protocol.runtime.embeddings import get_embedding_provider
from soul_protocol.runtime.embeddings.hash_embedder import HashEmbedder
from soul_protocol.runtime.embeddings.protocol import EmbeddingProvider
from soul_protocol.runtime.embeddings.tfidf_embedder import TFIDFEmbedder


class TestFactoryBuiltinProviders:
    """Test factory returns correct built-in providers."""

    def test_hash_provider(self) -> None:
        provider = get_embedding_provider("hash")
        assert isinstance(provider, HashEmbedder)

    def test_hash_provider_with_kwargs(self) -> None:
        provider = get_embedding_provider("hash", dimensions=32)
        assert provider.dimensions == 32

    def test_tfidf_provider(self) -> None:
        provider = get_embedding_provider("tfidf")
        assert isinstance(provider, TFIDFEmbedder)

    def test_tfidf_provider_with_kwargs(self) -> None:
        provider = get_embedding_provider("tfidf", dimensions=64)
        assert provider.dimensions == 64

    def test_default_is_hash(self) -> None:
        provider = get_embedding_provider()
        assert isinstance(provider, HashEmbedder)

    def test_builtin_providers_satisfy_protocol(self) -> None:
        for name in ["hash", "tfidf"]:
            provider = get_embedding_provider(name)
            assert isinstance(provider, EmbeddingProvider)


class TestFactoryExternalProviders:
    """Test factory creates external providers with lazy imports."""

    def test_sentence_transformer_provider(self) -> None:
        mock_module = MagicMock()
        mock_module.SentenceTransformer = MagicMock
        with patch.dict("sys.modules", {"sentence_transformers": mock_module}):
            provider = get_embedding_provider("sentence-transformer")
            from soul_protocol.runtime.embeddings.sentence_transformer import (
                SentenceTransformerProvider,
            )

            assert isinstance(provider, SentenceTransformerProvider)

    def test_openai_provider(self) -> None:
        provider = get_embedding_provider("openai", api_key="test-key")
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_ollama_provider(self) -> None:
        provider = get_embedding_provider("ollama")
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        assert isinstance(provider, OllamaEmbeddingProvider)

    def test_ollama_provider_with_custom_url(self) -> None:
        provider = get_embedding_provider("ollama", base_url="http://gpu-box:11434")
        assert provider._base_url == "http://gpu-box:11434"

    def test_openai_provider_with_custom_model(self) -> None:
        provider = get_embedding_provider("openai", model="text-embedding-3-large", api_key="test")
        assert provider._model == "text-embedding-3-large"


class TestFactoryErrors:
    """Test factory error handling."""

    def test_unknown_provider_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider("nonexistent")

    def test_unknown_provider_lists_available(self) -> None:
        with pytest.raises(ValueError, match="hash.*tfidf.*sentence-transformer.*openai.*ollama"):
            get_embedding_provider("bad-name")

    def test_sentence_transformer_import_error(self) -> None:
        """Factory should propagate ImportError when library missing."""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            provider = get_embedding_provider("sentence-transformer")
            with pytest.raises(ImportError, match="sentence-transformers"):
                provider.embed("hello")
