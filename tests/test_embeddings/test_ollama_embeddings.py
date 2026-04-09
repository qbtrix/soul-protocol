# test_embeddings/test_ollama_embeddings.py — Tests for OllamaEmbeddingProvider.
# Created: 2026-03-22 — Tests with mocked ollama library. Covers protocol compliance,
# lazy loading, batch embedding, custom base_url, import error handling.

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from soul_protocol.runtime.embeddings.protocol import EmbeddingProvider


def _make_mock_ollama_module(dim: int = 768):
    """Create a mock ollama module with a working Client."""
    mock_client = MagicMock()

    def _embed(model, input):
        if isinstance(input, list):
            embeddings = [
                [float(j * 0.001 + i * 0.01) for j in range(dim)] for i in range(len(input))
            ]
        else:
            embeddings = [[float(j * 0.001) for j in range(dim)]]
        return {"embeddings": embeddings}

    mock_client.embed = MagicMock(side_effect=_embed)

    mock_module = MagicMock()
    mock_module.Client = MagicMock(return_value=mock_client)
    return mock_module, mock_client


class TestOllamaEmbeddingProvider:
    """Tests for OllamaEmbeddingProvider with mocked ollama library."""

    def _make_provider(self, dim: int = 768, **kwargs):
        mock_module, mock_client = _make_mock_ollama_module(dim)
        with patch.dict("sys.modules", {"ollama": mock_module}):
            from soul_protocol.runtime.embeddings.ollama_embeddings import (
                OllamaEmbeddingProvider,
            )

            provider = OllamaEmbeddingProvider(**kwargs)
            provider._client = mock_client
        return provider

    def test_is_embedding_provider(self) -> None:
        provider = self._make_provider()
        assert isinstance(provider, EmbeddingProvider)

    def test_dimensions_auto_detect(self) -> None:
        provider = self._make_provider(dim=768)
        assert provider.dimensions == 768

    def test_dimensions_explicit(self) -> None:
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider(dimensions=512)
        assert provider.dimensions == 512

    def test_embed_returns_list_of_floats(self) -> None:
        provider = self._make_provider()
        vec = provider.embed("hello world")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)

    def test_embed_returns_correct_length(self) -> None:
        provider = self._make_provider(dim=768)
        vec = provider.embed("hello")
        assert len(vec) == 768

    def test_embed_batch_returns_correct_count(self) -> None:
        provider = self._make_provider()
        texts = ["hello", "world", "test"]
        vecs = provider.embed_batch(texts)
        assert len(vecs) == 3

    def test_embed_batch_empty_list(self) -> None:
        provider = self._make_provider()
        vecs = provider.embed_batch([])
        assert vecs == []

    def test_embed_batch_correct_dimensions(self) -> None:
        provider = self._make_provider(dim=768)
        vecs = provider.embed_batch(["a", "b"])
        for vec in vecs:
            assert len(vec) == 768

    def test_default_model(self) -> None:
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider()
        assert provider._model == "nomic-embed-text"

    def test_custom_model(self) -> None:
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider(model="mxbai-embed-large")
        assert provider._model == "mxbai-embed-large"

    def test_default_base_url(self) -> None:
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider()
        assert provider._base_url == "http://localhost:11434"

    def test_custom_base_url(self) -> None:
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider(base_url="http://gpu-box:11434")
        assert provider._base_url == "http://gpu-box:11434"

    def test_lazy_loading_no_client_on_init(self) -> None:
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider()
        assert provider._client is None


class TestOllamaImportError:
    """Test graceful degradation when ollama is not installed."""

    def test_import_error_on_embed(self) -> None:
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider()

        with patch.dict("sys.modules", {"ollama": None}):
            with pytest.raises(ImportError, match="ollama is required"):
                provider.embed("hello")

    def test_import_error_message_includes_install_hint(self) -> None:
        from soul_protocol.runtime.embeddings.ollama_embeddings import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider()

        with patch.dict("sys.modules", {"ollama": None}):
            with pytest.raises(ImportError, match="embeddings-ollama"):
                provider.embed("hello")
