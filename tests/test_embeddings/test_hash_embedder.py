# test_embeddings/test_hash_embedder.py — Tests for HashEmbedder.
# Created: 2026-03-06 — Covers determinism, dimensionality, normalization,
# batch embedding, and edge cases.

from __future__ import annotations

import math

from soul_protocol.runtime.embeddings.hash_embedder import HashEmbedder


class TestHashEmbedderDimensions:
    """Test dimensionality configuration."""

    def test_default_dimensions(self) -> None:
        embedder = HashEmbedder()
        assert embedder.dimensions == 64

    def test_custom_dimensions(self) -> None:
        embedder = HashEmbedder(dimensions=128)
        assert embedder.dimensions == 128

    def test_output_matches_dimensions(self) -> None:
        for dim in [16, 32, 64, 128, 256]:
            embedder = HashEmbedder(dimensions=dim)
            vec = embedder.embed("test text")
            assert len(vec) == dim


class TestHashEmbedderDeterminism:
    """Test that same input always produces same output."""

    def test_same_input_same_output(self) -> None:
        embedder = HashEmbedder()
        vec1 = embedder.embed("hello world")
        vec2 = embedder.embed("hello world")
        assert vec1 == vec2

    def test_different_instances_same_output(self) -> None:
        e1 = HashEmbedder(dimensions=32)
        e2 = HashEmbedder(dimensions=32)
        assert e1.embed("test") == e2.embed("test")

    def test_different_input_different_output(self) -> None:
        embedder = HashEmbedder()
        vec1 = embedder.embed("hello world")
        vec2 = embedder.embed("goodbye universe")
        assert vec1 != vec2

    def test_case_insensitive(self) -> None:
        embedder = HashEmbedder()
        vec1 = embedder.embed("Hello World")
        vec2 = embedder.embed("hello world")
        assert vec1 == vec2


class TestHashEmbedderNormalization:
    """Test that output vectors are L2-normalized."""

    def test_unit_norm(self) -> None:
        embedder = HashEmbedder()
        vec = embedder.embed("some test text for normalization")
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_empty_string_zero_vector(self) -> None:
        embedder = HashEmbedder()
        vec = embedder.embed("")
        assert all(x == 0.0 for x in vec)

    def test_whitespace_only_zero_vector(self) -> None:
        embedder = HashEmbedder()
        vec = embedder.embed("   ")
        assert all(x == 0.0 for x in vec)


class TestHashEmbedderBatch:
    """Test batch embedding."""

    def test_batch_matches_individual(self) -> None:
        embedder = HashEmbedder()
        texts = ["alpha", "beta", "gamma"]
        batch = embedder.embed_batch(texts)
        for text, batch_vec in zip(texts, batch):
            individual = embedder.embed(text)
            assert batch_vec == individual

    def test_empty_batch(self) -> None:
        embedder = HashEmbedder()
        assert embedder.embed_batch([]) == []

    def test_single_item_batch(self) -> None:
        embedder = HashEmbedder()
        batch = embedder.embed_batch(["only one"])
        assert len(batch) == 1
        assert batch[0] == embedder.embed("only one")
