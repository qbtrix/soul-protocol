# memory/social.py — SocialStore for relationship memories.
# Created: 2026-04-29 (#41) — New layer for storing per-user relationship
#   memories: interaction history snippets, trust signals, communication
#   preferences, anything the soul learns about its bonded entities. Same
#   shape as SemanticStore (a dict of MemoryEntry keyed by id) but without
#   superseded/confidence semantics. Wired into MemoryManager so callers
#   can reach it via ``manager.layer("social")`` (LayerView) or via the
#   underscore attribute ``manager._social`` (parallel to ``_semantic``,
#   ``_episodic``, ``_procedural``).

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from soul_protocol.runtime.memory.search import relevance_score
from soul_protocol.runtime.types import MemoryEntry, MemoryType

logger = logging.getLogger(__name__)


class SocialStore:
    """In-memory store for social (relationship) memories.

    Social memories capture per-user relationship signals — what the soul
    learned about how a particular person prefers to communicate, the trust
    level they've earned, the running tally of interactions. These are
    distinct from semantic facts (general knowledge) and episodic memories
    (specific events): they're the relationship layer.
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self._max_entries = max_entries
        self._entries: dict[str, MemoryEntry] = {}

    async def add(self, entry: MemoryEntry) -> str:
        """Store a social memory entry.

        If the entry has no ID, one is generated. The type is forced to
        SOCIAL and the layer is set to ``"social"`` so callers can store
        any MemoryEntry shape without remembering to set both fields.

        Returns the memory ID.
        """
        if not entry.id:
            entry.id = uuid.uuid4().hex[:12]

        entry.type = MemoryType.SOCIAL
        entry.layer = "social"

        if len(self._entries) >= self._max_entries:
            self._evict_least_important()

        self._entries[entry.id] = entry
        return entry.id

    async def search(
        self,
        query: str,
        limit: int = 10,
        min_importance: int = 0,
    ) -> list[MemoryEntry]:
        """Search social memories by token-overlap relevance.

        Only entries with a relevance score > 0.0 are returned. Results
        are sorted by relevance (descending), then importance (descending),
        then created_at (most recent first).
        """
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._entries.values():
            if entry.importance < min_importance:
                continue
            score = relevance_score(query, entry.content)
            if score > 0.0:
                scored.append((score, entry))

        scored.sort(key=lambda t: (-t[0], -t[1].importance, -t[1].created_at.timestamp()))
        return [entry for _, entry in scored[:limit]]

    async def remove(self, memory_id: str) -> bool:
        """Remove a social memory by ID. Returns True if found and removed."""
        if memory_id in self._entries:
            del self._entries[memory_id]
            return True
        return False

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Return a social memory by ID, or None if absent."""
        return self._entries.get(memory_id)

    def entries(self) -> list[MemoryEntry]:
        """Return all social memories, sorted by importance descending."""
        return sorted(
            self._entries.values(),
            key=lambda e: (-e.importance, -e.created_at.timestamp()),
        )

    async def search_and_delete(self, query: str) -> list[str]:
        """Search for social memories matching a query and delete them.

        Uses the same token-overlap scoring as ``search``. All matches
        with a relevance score > 0.0 are removed.

        Returns the list of deleted memory IDs.
        """
        matches = await self.search(query, limit=len(self._entries))
        deleted_ids = [entry.id for entry in matches]
        for mid in deleted_ids:
            del self._entries[mid]
        return deleted_ids

    async def delete_before(self, timestamp: datetime) -> list[str]:
        """Delete all social memories created before a given timestamp."""
        to_delete = [mid for mid, entry in self._entries.items() if entry.created_at < timestamp]
        for mid in to_delete:
            del self._entries[mid]
        return to_delete

    def count(self) -> int:
        """Return the number of stored social memories."""
        return len(self._entries)

    def _evict_least_important(self) -> None:
        """Remove the least-important entry to make room for a new one."""
        if not self._entries:
            return
        least_id = min(
            self._entries,
            key=lambda mid: (
                self._entries[mid].importance,
                self._entries[mid].created_at.timestamp(),
            ),
        )
        logger.debug("Social memory evicted: id=%s", least_id)
        del self._entries[least_id]
