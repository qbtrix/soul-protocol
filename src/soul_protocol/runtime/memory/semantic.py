# memory/semantic.py — SemanticStore for fact-based memories with confidence.
# Updated: 2026-03-10 — Added search_and_delete() and delete_before() for
#   GDPR-compliant targeted and time-based memory deletion.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Updated: v0.2.2 — Filter superseded facts from search() and facts().
#   Added include_superseded parameter to facts() for history access.
#   2026-02-22 — Replaced substring search with token-overlap relevance
#   scoring via search.py. Results now sorted by relevance, importance, recency.
# Updated: Added structured logging for fact eviction events.

from __future__ import annotations

import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

from soul_protocol.runtime.memory.search import relevance_score
from soul_protocol.runtime.types import MemoryEntry, MemoryType


class SemanticStore:
    """In-memory store for semantic (fact-based) memories.

    Semantic memories represent general knowledge and extracted facts:
    "User prefers dark mode", "User works at Acme Corp", etc.
    Each fact carries importance (1-10) and confidence (0.0-1.0) scores.
    """

    def __init__(self, max_facts: int = 1000) -> None:
        self._max_facts = max_facts
        self._facts: dict[str, MemoryEntry] = {}

    async def add(self, entry: MemoryEntry) -> str:
        """Store a semantic memory entry.

        If the entry has no ID, one is generated. The type is forced
        to SEMANTIC regardless of what was passed in.

        Returns the memory ID.
        """
        if not entry.id:
            entry.id = uuid.uuid4().hex[:12]

        entry.type = MemoryType.SEMANTIC

        # Evict lowest-importance fact if at capacity
        if len(self._facts) >= self._max_facts:
            self._evict_least_important()

        self._facts[entry.id] = entry
        return entry.id

    async def search(
        self,
        query: str,
        limit: int = 10,
        min_importance: int = 0,
    ) -> list[MemoryEntry]:
        """Search facts by token-overlap relevance with optional importance filter.

        Only entries with a relevance score > 0.0 are returned.
        Results are sorted by relevance (descending), then importance
        (descending), then created_at (most recent first).
        """
        scored: list[tuple[float, MemoryEntry]] = []
        for fact in self._facts.values():
            if fact.superseded_by is not None:
                continue
            if fact.importance < min_importance:
                continue
            score = relevance_score(query, fact.content)
            if score > 0.0:
                scored.append((score, fact))

        scored.sort(key=lambda t: (-t[0], -t[1].importance, -t[1].created_at.timestamp()))
        return [entry for _, entry in scored[:limit]]

    async def remove(self, memory_id: str) -> bool:
        """Remove a fact by ID. Returns True if found and removed."""
        if memory_id in self._facts:
            del self._facts[memory_id]
            return True
        return False

    def facts(self, include_superseded: bool = False) -> list[MemoryEntry]:
        """Return all semantic facts, sorted by importance descending.

        Args:
            include_superseded: If True, include facts that have been
                superseded by newer facts. Default False.
        """
        facts_list = list(self._facts.values())
        if not include_superseded:
            facts_list = [f for f in facts_list if f.superseded_by is None]
        return sorted(
            facts_list,
            key=lambda e: (-e.importance, -e.created_at.timestamp()),
        )

    async def search_and_delete(self, query: str) -> list[str]:
        """Search for facts matching a query and delete them.

        Uses the same token-overlap scoring as search(). All matches
        with a relevance score > 0.0 are removed.

        Args:
            query: The search query to match against fact content.

        Returns:
            List of deleted fact IDs.
        """
        matches = await self.search(query, limit=len(self._facts))
        deleted_ids = [entry.id for entry in matches]
        for mid in deleted_ids:
            del self._facts[mid]
        return deleted_ids

    async def delete_before(self, timestamp: datetime) -> list[str]:
        """Delete all facts created before a given timestamp.

        Args:
            timestamp: The cutoff datetime. Facts older than this
                       are deleted.

        Returns:
            List of deleted fact IDs.
        """
        to_delete = [mid for mid, entry in self._facts.items() if entry.created_at < timestamp]
        for mid in to_delete:
            del self._facts[mid]
        return to_delete

    def _evict_least_important(self) -> None:
        """Remove the least important fact to make room."""
        if not self._facts:
            return
        least_id = min(
            self._facts,
            key=lambda mid: (
                self._facts[mid].importance,
                self._facts[mid].created_at.timestamp(),
            ),
        )
        logger.debug("Semantic fact evicted: id=%s", least_id)
        del self._facts[least_id]
