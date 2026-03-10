# memory/recall.py — RecallEngine for cross-store memory retrieval.
# Updated: 2026-03-10 — Accept optional personality param (passed by MemoryManager, reserved for future use).
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Updated: v0.2.2 — Accept optional SearchStrategy for pluggable spreading activation.
#   v0.2.0 — Replaced flat relevance scoring with ACT-R activation-based
#   ranking. Memories are now scored by base-level activation (recency + frequency),
#   spreading activation (query relevance), and emotional boost (somatic markers).
#   Access timestamps are updated on retrieval (strengthens future recall).
#   Timestamps capped at MAX_ACCESS_TIMESTAMPS to bound memory growth.

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from soul_protocol.runtime.memory.activation import compute_activation
from soul_protocol.runtime.memory.episodic import EpisodicStore
from soul_protocol.runtime.memory.procedural import ProceduralStore
from soul_protocol.runtime.memory.semantic import SemanticStore
from soul_protocol.runtime.types import MemoryEntry, MemoryType

if TYPE_CHECKING:
    from soul_protocol.runtime.memory.strategy import SearchStrategy

# Cap access_timestamps to prevent unbounded memory growth in long-running sessions.
# 100 timestamps is sufficient for ACT-R power-law decay calculations.
MAX_ACCESS_TIMESTAMPS: int = 100


class RecallEngine:
    """Cross-store memory retrieval engine with ACT-R activation scoring.

    Queries all configured memory stores and ranks results by cognitive
    activation: recency + frequency (base-level), query relevance (spreading),
    and emotional intensity (somatic boost).
    """

    def __init__(
        self,
        episodic: EpisodicStore,
        semantic: SemanticStore,
        procedural: ProceduralStore,
        strategy: SearchStrategy | None = None,
        personality: object | None = None,
    ) -> None:
        self._episodic = episodic
        self._semantic = semantic
        self._procedural = procedural
        self._strategy = strategy
        self._personality = personality

    async def recall(
        self,
        query: str,
        limit: int = 10,
        types: list[MemoryType] | None = None,
        min_importance: int = 0,
    ) -> list[MemoryEntry]:
        """Search across memory stores and return activation-ranked results.

        Args:
            query: Search string for activation scoring.
            limit: Maximum number of results to return.
            types: If provided, only search these memory types.
                   If None, search all stores.
            min_importance: Minimum importance score (1-10) for results.

        Returns:
            List of MemoryEntry sorted by activation score descending.
        """
        results: list[MemoryEntry] = []
        search_all = types is None

        # Query each store based on requested types
        if search_all or MemoryType.EPISODIC in types:
            episodic_results = await self._episodic.search(query, limit=limit)
            results.extend(episodic_results)

        if search_all or MemoryType.SEMANTIC in types:
            semantic_results = await self._semantic.search(
                query, limit=limit, min_importance=min_importance
            )
            results.extend(semantic_results)

        if search_all or MemoryType.PROCEDURAL in types:
            procedural_results = await self._procedural.search(query, limit=limit)
            results.extend(procedural_results)

        # Apply importance filter to non-semantic results (semantic already filtered)
        if min_importance > 0:
            results = [r for r in results if r.importance >= min_importance]

        now = datetime.now()

        # Score by ACT-R activation (deterministic — no noise in recall ranking)
        # Uses pluggable strategy for spreading activation if provided (v0.2.2)
        results.sort(
            key=lambda e: (
                -compute_activation(e, query, now=now, noise=False, strategy=self._strategy)
            ),
        )

        # Update access metadata on retrieved entries (strengthens future recall).
        # Cap timestamps to MAX_ACCESS_TIMESTAMPS to prevent unbounded growth.
        for entry in results[:limit]:
            entry.last_accessed = now
            entry.access_count += 1
            entry.access_timestamps.append(now)
            if len(entry.access_timestamps) > MAX_ACCESS_TIMESTAMPS:
                entry.access_timestamps = entry.access_timestamps[-MAX_ACCESS_TIMESTAMPS:]

        return results[:limit]
