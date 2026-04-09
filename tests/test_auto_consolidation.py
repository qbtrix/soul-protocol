# tests/test_auto_consolidation.py — Tests for auto-scheduled consolidation (F5)
# Created: 2026-03-29 — Verifies that observe() auto-triggers archival and
#   reflection at configurable intervals, and that interaction_count persists
#   through export/awaken cycles.

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction, MemorySettings


def _make_interaction(text: str = "Hello world") -> Interaction:
    return Interaction.from_pair(user_input=text, agent_output="Response")


class TestAutoConsolidation:
    @pytest.mark.asyncio
    async def test_interaction_count_increments(self):
        """Each observe() should increment _interaction_count."""
        soul = await Soul.birth("TestSoul")
        assert soul._interaction_count == 0

        await soul.observe(_make_interaction("First"))
        assert soul._interaction_count == 1

        await soul.observe(_make_interaction("Second"))
        assert soul._interaction_count == 2

    @pytest.mark.asyncio
    async def test_consolidation_triggers_at_interval(self):
        """archive_old_memories should be called at consolidation_interval."""
        soul = await Soul.birth("TestSoul")
        # Set interval to 3 for faster testing
        soul._memory._settings.consolidation_interval = 3

        with patch.object(
            soul._memory, "archive_old_memories", new_callable=AsyncMock
        ) as mock_archive:
            mock_archive.return_value = None

            # Interactions 1, 2 — no trigger
            await soul.observe(_make_interaction("One"))
            await soul.observe(_make_interaction("Two"))
            mock_archive.assert_not_called()

            # Interaction 3 — trigger!
            await soul.observe(_make_interaction("Three"))
            mock_archive.assert_called_once()

    @pytest.mark.asyncio
    async def test_consolidation_skips_without_engine(self):
        """Without a CognitiveEngine, reflect should NOT be called (only archival)."""
        soul = await Soul.birth("TestSoul")
        soul._memory._settings.consolidation_interval = 2
        # No engine set (heuristic only)
        soul._engine = None

        with (
            patch.object(
                soul._memory, "archive_old_memories", new_callable=AsyncMock
            ) as mock_archive,
            patch.object(soul, "reflect", new_callable=AsyncMock) as mock_reflect,
        ):
            mock_archive.return_value = None

            await soul.observe(_make_interaction("One"))
            await soul.observe(_make_interaction("Two"))

            mock_archive.assert_called_once()
            mock_reflect.assert_not_called()

    @pytest.mark.asyncio
    async def test_interval_configurable(self):
        """Different consolidation_interval values should work."""
        soul = await Soul.birth("TestSoul")
        soul._memory._settings.consolidation_interval = 5

        with patch.object(
            soul._memory, "archive_old_memories", new_callable=AsyncMock
        ) as mock_archive:
            mock_archive.return_value = None

            for i in range(4):
                await soul.observe(_make_interaction(f"Msg {i}"))
            mock_archive.assert_not_called()

            await soul.observe(_make_interaction("Msg 4"))
            mock_archive.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_interval_disables(self):
        """consolidation_interval=0 should disable auto-consolidation."""
        soul = await Soul.birth("TestSoul")
        soul._memory._settings.consolidation_interval = 0

        with patch.object(
            soul._memory, "archive_old_memories", new_callable=AsyncMock
        ) as mock_archive:
            mock_archive.return_value = None

            for i in range(25):
                await soul.observe(_make_interaction(f"Msg {i}"))

            mock_archive.assert_not_called()


class TestInteractionCountPersistence:
    @pytest.mark.asyncio
    async def test_count_persists_through_serialize(self):
        """interaction_count should be saved in SoulConfig."""
        soul = await Soul.birth("TestSoul")
        soul._interaction_count = 42

        config = soul.serialize()
        assert config.interaction_count == 42

    @pytest.mark.asyncio
    async def test_count_restored_on_awaken(self, tmp_path):
        """interaction_count should survive export/awaken."""
        soul = await Soul.birth("TestSoul")
        soul._interaction_count = 15

        path = tmp_path / "test.soul"
        await soul.export(str(path))

        restored = await Soul.awaken(str(path))
        assert restored._interaction_count == 15

    @pytest.mark.asyncio
    async def test_default_interval_is_20(self):
        """Default consolidation_interval should be 20."""
        settings = MemorySettings()
        assert settings.consolidation_interval == 20
