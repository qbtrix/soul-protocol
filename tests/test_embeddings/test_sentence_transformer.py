# test_embeddings/test_sentence_transformer.py — Tests for SentenceTransformerProvider.
# Created: 2026-03-22 — Tests with mocked sentence-transformers library to avoid
# needing the heavy dependency in CI. Covers protocol compliance, lazy loading,
# batch embedding, import error handling.

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

np = pytest.importorskip("numpy", reason="numpy required for sentence-transformer tests")

from soul_protocol.runtime.embeddings.protocol import EmbeddingProvider


def _make_mock_st_module(dim: int = 384):
    """Create a mock sentence_transformers module with a working SentenceTransformer."""
    mock_model = MagicMock()

    def _encode(texts, convert_to_numpy=True, normalize_embeddings=False):
        vecs = np.random.default_rng(42).random((len(texts), dim)).astype(np.float32)
        if normalize_embeddings:
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            vecs = vecs / norms
        return vecs

    mock_model.encode = MagicMock(side_effect=_encode)

    mock_module = MagicMock()
    mock_module.SentenceTransformer = MagicMock(return_value=mock_model)
    return mock_module, mock_model


class TestSentenceTransformerProvider:
    """Tests for SentenceTransformerProvider with mocked sentence-transformers."""

    def _make_provider(self, dim: int = 384):
        mock_module, mock_model = _make_mock_st_module(dim)
        with patch.dict("sys.modules", {"sentence_transformers": mock_module}):
            from soul_protocol.runtime.embeddings.sentence_transformer import (
                SentenceTransformerProvider,
            )
            provider = SentenceTransformerProvider(model_name="all-MiniLM-L6-v2")
            # Trigger lazy load
            provider._load_model()
        return provider

    def test_is_embedding_provider(self) -> None:
        provider = self._make_provider()
        assert isinstance(provider, EmbeddingProvider)

    def test_dimensions(self) -> None:
        provider = self._make_provider(dim=384)
        assert provider.dimensions == 384

    def test_dimensions_custom(self) -> None:
        provider = self._make_provider(dim=768)
        assert provider.dimensions == 768

    def test_embed_returns_list_of_floats(self) -> None:
        provider = self._make_provider()
        vec = provider.embed("hello world")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)

    def test_embed_returns_correct_length(self) -> None:
        provider = self._make_provider(dim=384)
        vec = provider.embed("hello world")
        assert len(vec) == 384

    def test_embed_batch_returns_correct_count(self) -> None:
        provider = self._make_provider()
        texts = ["hello", "world", "test"]
        vecs = provider.embed_batch(texts)
        assert len(vecs) == 3

    def test_embed_batch_correct_dimensions(self) -> None:
        provider = self._make_provider(dim=384)
        vecs = provider.embed_batch(["a", "b"])
        for vec in vecs:
            assert len(vec) == 384

    def test_embed_batch_empty_list(self) -> None:
        provider = self._make_provider()
        vecs = provider.embed_batch([])
        assert vecs == []

    def test_lazy_loading_no_import_on_init(self) -> None:
        """Model should NOT be loaded on __init__, only on first embed."""
        from soul_protocol.runtime.embeddings.sentence_transformer import (
            SentenceTransformerProvider,
        )
        provider = SentenceTransformerProvider()
        assert provider._model is None

    def test_default_model_name(self) -> None:
        from soul_protocol.runtime.embeddings.sentence_transformer import (
            SentenceTransformerProvider,
        )
        provider = SentenceTransformerProvider()
        assert provider._model_name == "all-MiniLM-L6-v2"

    def test_custom_model_name(self) -> None:
        from soul_protocol.runtime.embeddings.sentence_transformer import (
            SentenceTransformerProvider,
        )
        provider = SentenceTransformerProvider(model_name="paraphrase-MiniLM-L3-v2")
        assert provider._model_name == "paraphrase-MiniLM-L3-v2"

    def test_custom_device(self) -> None:
        from soul_protocol.runtime.embeddings.sentence_transformer import (
            SentenceTransformerProvider,
        )
        provider = SentenceTransformerProvider(device="cpu")
        assert provider._device == "cpu"


class TestSentenceTransformerImportError:
    """Test graceful degradation when sentence-transformers is not installed."""

    def test_import_error_on_embed(self) -> None:
        from soul_protocol.runtime.embeddings.sentence_transformer import (
            SentenceTransformerProvider,
        )
        provider = SentenceTransformerProvider()

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers is required"):
                provider.embed("hello")

    def test_import_error_message_includes_install_hint(self) -> None:
        from soul_protocol.runtime.embeddings.sentence_transformer import (
            SentenceTransformerProvider,
        )
        provider = SentenceTransformerProvider()

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="embeddings-st"):
                provider.embed("hello")
