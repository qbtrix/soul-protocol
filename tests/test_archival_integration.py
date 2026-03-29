# tests/test_archival_integration.py — Tests for archival memory wiring (F2)
# Created: 2026-03-29 — Verifies archive_old_memories() compresses old episodic
#   entries into ConversationArchive objects, marks them archived, persists through
#   to_dict/from_dict, and integrates with recall filtering.

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from soul_protocol.runtime.memory.manager import MemoryManager
from soul_protocol.runtime.types import (
    CoreMemory,
    Interaction,
    MemoryEntry,
    MemorySettings,
    MemoryType,
)


@pytest.fixture
def manager() -> MemoryManager:
    return MemoryManager(core=CoreMemory(), settings=MemorySettings())


def _make_old_entry(content: str, hours_ago: float, importance: int = 5) -> MemoryEntry:
    """Create an episodic memory entry backdated by hours_ago."""
    return MemoryEntry(
        id=uuid.uuid4().hex[:12],
        type=MemoryType.EPISODIC,
        content=content,
        importance=importance,
        created_at=datetime.now() - timedelta(hours=hours_ago),
    )


class TestArchiveOldMemories:
    @pytest.mark.asyncio
    async def test_creates_archive_from_old_entries(self, manager: MemoryManager):
        """archive_old_memories() creates a ConversationArchive from old episodics."""
        # Add 4 old entries (> 48 hours old)
        for i in range(4):
            entry = _make_old_entry(f"Old memory number {i}. Some details.", hours_ago=72)
            manager._episodic._memories[entry.id] = entry

        archive = await manager.archive_old_memories(max_age_hours=48.0)

        assert archive is not None
        assert len(archive.memory_refs) == 4
        assert "Old memory number" in archive.summary
        assert manager.archival.count() == 1

    @pytest.mark.asyncio
    async def test_marks_entries_archived(self, manager: MemoryManager):
        """Archived entries should have archived=True."""
        for i in range(3):
            entry = _make_old_entry(f"Fact {i}. Extra text.", hours_ago=72)
            manager._episodic._memories[entry.id] = entry

        await manager.archive_old_memories(max_age_hours=48.0)

        for entry in manager._episodic.entries():
            assert entry.archived is True

    @pytest.mark.asyncio
    async def test_skips_when_too_few(self, manager: MemoryManager):
        """Should skip archival when fewer than 3 old entries."""
        entry = _make_old_entry("Lonely memory. Details.", hours_ago=72)
        manager._episodic._memories[entry.id] = entry

        archive = await manager.archive_old_memories(max_age_hours=48.0)

        assert archive is None
        assert manager.archival.count() == 0

    @pytest.mark.asyncio
    async def test_ignores_recent_entries(self, manager: MemoryManager):
        """Entries newer than max_age_hours should not be archived."""
        # 2 old entries (not enough) + 3 recent entries
        for i in range(2):
            old = _make_old_entry(f"Old {i}. Text.", hours_ago=72)
            manager._episodic._memories[old.id] = old
        for i in range(3):
            recent = _make_old_entry(f"Recent {i}. Text.", hours_ago=1)
            manager._episodic._memories[recent.id] = recent

        archive = await manager.archive_old_memories(max_age_hours=48.0)

        assert archive is None  # Only 2 old entries, not enough

    @pytest.mark.asyncio
    async def test_does_not_rearchive(self, manager: MemoryManager):
        """Already-archived entries should not be archived again."""
        for i in range(4):
            entry = _make_old_entry(f"Memory {i}. Details.", hours_ago=72)
            manager._episodic._memories[entry.id] = entry

        # Archive once
        archive1 = await manager.archive_old_memories(max_age_hours=48.0)
        assert archive1 is not None

        # Try again — all are now archived
        archive2 = await manager.archive_old_memories(max_age_hours=48.0)
        assert archive2 is None
        assert manager.archival.count() == 1

    @pytest.mark.asyncio
    async def test_key_moments_from_high_importance(self, manager: MemoryManager):
        """Key moments should come from entries with importance >= 7."""
        for i in range(3):
            entry = _make_old_entry(f"Normal fact {i}. More.", hours_ago=72, importance=4)
            manager._episodic._memories[entry.id] = entry
        important = _make_old_entry("Critical discovery. Big impact.", hours_ago=72, importance=9)
        manager._episodic._memories[important.id] = important

        archive = await manager.archive_old_memories(max_age_hours=48.0)

        assert archive is not None
        assert len(archive.key_moments) == 1
        assert "Critical discovery" in archive.key_moments[0]


class TestArchivalRecallFiltering:
    @pytest.mark.asyncio
    async def test_recall_excludes_archived_entries(self, manager: MemoryManager):
        """Archived episodic entries should not appear in recall results."""
        for i in range(4):
            entry = _make_old_entry(f"Searchable alpha fact {i}. Details.", hours_ago=72)
            manager._episodic._memories[entry.id] = entry

        # Verify they show up before archival
        pre_results = await manager.recall("alpha")
        assert len(pre_results) >= 4

        # Archive them
        await manager.archive_old_memories(max_age_hours=48.0)

        # Verify they no longer show up
        post_results = await manager.recall("alpha")
        assert len(post_results) == 0


class TestArchivalPersistence:
    @pytest.mark.asyncio
    async def test_archives_persist_through_to_dict(self, manager: MemoryManager):
        """Archives should be included in to_dict() output."""
        for i in range(3):
            entry = _make_old_entry(f"Persist test {i}. Data.", hours_ago=72)
            manager._episodic._memories[entry.id] = entry

        await manager.archive_old_memories(max_age_hours=48.0)
        data = manager.to_dict()

        assert "archives" in data
        assert len(data["archives"]) == 1
        assert "Persist test" in data["archives"][0]["summary"]

    @pytest.mark.asyncio
    async def test_archives_restored_from_dict(self, manager: MemoryManager):
        """Archives should be restored via from_dict()."""
        for i in range(3):
            entry = _make_old_entry(f"Restore test {i}. Info.", hours_ago=72)
            manager._episodic._memories[entry.id] = entry

        await manager.archive_old_memories(max_age_hours=48.0)
        data = manager.to_dict()

        restored = MemoryManager.from_dict(data, settings=MemorySettings())
        assert restored.archival.count() == 1
        archives = restored.archival.all_archives()
        assert "Restore test" in archives[0].summary
