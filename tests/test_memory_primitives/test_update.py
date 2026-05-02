# test_update.py — Soul.update() — in-place patch within reconsolidation window.
# Created: 2026-04-29 (#192) — verifies window gating, PE band gating, content
# mutation, chain emission, and the documented dict shape.

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from soul_protocol.runtime.exceptions import (
    PredictionErrorOutOfBandError,
    ReconsolidationWindowClosedError,
)


class TestUpdateWithin:
    @pytest.mark.asyncio
    async def test_update_succeeds_within_window(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        # Open the window via recall
        await soul.recall("Project Atlas")
        result = await soul.update(mid, "Project Atlas ships in July", prediction_error=0.5)
        assert result["found"] is True
        assert result["action"] == "updated"
        entry, _ = await soul._memory.find_by_id(mid)
        assert entry.content == "Project Atlas ships in July"

    @pytest.mark.asyncio
    async def test_update_records_chain_entry(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        before_len = len(soul.trust_chain.entries)
        await soul.update(mid, "Project Atlas ships in July", prediction_error=0.5)
        new_entries = soul.trust_chain.entries[before_len:]
        assert any(e.action == "memory.update" for e in new_entries)

    @pytest.mark.asyncio
    async def test_update_stamps_prediction_error(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        await soul.update(mid, "patch", prediction_error=0.4)
        entry, _ = await soul._memory.find_by_id(mid)
        assert entry.prediction_error == 0.4


class TestUpdateOutsideWindow:
    @pytest.mark.asyncio
    async def test_update_no_recall_raises(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        with pytest.raises(ReconsolidationWindowClosedError):
            await soul.update(mid, "patch", prediction_error=0.5)

    @pytest.mark.asyncio
    async def test_update_after_ttl_expires(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        # Force the window to look stale
        soul._reconsolidation_window[mid] = datetime.now() - timedelta(seconds=3700)
        with pytest.raises(ReconsolidationWindowClosedError):
            await soul.update(mid, "patch", prediction_error=0.5)


class TestUpdatePEBand:
    @pytest.mark.asyncio
    async def test_update_too_low_pe_raises(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        with pytest.raises(PredictionErrorOutOfBandError):
            await soul.update(mid, "patch", prediction_error=0.1)

    @pytest.mark.asyncio
    async def test_update_too_high_pe_raises(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        with pytest.raises(PredictionErrorOutOfBandError):
            await soul.update(mid, "patch", prediction_error=0.9)

    @pytest.mark.asyncio
    async def test_update_empty_patch_raises(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.recall("Project Atlas")
        with pytest.raises(ValueError):
            await soul.update(mid, "", prediction_error=0.5)


class TestUpdateUnknownId:
    @pytest.mark.asyncio
    async def test_update_unknown_returns_not_found(self, soul):
        soul._reconsolidation_window["deadbeef0000"] = datetime.now()
        result = await soul.update("deadbeef0000", "patch", prediction_error=0.5)
        assert result["found"] is False
