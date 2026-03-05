# memory/procedural.py — ProceduralStore for how-to memories.
# Updated: 2026-02-22 — Added entries() method for listing all procedures;
# replaced substring search with token-overlap relevance scoring via search.py.

from __future__ import annotations

import uuid

from soul_protocol.memory.search import relevance_score
from soul_protocol.types import MemoryEntry, MemoryType


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

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search procedures by token-overlap relevance scoring.

        Only entries with a relevance score > 0.0 are returned.
        Results are sorted by relevance (descending), then importance
        (descending), then created_at (most recent first).
        """
        scored: list[tuple[float, MemoryEntry]] = []
        for proc in self._procedures.values():
            score = relevance_score(query, proc.content)
            if score > 0.0:
                scored.append((score, proc))

        scored.sort(key=lambda t: (-t[0], -t[1].importance, -t[1].created_at.timestamp()))
        return [entry for _, entry in scored[:limit]]

    async def remove(self, memory_id: str) -> bool:
        """Remove a procedure by ID. Returns True if found and removed."""
        if memory_id in self._procedures:
            del self._procedures[memory_id]
            return True
        return False

    def entries(self) -> list[MemoryEntry]:
        """Return all procedural memories, sorted by importance desc then recency desc."""
        return sorted(
            self._procedures.values(),
            key=lambda e: (-e.importance, -e.created_at.timestamp()),
        )
