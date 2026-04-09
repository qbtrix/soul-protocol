# test_archival.py — Tests for the archival memory tier.
# Created: 2026-03-06 — Covers archive creation, keyword search, date-range
#   queries, get_by_id, count, and edge cases.

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from soul_protocol.runtime.memory.archival import ArchivalMemoryStore, ConversationArchive


@pytest.fixture
def store() -> ArchivalMemoryStore:
    return ArchivalMemoryStore()


def _make_archive(
    id: str,
    summary: str = "A conversation about Python programming",
    key_moments: list[str] | None = None,
    start_offset_hours: int = 0,
    duration_hours: int = 1,
) -> ConversationArchive:
    """Helper to create test archives with controllable timestamps."""
    base = datetime(2026, 3, 1, 10, 0, 0)
    start = base + timedelta(hours=start_offset_hours)
    end = start + timedelta(hours=duration_hours)
    return ConversationArchive(
        id=id,
        start_time=start,
        end_time=end,
        summary=summary,
        key_moments=key_moments or [],
        participants=["user", "soul"],
    )


class TestArchiveCreation:
    def test_archive_conversation_returns_id(self, store: ArchivalMemoryStore):
        archive = _make_archive("arc-001")
        result = store.archive_conversation(archive)
        assert result == "arc-001"

    def test_count_increments(self, store: ArchivalMemoryStore):
        assert store.count() == 0
        store.archive_conversation(_make_archive("arc-001"))
        assert store.count() == 1
        store.archive_conversation(_make_archive("arc-002"))
        assert store.count() == 2

    def test_all_archives_returns_copies(self, store: ArchivalMemoryStore):
        store.archive_conversation(_make_archive("arc-001"))
        archives = store.all_archives()
        assert len(archives) == 1
        assert archives[0].id == "arc-001"


class TestArchiveSearch:
    def test_search_by_summary_keyword(self, store: ArchivalMemoryStore):
        store.archive_conversation(
            _make_archive("arc-001", summary="Discussed Python web frameworks")
        )
        store.archive_conversation(_make_archive("arc-002", summary="Talked about cooking recipes"))

        results = store.search_archives("Python")
        assert len(results) == 1
        assert results[0].id == "arc-001"

    def test_search_by_key_moments(self, store: ArchivalMemoryStore):
        store.archive_conversation(
            _make_archive(
                "arc-001",
                summary="General chat",
                key_moments=["User mentioned they love Rust"],
            )
        )

        results = store.search_archives("Rust")
        assert len(results) == 1
        assert results[0].id == "arc-001"

    def test_search_returns_empty_for_no_match(self, store: ArchivalMemoryStore):
        store.archive_conversation(_make_archive("arc-001", summary="About dogs"))
        results = store.search_archives("quantum physics")
        assert results == []

    def test_search_respects_limit(self, store: ArchivalMemoryStore):
        for i in range(10):
            store.archive_conversation(_make_archive(f"arc-{i:03d}", summary=f"Python topic {i}"))

        results = store.search_archives("Python", limit=3)
        assert len(results) == 3

    def test_search_ranks_by_overlap(self, store: ArchivalMemoryStore):
        store.archive_conversation(_make_archive("arc-001", summary="Python is great"))
        store.archive_conversation(
            _make_archive(
                "arc-002",
                summary="Python web frameworks and Python testing tools",
                start_offset_hours=1,
            )
        )

        results = store.search_archives("Python web")
        # arc-002 has more token overlap with "Python web"
        assert results[0].id == "arc-002"

    def test_search_empty_query(self, store: ArchivalMemoryStore):
        store.archive_conversation(_make_archive("arc-001"))
        results = store.search_archives("")
        assert results == []


class TestDateRangeQueries:
    def test_get_by_date_range_inclusive(self, store: ArchivalMemoryStore):
        store.archive_conversation(_make_archive("arc-001", start_offset_hours=0))
        store.archive_conversation(_make_archive("arc-002", start_offset_hours=5))
        store.archive_conversation(_make_archive("arc-003", start_offset_hours=10))

        base = datetime(2026, 3, 1, 10, 0, 0)
        results = store.get_by_date_range(
            base + timedelta(hours=4),
            base + timedelta(hours=6),
        )
        # Only arc-002 overlaps with hour 4-6
        assert len(results) == 1
        assert results[0].id == "arc-002"

    def test_get_by_date_range_overlapping(self, store: ArchivalMemoryStore):
        # Archive spanning hours 0-2
        store.archive_conversation(_make_archive("arc-001", start_offset_hours=0, duration_hours=2))

        base = datetime(2026, 3, 1, 10, 0, 0)
        # Query for hour 1-3: should overlap with arc-001 (hour 0-2)
        results = store.get_by_date_range(
            base + timedelta(hours=1),
            base + timedelta(hours=3),
        )
        assert len(results) == 1

    def test_get_by_date_range_no_results(self, store: ArchivalMemoryStore):
        store.archive_conversation(_make_archive("arc-001", start_offset_hours=0))

        base = datetime(2026, 3, 1, 10, 0, 0)
        results = store.get_by_date_range(
            base + timedelta(hours=5),
            base + timedelta(hours=6),
        )
        assert results == []

    def test_get_by_date_range_sorted_by_start(self, store: ArchivalMemoryStore):
        store.archive_conversation(_make_archive("arc-003", start_offset_hours=10))
        store.archive_conversation(_make_archive("arc-001", start_offset_hours=0))
        store.archive_conversation(_make_archive("arc-002", start_offset_hours=5))

        base = datetime(2026, 3, 1, 10, 0, 0)
        results = store.get_by_date_range(base, base + timedelta(hours=20))
        assert [r.id for r in results] == ["arc-001", "arc-002", "arc-003"]


class TestGetById:
    def test_get_existing(self, store: ArchivalMemoryStore):
        store.archive_conversation(_make_archive("arc-001"))
        result = store.get_by_id("arc-001")
        assert result is not None
        assert result.id == "arc-001"

    def test_get_missing(self, store: ArchivalMemoryStore):
        assert store.get_by_id("nonexistent") is None
