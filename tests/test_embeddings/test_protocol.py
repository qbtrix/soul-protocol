# test_embeddings/test_protocol.py — Protocol compliance tests for embedding providers.
# Created: 2026-03-06 — Verifies that HashEmbedder and TFIDFEmbedder satisfy the
# EmbeddingProvider protocol at runtime.

from __future__ import annotations

from soul_protocol.runtime.embeddings.hash_embedder import HashEmbedder
from soul_protocol.runtime.embeddings.protocol import EmbeddingProvider
from soul_protocol.runtime.embeddings.tfidf_embedder import TFIDFEmbedder


class TestProtocolCompliance:
    """Verify both embedders satisfy the EmbeddingProvider protocol."""

    def test_hash_embedder_is_embedding_provider(self) -> None:
        embedder = HashEmbedder()
        assert isinstance(embedder, EmbeddingProvider)

    def test_tfidf_embedder_is_embedding_provider(self) -> None:
        embedder = TFIDFEmbedder()
        assert isinstance(embedder, EmbeddingProvider)

    def test_hash_embedder_has_dimensions(self) -> None:
        embedder = HashEmbedder(dimensions=32)
        assert embedder.dimensions == 32

    def test_tfidf_embedder_has_dimensions(self) -> None:
        embedder = TFIDFEmbedder(dimensions=64)
        assert embedder.dimensions == 64

    def test_hash_embedder_embed_returns_correct_length(self) -> None:
        embedder = HashEmbedder(dimensions=32)
        vec = embedder.embed("hello world")
        assert len(vec) == 32
        assert all(isinstance(v, float) for v in vec)

    def test_tfidf_embedder_embed_returns_correct_length(self) -> None:
        embedder = TFIDFEmbedder(dimensions=64)
        embedder.fit(["hello world", "foo bar"])
        vec = embedder.embed("hello world")
        assert len(vec) == 64
        assert all(isinstance(v, float) for v in vec)

    def test_hash_embedder_embed_batch_returns_correct_count(self) -> None:
        embedder = HashEmbedder()
        texts = ["hello", "world", "test"]
        vecs = embedder.embed_batch(texts)
        assert len(vecs) == 3
        for vec in vecs:
            assert len(vec) == embedder.dimensions

    def test_tfidf_embedder_embed_batch_returns_correct_count(self) -> None:
        embedder = TFIDFEmbedder()
        texts = ["hello world", "foo bar", "test case"]
        embedder.fit(texts)
        vecs = embedder.embed_batch(texts)
        assert len(vecs) == 3
        for vec in vecs:
            assert len(vec) == embedder.dimensions

    def test_non_compliant_class_fails_isinstance(self) -> None:
        """A class without the right methods should fail isinstance check."""

        class NotAnEmbedder:
            pass

        obj = NotAnEmbedder()
        assert not isinstance(obj, EmbeddingProvider)

    def test_partial_implementation_fails_isinstance(self) -> None:
        """A class with only some methods should fail isinstance check."""

        class PartialEmbedder:
            @property
            def dimensions(self) -> int:
                return 10

            def embed(self, text: str) -> list[float]:
                return [0.0] * 10

            # Missing embed_batch

        obj = PartialEmbedder()
        assert not isinstance(obj, EmbeddingProvider)
