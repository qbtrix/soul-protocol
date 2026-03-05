# memory/episodic.py — EpisodicStore for timestamped interaction memories.
# Updated: v0.2.0 — Store somatic markers and significance scores on entries.
#   Eviction now considers activation (significance + access) not just age.
#   Added store_with_psychology() for the enriched observe pipeline.

from __future__ import annotations

import uuid
from datetime import datetime

from soul_protocol.memory.search import relevance_score
from soul_protocol.types import Interaction, MemoryEntry, MemoryType, SomaticMarker


class EpisodicStore:
    """In-memory store for episodic (interaction) memories.

    Episodic memories capture what happened — timestamped records of
    conversations and events. They form the soul's autobiographical memory.

    v0.2.0: Entries can carry somatic markers (emotional context) and
    significance scores. Eviction prefers low-significance entries.
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self._max_entries = max_entries
        self._memories: dict[str, MemoryEntry] = {}

    async def add(self, interaction: Interaction) -> str:
        """Convert an Interaction into a MemoryEntry and store it.

        Returns the generated memory ID.
        """
        memory_id = uuid.uuid4().hex[:12]

        content = f"User: {interaction.user_input}\nAgent: {interaction.agent_output}"

        entry = MemoryEntry(
            id=memory_id,
            type=MemoryType.EPISODIC,
            content=content,
            importance=5,
            created_at=interaction.timestamp,
            entities=[],
            access_timestamps=[interaction.timestamp],
        )

        # Evict if at capacity
        if len(self._memories) >= self._max_entries:
            self._evict_least_significant()

        self._memories[memory_id] = entry
        return memory_id

    async def add_with_psychology(
        self,
        interaction: Interaction,
        somatic: SomaticMarker | None = None,
        significance: float = 0.0,
    ) -> str:
        """Store an interaction with psychology-informed metadata.

        This is the enriched path used by the v0.2.0 observe pipeline.

        Args:
            interaction: The interaction to store.
            somatic: Emotional context from sentiment detection.
            significance: Overall significance score from the attention gate.

        Returns:
            The generated memory ID.
        """
        memory_id = uuid.uuid4().hex[:12]

        content = f"User: {interaction.user_input}\nAgent: {interaction.agent_output}"

        # Map emotional intensity to importance (5-9 range)
        importance = 5
        if somatic and somatic.arousal > 0.3:
            importance = min(9, 5 + int(somatic.arousal * 4))

        entry = MemoryEntry(
            id=memory_id,
            type=MemoryType.EPISODIC,
            content=content,
            importance=importance,
            emotion=somatic.label if somatic else None,
            created_at=interaction.timestamp,
            entities=[],
            somatic=somatic,
            significance=significance,
            access_timestamps=[interaction.timestamp],
        )

        # Evict if at capacity
        if len(self._memories) >= self._max_entries:
            self._evict_least_significant()

        self._memories[memory_id] = entry
        return memory_id

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a single memory by ID, updating access metadata."""
        entry = self._memories.get(memory_id)
        if entry is not None:
            now = datetime.now()
            entry.last_accessed = now
            entry.access_count += 1
            entry.access_timestamps.append(now)
        return entry

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search memories by token-overlap relevance scoring.

        Only entries with a relevance score > 0.0 are returned.
        Results are sorted by relevance (descending), then importance
        (descending), then created_at (most recent first).
        """
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._memories.values():
            score = relevance_score(query, entry.content)
            if score > 0.0:
                scored.append((score, entry))

        scored.sort(key=lambda t: (-t[0], -t[1].importance, -t[1].created_at.timestamp()))
        return [entry for _, entry in scored[:limit]]

    async def remove(self, memory_id: str) -> bool:
        """Remove a memory by ID. Returns True if found and removed."""
        if memory_id in self._memories:
            del self._memories[memory_id]
            return True
        return False

    def entries(self) -> list[MemoryEntry]:
        """Return all episodic memories, sorted by created_at descending."""
        return sorted(
            self._memories.values(),
            key=lambda e: e.created_at.timestamp(),
            reverse=True,
        )

    def recent_contents(self, n: int = 10) -> list[str]:
        """Return content strings of the N most recent entries.

        Used by the attention gate for novelty comparison.

        Args:
            n: Number of recent entries to return.

        Returns:
            List of content strings, most recent first.
        """
        recent = self.entries()[:n]
        return [e.content for e in recent]

    def _evict_least_significant(self) -> None:
        """Remove the least significant entry to make room.

        Prefers evicting entries with low significance, low importance,
        and no recent access. Falls back to oldest if all are equal.
        """
        if not self._memories:
            return

        # Score each entry: lower = more likely to evict
        def eviction_score(entry: MemoryEntry) -> float:
            return entry.significance * 2.0 + entry.importance * 0.1 + entry.access_count * 0.5

        victim_id = min(
            self._memories,
            key=lambda mid: eviction_score(self._memories[mid]),
        )
        del self._memories[victim_id]

    # Legacy alias
    _evict_oldest = _evict_least_significant
