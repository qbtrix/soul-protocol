# test_embeddings/test_tfidf_embedder.py — Tests for TFIDFEmbedder.
# Created: 2026-03-06 — Covers fitting, embedding, similarity between related
# texts, unfitted behavior, and edge cases.

from __future__ import annotations

import math

import pytest

from soul_protocol.runtime.embeddings.similarity import cosine_similarity
from soul_protocol.runtime.embeddings.tfidf_embedder import TFIDFEmbedder


class TestTFIDFEmbedderBasics:
    """Test basic TFIDFEmbedder functionality."""

    def test_default_dimensions(self) -> None:
        embedder = TFIDFEmbedder()
        assert embedder.dimensions == 128

    def test_custom_dimensions(self) -> None:
        embedder = TFIDFEmbedder(dimensions=64)
        assert embedder.dimensions == 64

    def test_not_fitted_initially(self) -> None:
        embedder = TFIDFEmbedder()
        assert not embedder.fitted

    def test_fitted_after_fit(self) -> None:
        embedder = TFIDFEmbedder()
        embedder.fit(["hello world"])
        assert embedder.fitted


class TestTFIDFEmbedderFit:
    """Test fitting on a corpus."""

    def test_fit_empty_corpus(self) -> None:
        embedder = TFIDFEmbedder()
        embedder.fit([])
        assert embedder.fitted
        vec = embedder.embed("anything")
        assert all(x == 0.0 for x in vec)

    def test_fit_builds_vocabulary(self) -> None:
        embedder = TFIDFEmbedder()
        embedder.fit(["python programming language", "java programming language"])
        # After fitting, embedding should produce non-zero vectors for corpus terms
        vec = embedder.embed("python programming")
        assert any(x != 0.0 for x in vec)

    def test_fit_respects_dimensions(self) -> None:
        embedder = TFIDFEmbedder(dimensions=5)
        # Fit with many unique terms
        embedder.fit(
            [
                "alpha beta gamma delta epsilon",
                "zeta eta theta iota kappa",
                "lambda mu nu xi omicron",
            ]
        )
        vec = embedder.embed("alpha beta")
        assert len(vec) == 5


class TestTFIDFEmbedderEmbed:
    """Test embedding behavior."""

    def test_unfitted_returns_zero_vector(self) -> None:
        embedder = TFIDFEmbedder()
        vec = embedder.embed("hello world")
        assert all(x == 0.0 for x in vec)

    def test_output_length_matches_dimensions(self) -> None:
        embedder = TFIDFEmbedder(dimensions=32)
        embedder.fit(["some text"])
        vec = embedder.embed("some text")
        assert len(vec) == 32

    def test_normalized_output(self) -> None:
        embedder = TFIDFEmbedder()
        embedder.fit(["hello world foo bar", "test case example"])
        vec = embedder.embed("hello world")
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            assert abs(norm - 1.0) < 1e-6

    def test_empty_text_returns_zero_vector(self) -> None:
        embedder = TFIDFEmbedder()
        embedder.fit(["hello world"])
        vec = embedder.embed("")
        assert all(x == 0.0 for x in vec)

    def test_unknown_terms_return_zero_vector(self) -> None:
        embedder = TFIDFEmbedder()
        embedder.fit(["alpha beta gamma"])
        vec = embedder.embed("zzzzz xxxxx")
        assert all(x == 0.0 for x in vec)


class TestTFIDFEmbedderSimilarity:
    """Test that related texts produce similar vectors."""

    @pytest.fixture
    def fitted_embedder(self) -> TFIDFEmbedder:
        embedder = TFIDFEmbedder(dimensions=128)
        corpus = [
            "python is a programming language used for web development",
            "javascript is used for frontend web development",
            "machine learning uses python and numpy for data science",
            "cooking pasta requires boiling water and adding sauce",
            "baking bread needs flour yeast water and salt",
            "football soccer basketball are popular team sports",
            "running swimming cycling are individual endurance sports",
        ]
        embedder.fit(corpus)
        return embedder

    def test_similar_topics_high_similarity(self, fitted_embedder: TFIDFEmbedder) -> None:
        vec1 = fitted_embedder.embed("python web development programming")
        vec2 = fitted_embedder.embed("javascript web development frontend")
        sim = cosine_similarity(vec1, vec2)
        # These share "web" and "development" — should have positive similarity
        assert sim > 0.0

    def test_different_topics_low_similarity(self, fitted_embedder: TFIDFEmbedder) -> None:
        vec_prog = fitted_embedder.embed("python programming language")
        vec_cook = fitted_embedder.embed("cooking pasta sauce")
        vec_sport = fitted_embedder.embed("football basketball sports")

        sim_prog_cook = cosine_similarity(vec_prog, vec_cook)
        sim_prog_sport = cosine_similarity(vec_prog, vec_sport)

        # Programming should be more different from cooking/sports
        # than cooking topics are to each other
        assert sim_prog_cook < 0.5
        assert sim_prog_sport < 0.5

    def test_identical_text_perfect_similarity(self, fitted_embedder: TFIDFEmbedder) -> None:
        vec = fitted_embedder.embed("python programming")
        sim = cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6


class TestTFIDFEmbedderBatch:
    """Test batch embedding."""

    def test_batch_matches_individual(self) -> None:
        embedder = TFIDFEmbedder()
        texts = ["hello world", "foo bar", "test case"]
        embedder.fit(texts)
        batch = embedder.embed_batch(texts)
        for text, batch_vec in zip(texts, batch):
            individual = embedder.embed(text)
            assert batch_vec == individual

    def test_empty_batch(self) -> None:
        embedder = TFIDFEmbedder()
        embedder.fit(["something"])
        assert embedder.embed_batch([]) == []
