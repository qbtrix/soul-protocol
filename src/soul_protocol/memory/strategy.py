# memory/strategy.py — SearchStrategy protocol for pluggable retrieval scoring.
# Created: v0.2.2 — Pluggable retrieval following CognitiveEngine pattern.
#   SearchStrategy: single-method protocol consumers implement for custom scoring.
#   TokenOverlapStrategy: zero-dependency default wrapping existing token-overlap.

from __future__ import annotations

from typing import Protocol, runtime_checkable

from soul_protocol.memory.search import relevance_score


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
