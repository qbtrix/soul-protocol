# test_embeddings/test_openai_embeddings.py — Tests for OpenAIEmbeddingProvider.
# Created: 2026-03-22 — Tests with mocked openai library. Covers protocol compliance,
# retry logic, API key validation, batch embedding, dimension detection.

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from soul_protocol.runtime.embeddings.protocol import EmbeddingProvider


def _make_mock_response(texts: list[str], dim: int = 1536):
    """Build a mock OpenAI embeddings response."""
    data = []
    for i, text in enumerate(texts):
        embedding = [float(j * 0.001 + i * 0.01) for j in range(dim)]
        data.append(SimpleNamespace(index=i, embedding=embedding))
    return SimpleNamespace(data=data)


def _make_mock_openai_module(dim: int = 1536):
    """Create a mock openai module with a working OpenAI client."""
    mock_client = MagicMock()

    def _create_embeddings(input, model):
        return _make_mock_response(input, dim)

    mock_client.embeddings.create = MagicMock(side_effect=_create_embeddings)

    mock_module = MagicMock()
    mock_module.OpenAI = MagicMock(return_value=mock_client)
    return mock_module, mock_client


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider with mocked openai library."""

    def _make_provider(self, dim: int = 1536, **kwargs):
        mock_module, mock_client = _make_mock_openai_module(dim)
        with patch.dict("sys.modules", {"openai": mock_module}):
            from soul_protocol.runtime.embeddings.openai_embeddings import (
                OpenAIEmbeddingProvider,
            )

            provider = OpenAIEmbeddingProvider(api_key="test-key-123", **kwargs)
            # Pre-inject the mock client
            provider._client = mock_client
        return provider

    def test_is_embedding_provider(self) -> None:
        provider = self._make_provider()
        assert isinstance(provider, EmbeddingProvider)

    def test_dimensions_known_model(self) -> None:
        """Known models return dimensions without API call."""
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small", api_key="test")
        assert provider.dimensions == 1536

    def test_dimensions_large_model(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-large", api_key="test")
        assert provider.dimensions == 3072

    def test_embed_returns_list_of_floats(self) -> None:
        provider = self._make_provider()
        vec = provider.embed("hello world")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)

    def test_embed_returns_correct_length(self) -> None:
        provider = self._make_provider(dim=1536)
        vec = provider.embed("hello")
        assert len(vec) == 1536

    def test_embed_batch_returns_correct_count(self) -> None:
        provider = self._make_provider()
        texts = ["hello", "world", "test", "foo"]
        vecs = provider.embed_batch(texts)
        assert len(vecs) == 4

    def test_embed_batch_empty_list(self) -> None:
        provider = self._make_provider()
        vecs = provider.embed_batch([])
        assert vecs == []

    def test_embed_batch_correct_dimensions(self) -> None:
        provider = self._make_provider(dim=1536)
        vecs = provider.embed_batch(["a", "b", "c"])
        for vec in vecs:
            assert len(vec) == 1536

    def test_default_model(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider(api_key="test")
        assert provider._model == "text-embedding-3-small"

    def test_custom_model(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-large", api_key="test")
        assert provider._model == "text-embedding-3-large"

    def test_api_key_from_env(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key-456"}):
            provider = OpenAIEmbeddingProvider()
            assert provider._api_key == "env-key-456"

    def test_api_key_explicit_overrides_env(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            provider = OpenAIEmbeddingProvider(api_key="explicit-key")
            assert provider._api_key == "explicit-key"

    def test_missing_api_key_raises_value_error(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        mock_module = MagicMock()
        with patch.dict(os.environ, {}, clear=True):
            # Remove OPENAI_API_KEY if present
            os.environ.pop("OPENAI_API_KEY", None)
            provider = OpenAIEmbeddingProvider(api_key=None)
            provider._api_key = None
            with patch.dict("sys.modules", {"openai": mock_module}):
                with pytest.raises(ValueError, match="API key is required"):
                    provider.embed("hello")


class TestOpenAIRetryLogic:
    """Test retry with exponential backoff."""

    def test_retries_on_rate_limit(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        mock_module, mock_client = _make_mock_openai_module()

        rate_limit_error = Exception("Rate limited")
        rate_limit_error.status_code = 429

        # Fail twice, succeed third time
        mock_client.embeddings.create = MagicMock(
            side_effect=[
                rate_limit_error,
                rate_limit_error,
                _make_mock_response(["hello"]),
            ]
        )

        provider = OpenAIEmbeddingProvider(api_key="test", max_retries=3, base_delay=0.01)
        provider._client = mock_client

        with patch.dict("sys.modules", {"openai": mock_module}):
            vec = provider.embed("hello")
            assert len(vec) == 1536

    def test_raises_after_max_retries(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        mock_module, mock_client = _make_mock_openai_module()

        error = Exception("Server error")
        error.status_code = 500
        mock_client.embeddings.create = MagicMock(side_effect=error)

        provider = OpenAIEmbeddingProvider(api_key="test", max_retries=2, base_delay=0.01)
        provider._client = mock_client

        with patch.dict("sys.modules", {"openai": mock_module}):
            with pytest.raises(Exception, match="Server error"):
                provider.embed("hello")

    def test_no_retry_on_auth_error(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        mock_module, mock_client = _make_mock_openai_module()

        auth_error = Exception("Unauthorized")
        auth_error.status_code = 401
        mock_client.embeddings.create = MagicMock(side_effect=auth_error)

        provider = OpenAIEmbeddingProvider(api_key="bad-key", max_retries=3, base_delay=0.01)
        provider._client = mock_client

        with patch.dict("sys.modules", {"openai": mock_module}):
            with pytest.raises(Exception, match="Unauthorized"):
                provider.embed("hello")
            # Should only have been called once (no retries)
            assert mock_client.embeddings.create.call_count == 1


class TestOpenAIImportError:
    """Test graceful degradation when openai is not installed."""

    def test_import_error_on_embed(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider(api_key="test")
        provider._client = None

        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError, match="openai is required"):
                provider.embed("hello")

    def test_import_error_message_includes_install_hint(self) -> None:
        from soul_protocol.runtime.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider(api_key="test")
        provider._client = None

        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError, match="embeddings-openai"):
                provider.embed("hello")
