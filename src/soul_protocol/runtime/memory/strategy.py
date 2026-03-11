# memory/strategy.py — SearchStrategy protocol for pluggable retrieval scoring.
# Updated: phase1-ablation-fixes — Added BM25SearchStrategy using BM25Index for
#   term-frequency-saturated scoring with IDF weighting.  Now the default strategy.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Created: v0.2.2 — Pluggable retrieval following CognitiveEngine pattern.
#   SearchStrategy: single-method protocol consumers implement for custom scoring.
#   TokenOverlapStrategy: zero-dependency default wrapping existing token-overlap.

from __future__ import annotations

from typing import Protocol, runtime_checkable

from soul_protocol.runtime.memory.search import BM25Index, relevance_score


@runtime_checkable
class SearchStrategy(Protocol):
    """Interface for memory retrieval scoring.

    The consumer provides a custom scoring strategy (embeddings, vector DB, etc.)
    via this interface. The soul uses it to rank memories during recall.

    The default is token-overlap matching (TokenOverlapStrategy). Replace with
    any implementation that scores query-content relevance on a 0.0-1.0 scale.

    Simplest implementation:
        class MySearch:
            def score(self, query: str, content: str) -> float:
                return cosine_similarity(embed(query), embed(content))
    """

    def score(self, query: str, content: str) -> float: ...


class TokenOverlapStrategy:
    """Zero-dependency default wrapping existing token-overlap scoring.

    Identical behavior to v0.2.1 — no change in output.
    Uses Jaccard token overlap: fraction of query tokens found in content.
    """

    def score(self, query: str, content: str) -> float:
        """Score relevance by token overlap (0.0 to 1.0)."""
        return relevance_score(query, content)


class BM25SearchStrategy:
    """BM25-based retrieval scoring with term-frequency saturation and IDF.

    Maintains an internal BM25Index that gets populated as memories are added.
    Scores are normalized to 0.0-1.0 range using a sigmoid-like mapping so
    they stay compatible with the activation formula.
    """

    def __init__(self) -> None:
        self._index = BM25Index()
        self._content_to_id: dict[str, str] = {}
        self._id_counter: int = 0

    def add(self, content: str) -> None:
        """Index a piece of content for future scoring.

        Args:
            content: The memory content to index.
        """
        doc_id = f"doc_{self._id_counter}"
        self._id_counter += 1
        self._content_to_id[content] = doc_id
        self._index.add(doc_id, content)

    def remove(self, content: str) -> None:
        """Remove content from the index.

        Args:
            content: The memory content to remove.
        """
        doc_id = self._content_to_id.pop(content, None)
        if doc_id is not None:
            self._index.remove(doc_id)

    def score(self, query: str, content: str) -> float:
        """Score relevance using BM25 (normalized to 0.0-1.0).

        If the content hasn't been indexed yet, it's added on-the-fly.

        Args:
            query: The search query.
            content: The content to score against.

        Returns:
            Float between 0.0 and 1.0 representing BM25-based relevance.
        """
        if content not in self._content_to_id:
            self.add(content)

        doc_id = self._content_to_id[content]
        raw = self._index.score(query, doc_id)

        # Normalize raw BM25 score to 0-1 range using tanh
        # tanh(raw / 3) gives a smooth mapping where score ~3 maps to ~0.75
        import math

        return math.tanh(raw / 3.0)
