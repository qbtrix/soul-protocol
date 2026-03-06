# memory/archival.py — ArchivalMemoryStore for deep conversation archives.
# Created: 2026-03-06 — New archival memory tier for compressed conversation
#   storage. Supports keyword search across summaries and key_moments,
#   date-range queries, and basic CRUD operations.

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConversationArchive(BaseModel):
    """Compressed archive of a conversation session."""

    id: str
    start_time: datetime
    end_time: datetime
    summary: str  # LLM-generated or rule-based summary
    key_moments: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)  # IDs of extracted memories
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArchivalMemoryStore:
    """Deep storage for full conversation archives.

    Stores compressed conversation sessions with searchable summaries,
    key moments, and date-range filtering. Designed for long-term
    retention without consuming active context.
    """

    def __init__(self) -> None:
        self._archives: list[ConversationArchive] = []

    def archive_conversation(self, archive: ConversationArchive) -> str:
        """Store a conversation archive.

        Args:
            archive: The ConversationArchive to store.

        Returns:
            The archive ID.
        """
        self._archives.append(archive)
        return archive.id

    def search_archives(self, query: str, limit: int = 5) -> list[ConversationArchive]:
        """Search archives by keyword overlap in summary and key_moments.

        Uses token-level matching: the query is tokenized and compared against
        the summary text and each key moment. Archives are ranked by the number
        of matching tokens (descending), then by end_time (most recent first).

        Args:
            query: Space-separated keywords to search for.
            limit: Maximum number of results to return.

        Returns:
            List of matching ConversationArchive objects, ranked by relevance.
        """
        query_tokens = set(query.lower().split())
        if not query_tokens:
            return []

        scored: list[tuple[int, ConversationArchive]] = []

        for archive in self._archives:
            # Build searchable text from summary + key moments
            searchable = archive.summary.lower()
            for moment in archive.key_moments:
                searchable += " " + moment.lower()

            archive_tokens = set(searchable.split())
            overlap = len(query_tokens & archive_tokens)

            if overlap > 0:
                scored.append((overlap, archive))

        # Sort by overlap descending, then by recency
        scored.sort(key=lambda t: (-t[0], -t[1].end_time.timestamp()))
        return [archive for _, archive in scored[:limit]]

    def get_by_date_range(
        self, start: datetime, end: datetime
    ) -> list[ConversationArchive]:
        """Get all archives whose sessions overlap with the given date range.

        An archive overlaps if its start_time is before the range end AND
        its end_time is after the range start.

        Args:
            start: Start of the date range (inclusive).
            end: End of the date range (inclusive).

        Returns:
            List of matching archives, sorted by start_time ascending.
        """
        results = [
            archive
            for archive in self._archives
            if archive.start_time <= end and archive.end_time >= start
        ]
        results.sort(key=lambda a: a.start_time)
        return results

    def get_by_id(self, archive_id: str) -> ConversationArchive | None:
        """Look up a single archive by its ID."""
        for archive in self._archives:
            if archive.id == archive_id:
                return archive
        return None

    def count(self) -> int:
        """Return the total number of stored archives."""
        return len(self._archives)

    def all_archives(self) -> list[ConversationArchive]:
        """Return a copy of all stored archives."""
        return list(self._archives)
