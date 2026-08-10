# memory/episodic.py — EpisodicStore for timestamped interaction memories.
# Updated: 2026-05-29 — Added add_entry() to store a pre-built MemoryEntry
#   VERBATIM (fixes #234 + sibling importance-drop bug). The Interaction-based
#   add()/add_with_psychology() builders that wrap content in the
#   "User: ...\nAgent: ..." envelope are left untouched — observe relies on them.
# Updated: 2026-07-24 (#247) — search() takes a relevance_floor and gates
#   candidates via passes_relevance_floor() instead of a bare `score > 0.0`.
#   Default floor 0.0 keeps the historical "any overlap" behaviour; a positive
#   floor drops weak matches at the store level.
# Updated: 2026-03-29 — Filter archived entries from search() results (F2).
# Updated: 2026-03-13 — Added update_entry() public method for updating fields
#   on stored entries (replaces direct _memories dict access from manager.py).
# Updated: 2026-03-10 — Added search_and_delete() and delete_before() for
#   GDPR-compliant targeted and time-based memory deletion.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Updated: v0.2.0 — Store somatic markers and significance scores on entries.
#   Eviction now considers activation (significance + access) not just age.
#   Added store_with_psychology() for the enriched observe pipeline.
# Updated: Added structured logging for memory eviction events.

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from soul_protocol.runtime.memory.search import (
    DEFAULT_RELEVANCE_FLOOR,
    passes_relevance_floor,
    relevance_score,
)
from soul_protocol.runtime.types import Interaction, MemoryEntry, MemoryType, SomaticMarker

logger = logging.getLogger(__name__)


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

    async def add_entry(self, entry: MemoryEntry) -> str:
        """Store a pre-built :class:`MemoryEntry` VERBATIM.

        Unlike :meth:`add` and :meth:`add_with_psychology` — which build a
        ``"User: ...\\nAgent: ..."`` envelope from an :class:`Interaction` and
        hardcode importance — this stores the entry exactly as the caller
        constructed it. Used by the blunt ``Soul.remember(type=EPISODIC)`` /
        ``Soul.note(...)`` path so content, importance, emotion, entities,
        somatic, significance, visibility, scope, domain, and user_id all
        survive the write (fixes #234 and the sibling importance-drop bug).

        Generates an id when ``entry.id`` is empty, forces
        ``type = MemoryType.EPISODIC``, seeds ``access_timestamps`` from
        ``created_at`` when empty, and runs the same capacity/eviction logic
        as :meth:`add`.

        Returns the stored memory ID.
        """
        entry.type = MemoryType.EPISODIC
        if not entry.id:
            entry.id = uuid.uuid4().hex[:12]
        if not entry.access_timestamps:
            entry.access_timestamps = [entry.created_at]

        # Evict if at capacity (mirrors add()).
        if len(self._memories) >= self._max_entries:
            self._evict_least_significant()

        self._memories[entry.id] = entry
        return entry.id

    def update_entry(self, memory_id: str, **kwargs) -> bool:
        """Update fields on an existing episodic entry.

        Args:
            memory_id: The ID of the entry to update.
            **kwargs: Field names and values to set on the entry.
                      Unknown fields (not present on the entry) are ignored.

        Returns:
            True if the entry was found and updated, False if not found.
        """
        if memory_id in self._memories:
            entry = self._memories[memory_id]
            for key, value in kwargs.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            return True
        return False

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a single memory by ID, updating access metadata."""
        entry = self._memories.get(memory_id)
        if entry is not None:
            now = datetime.now()
            entry.last_accessed = now
            entry.access_count += 1
            entry.access_timestamps.append(now)
        return entry

    async def search(
        self,
        query: str,
        limit: int = 10,
        relevance_floor: float = DEFAULT_RELEVANCE_FLOOR,
    ) -> list[MemoryEntry]:
        """Search memories by token-overlap relevance scoring.

        Only entries whose relevance score clears ``relevance_floor`` are
        returned. The default floor of 0.0 keeps the historical behaviour:
        any positive overlap earns a slot. A positive floor turns the gate
        graded — a weak match below the floor is dropped.

        Results are sorted by relevance (descending), then importance
        (descending), then created_at (most recent first).
        """
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._memories.values():
            if entry.archived:
                continue
            score = relevance_score(query, entry.content)
            if passes_relevance_floor(score, relevance_floor):
                scored.append((score, entry))

        scored.sort(key=lambda t: (-t[0], -t[1].importance, -t[1].created_at.timestamp()))
        return [entry for _, entry in scored[:limit]]

    async def remove(self, memory_id: str) -> bool:
        """Remove a memory by ID. Returns True if found and removed."""
        if memory_id in self._memories:
            del self._memories[memory_id]
            return True
        return False

    def count(self) -> int:
        """Return the number of stored episodic memories."""
        return len(self._memories)

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

    async def search_and_delete(self, query: str) -> list[str]:
        """Search for memories matching a query and delete them.

        Uses the same token-overlap scoring as search(). All matches
        with a relevance score > 0.0 are removed.

        Args:
            query: The search query to match against memory content.

        Returns:
            List of deleted memory IDs.
        """
        matches = await self.search(query, limit=len(self._memories))
        deleted_ids = [entry.id for entry in matches]
        for mid in deleted_ids:
            del self._memories[mid]
        return deleted_ids

    async def delete_before(self, timestamp: datetime) -> list[str]:
        """Delete all memories created before a given timestamp.

        Args:
            timestamp: The cutoff datetime. Memories older than this
                       are deleted.

        Returns:
            List of deleted memory IDs.
        """
        to_delete = [mid for mid, entry in self._memories.items() if entry.created_at < timestamp]
        for mid in to_delete:
            del self._memories[mid]
        return to_delete

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
        logger.debug("Episodic memory evicted: id=%s", victim_id)
        del self._memories[victim_id]

    # Legacy alias
    _evict_oldest = _evict_least_significant
