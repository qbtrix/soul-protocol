# memory/procedural.py — ProceduralStore for how-to memories.
# Updated: feat/recall-graded-floor (#247) — search() takes a relevance_floor
#   and gates candidates via passes_relevance_floor() instead of a bare
#   `score > 0.0`. Default floor 0.0 keeps the historical "any overlap"
#   behaviour; a positive floor drops weak matches at the store level.
# Updated: 2026-03-10 — Added search_and_delete() and delete_before() for
#   GDPR-compliant targeted and time-based memory deletion.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Updated: 2026-02-22 — Added entries() method for listing all procedures;
# replaced substring search with token-overlap relevance scoring via search.py.

from __future__ import annotations

import uuid
from datetime import datetime

from soul_protocol.runtime.memory.search import (
    DEFAULT_RELEVANCE_FLOOR,
    passes_relevance_floor,
    relevance_score,
)
from soul_protocol.runtime.types import MemoryEntry, MemoryType


class ProceduralStore:
    """In-memory store for procedural (how-to) memories.

    Procedural memories capture learned processes and instructions:
    "To deploy, run X then Y", "User prefers PR workflow over direct push", etc.
    """

    def __init__(self) -> None:
        self._procedures: dict[str, MemoryEntry] = {}

    async def add(self, entry: MemoryEntry) -> str:
        """Store a procedural memory entry.

        If the entry has no ID, one is generated. The type is forced
        to PROCEDURAL regardless of what was passed in.

        Returns the memory ID.
        """
        if not entry.id:
            entry.id = uuid.uuid4().hex[:12]

        entry.type = MemoryType.PROCEDURAL
        self._procedures[entry.id] = entry
        return entry.id

    async def search(
        self,
        query: str,
        limit: int = 10,
        relevance_floor: float = DEFAULT_RELEVANCE_FLOOR,
    ) -> list[MemoryEntry]:
        """Search procedures by token-overlap relevance scoring.

        Only entries whose relevance score clears ``relevance_floor`` are
        returned. The default floor of 0.0 keeps the historical behaviour:
        any positive overlap earns a slot. A positive floor turns the gate
        graded — a weak match below the floor is dropped.

        Results are sorted by relevance (descending), then importance
        (descending), then created_at (most recent first).
        """
        scored: list[tuple[float, MemoryEntry]] = []
        for proc in self._procedures.values():
            score = relevance_score(query, proc.content)
            if passes_relevance_floor(score, relevance_floor):
                scored.append((score, proc))

        scored.sort(key=lambda t: (-t[0], -t[1].importance, -t[1].created_at.timestamp()))
        return [entry for _, entry in scored[:limit]]

    async def remove(self, memory_id: str) -> bool:
        """Remove a procedure by ID. Returns True if found and removed."""
        if memory_id in self._procedures:
            del self._procedures[memory_id]
            return True
        return False

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Return a procedure by ID, or None if absent."""
        return self._procedures.get(memory_id)

    async def search_and_delete(self, query: str) -> list[str]:
        """Search for procedures matching a query and delete them.

        Uses the same token-overlap scoring as search(). All matches
        with a relevance score > 0.0 are removed.

        Args:
            query: The search query to match against procedure content.

        Returns:
            List of deleted procedure IDs.
        """
        matches = await self.search(query, limit=len(self._procedures))
        deleted_ids = [entry.id for entry in matches]
        for mid in deleted_ids:
            del self._procedures[mid]
        return deleted_ids

    async def delete_before(self, timestamp: datetime) -> list[str]:
        """Delete all procedures created before a given timestamp.

        Args:
            timestamp: The cutoff datetime. Procedures older than this
                       are deleted.

        Returns:
            List of deleted procedure IDs.
        """
        to_delete = [mid for mid, entry in self._procedures.items() if entry.created_at < timestamp]
        for mid in to_delete:
            del self._procedures[mid]
        return to_delete

    def entries(self) -> list[MemoryEntry]:
        """Return all procedural memories, sorted by importance desc then recency desc."""
        return sorted(
            self._procedures.values(),
            key=lambda e: (-e.importance, -e.created_at.timestamp()),
        )
