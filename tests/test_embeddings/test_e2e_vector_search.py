# test_embeddings/test_e2e_vector_search.py — End-to-end vector search tests.
# Created: 2026-03-06 — Creates memory entries about different topics (programming,
# cooking, sports), uses VectorSearchStrategy with TFIDFEmbedder, and verifies
# that semantic search returns topically relevant results.

from __future__ import annotations

from datetime import datetime

import pytest

from soul_protocol.runtime.embeddings.similarity import cosine_similarity
from soul_protocol.runtime.embeddings.tfidf_embedder import TFIDFEmbedder
from soul_protocol.runtime.embeddings.vector_strategy import VectorSearchStrategy
from soul_protocol.runtime.types import MemoryEntry, MemoryType


def _make_memory(content: str, mem_type: MemoryType = MemoryType.SEMANTIC) -> MemoryEntry:
    """Create a MemoryEntry for testing."""
    return MemoryEntry(
        type=mem_type,
        content=content,
        importance=5,
        created_at=datetime.now(),
    )


class TestE2EVectorSearch:
    """End-to-end tests: create memories, fit embedder, search semantically."""

    @pytest.fixture
    def topic_memories(self) -> list[MemoryEntry]:
        """Create diverse memories across three topics."""
        return [
            # Programming memories
            _make_memory("I learned Python programming and built a web scraper"),
            _make_memory("Debugging JavaScript code in the browser console"),
            _make_memory("Writing unit tests with pytest for the backend API"),
            _make_memory("Deploying a Docker container to the cloud server"),
            # Cooking memories
            _make_memory("Made homemade pasta with fresh tomato basil sauce"),
            _make_memory("Tried a new chocolate cake recipe with cream frosting"),
            _make_memory("Grilled salmon with lemon butter and roasted vegetables"),
            _make_memory("Baked sourdough bread using a wild yeast starter"),
            # Sports memories
            _make_memory("Watched the football championship game last weekend"),
            _make_memory("Went running in the park for five miles this morning"),
            _make_memory("Played basketball at the community center gym"),
            _make_memory("Swimming laps at the pool for cardio training"),
        ]

    @pytest.fixture
    def vector_strategy(self, topic_memories: list[MemoryEntry]) -> VectorSearchStrategy:
        """Create a fitted VectorSearchStrategy."""
        corpus = [m.content for m in topic_memories]
        embedder = TFIDFEmbedder(dimensions=128)
        embedder.fit(corpus)
        return VectorSearchStrategy(embedder, threshold=0.0)

    def test_programming_query_finds_programming_memories(
        self,
        vector_strategy: VectorSearchStrategy,
        topic_memories: list[MemoryEntry],
    ) -> None:
        """Search for 'python coding' — programming memories should rank higher."""
        results = vector_strategy.search("python coding programming", topic_memories, limit=4)
        assert len(results) > 0

        # At least one of the top results should be about programming
        top_contents = [r.content for r in results]
        programming_keywords = ["python", "javascript", "pytest", "docker", "code", "programming"]
        has_programming = any(
            any(kw in content.lower() for kw in programming_keywords) for content in top_contents
        )
        assert has_programming, f"Expected programming results in top 4, got: {top_contents}"

    def test_cooking_query_finds_cooking_memories(
        self,
        vector_strategy: VectorSearchStrategy,
        topic_memories: list[MemoryEntry],
    ) -> None:
        """Search for 'recipe' — cooking memories should rank higher."""
        results = vector_strategy.search("recipe cooking food", topic_memories, limit=4)
        assert len(results) > 0

        top_contents = [r.content for r in results]
        cooking_keywords = ["pasta", "cake", "recipe", "salmon", "bread", "baked", "grilled"]
        has_cooking = any(
            any(kw in content.lower() for kw in cooking_keywords) for content in top_contents
        )
        assert has_cooking, f"Expected cooking results in top 4, got: {top_contents}"

    def test_sports_query_finds_sports_memories(
        self,
        vector_strategy: VectorSearchStrategy,
        topic_memories: list[MemoryEntry],
    ) -> None:
        """Search for sports-related terms — sports memories should rank higher."""
        # Use terms that actually appear in the sports corpus entries
        results = vector_strategy.search(
            "football basketball running swimming", topic_memories, limit=4
        )
        assert len(results) > 0

        top_contents = [r.content for r in results]
        sports_keywords = [
            "football",
            "running",
            "basketball",
            "swimming",
            "game",
            "laps",
            "park",
            "gym",
            "pool",
        ]
        has_sports = any(
            any(kw in content.lower() for kw in sports_keywords) for content in top_contents
        )
        assert has_sports, f"Expected sports results in top 4, got: {top_contents}"

    def test_threshold_filtering(
        self,
        topic_memories: list[MemoryEntry],
    ) -> None:
        """High threshold should exclude low-similarity results."""
        corpus = [m.content for m in topic_memories]
        embedder = TFIDFEmbedder(dimensions=128)
        embedder.fit(corpus)

        # Very high threshold — should get very few or no results
        strict_strategy = VectorSearchStrategy(embedder, threshold=0.95)
        results = strict_strategy.search(
            "completely unrelated quantum physics topic", topic_memories
        )
        # With threshold 0.95 and an unrelated query, should get very few matches
        assert len(results) < len(topic_memories)

    def test_limit_parameter(
        self,
        vector_strategy: VectorSearchStrategy,
        topic_memories: list[MemoryEntry],
    ) -> None:
        """Limit parameter should cap the number of results."""
        results_2 = vector_strategy.search("programming", topic_memories, limit=2)
        results_10 = vector_strategy.search("programming", topic_memories, limit=10)
        assert len(results_2) <= 2
        assert len(results_10) <= 10

    def test_results_ordered_by_similarity(
        self,
        vector_strategy: VectorSearchStrategy,
        topic_memories: list[MemoryEntry],
    ) -> None:
        """Results should be ordered by descending similarity."""
        results = vector_strategy.search("python coding", topic_memories, limit=12)
        if len(results) < 2:
            pytest.skip("Not enough results to test ordering")

        embedder = vector_strategy.embedder
        query_vec = embedder.embed("python coding")
        similarities = [cosine_similarity(query_vec, embedder.embed(r.content)) for r in results]
        # Verify descending order
        for i in range(len(similarities) - 1):
            assert similarities[i] >= similarities[i + 1] - 1e-9

    def test_full_pipeline_with_index(
        self,
        topic_memories: list[MemoryEntry],
    ) -> None:
        """Test the index-based search path end-to-end."""
        corpus = [m.content for m in topic_memories]
        embedder = TFIDFEmbedder(dimensions=128)
        embedder.fit(corpus)

        strategy = VectorSearchStrategy(embedder, threshold=0.0)
        strategy.index_batch(corpus)

        results = strategy.search_indexed("python programming", limit=3)
        assert len(results) > 0
        # Results are (content, similarity) tuples
        top_content = results[0][0]
        assert isinstance(top_content, str)
        assert results[0][1] >= results[-1][1]  # Ordered by similarity
