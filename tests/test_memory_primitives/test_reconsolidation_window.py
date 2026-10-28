# test_reconsolidation_window.py — Window state for the in-place update verb.
# Created: 2026-04-29 (#192) — recall opens windows for every returned entry;
# update enforces the open-window rule; the LRU cap evicts the oldest entry
# when the map crosses 1000.

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from soul_protocol.runtime.exceptions import ReconsolidationWindowClosedError
from soul_protocol.runtime.soul import _RECONSOLIDATION_WINDOW_MAX


class TestWindowOpensOnRecall:
    @pytest.mark.asyncio
    async def test_recall_opens_window(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        assert mid not in soul._reconsolidation_window
        await soul.recall("Project Atlas")
        assert mid in soul._reconsolidation_window

    @pytest.mark.asyncio
    async def test_window_open_for_an_hour(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        # A near-hour window should still be open
        soul._reconsolidation_window[mid] = datetime.now() - timedelta(seconds=3500)
        is_open, _ = soul._is_reconsolidation_window_open(mid)
        assert is_open is True

    @pytest.mark.asyncio
    async def test_window_closes_after_ttl(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        soul._reconsolidation_window[mid] = datetime.now() - timedelta(seconds=3700)
        is_open, _ = soul._is_reconsolidation_window_open(mid)
        assert is_open is False
        assert mid not in soul._reconsolidation_window  # evicted on lookup


class TestUpdateGate:
    @pytest.mark.asyncio
    async def test_update_inside_window(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        result = await soul.update(mid, "patch", prediction_error=0.5)
        assert result["found"] is True

    @pytest.mark.asyncio
    async def test_update_outside_window(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        soul._reconsolidation_window[mid] = datetime.now() - timedelta(seconds=3700)
        with pytest.raises(ReconsolidationWindowClosedError):
            await soul.update(mid, "patch", prediction_error=0.5)


class TestLRUCap:
    @pytest.mark.asyncio
    async def test_lru_evicts_oldest_when_over_cap(self, soul):
        # Force-fill the window past the cap with fake ids
        base = datetime.now() - timedelta(hours=2)
        for i in range(_RECONSOLIDATION_WINDOW_MAX):
            soul._reconsolidation_window[f"old_{i}"] = base + timedelta(seconds=i)
        assert len(soul._reconsolidation_window) == _RECONSOLIDATION_WINDOW_MAX
        # Adding one more should drop the oldest
        soul._open_reconsolidation_window("new_id")
        assert len(soul._reconsolidation_window) == _RECONSOLIDATION_WINDOW_MAX
        assert "old_0" not in soul._reconsolidation_window
        assert "new_id" in soul._reconsolidation_window


class TestWindowResetOnAwaken:
    @pytest.mark.asyncio
    async def test_awaken_starts_with_empty_window(self, tmp_path):
        from soul_protocol.runtime.soul import Soul

        path = tmp_path / "reset.soul"
        soul = await Soul.birth(name="Resetter", personality="test")
        mid = await soul.remember("test", importance=7)
        await soul.recall("test")
        assert mid in soul._reconsolidation_window
        await soul.export(str(path), include_keys=True)

        revived = await Soul.awaken(str(path))
        assert revived._reconsolidation_window == {}
