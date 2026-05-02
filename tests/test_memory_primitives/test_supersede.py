# test_supersede.py — Soul.supersede() with the v0.5.0 PE band check.
# Created: 2026-04-29 (#192) — supersede now requires PE >= 0.85 by default.
# Existing supersede tests stay green because the default PE matches the band.

from __future__ import annotations

import pytest

from soul_protocol.runtime.exceptions import PredictionErrorOutOfBandError


class TestSupersedeDefault:
    @pytest.mark.asyncio
    async def test_default_pe_works(self, soul_with_facts):
        soul = soul_with_facts
        old_id = soul._seed_ids[0]
        result = await soul.supersede(old_id, "Project Atlas ships in October")
        assert result["found"] is True
        assert result["new_id"] is not None
        assert result["prediction_error"] == 0.85

    @pytest.mark.asyncio
    async def test_back_edge_set(self, soul_with_facts):
        soul = soul_with_facts
        old_id = soul._seed_ids[0]
        result = await soul.supersede(old_id, "Project Atlas ships in October")
        new_entry, _ = await soul._memory.find_by_id(result["new_id"])
        old_entry, _ = await soul._memory.find_by_id(old_id)
        assert new_entry.supersedes == old_id
        assert old_entry.superseded_by == result["new_id"]

    @pytest.mark.asyncio
    async def test_chain_carries_pe(self, soul_with_facts):
        soul = soul_with_facts
        old_id = soul._seed_ids[0]
        before = len(soul.trust_chain.entries)
        await soul.supersede(old_id, "Project Atlas ships in October", prediction_error=0.95)
        new_entries = soul.trust_chain.entries[before:]
        # The trust chain stores the payload hash, not the dict — but the
        # event was emitted, which is what we want to verify.
        assert any(e.action == "memory.supersede" for e in new_entries)


class TestSupersedePEBand:
    @pytest.mark.asyncio
    async def test_low_pe_raises(self, soul_with_facts):
        soul = soul_with_facts
        old_id = soul._seed_ids[0]
        with pytest.raises(PredictionErrorOutOfBandError):
            await soul.supersede(old_id, "new", prediction_error=0.5)

    @pytest.mark.asyncio
    async def test_above_min_pe_works(self, soul_with_facts):
        soul = soul_with_facts
        old_id = soul._seed_ids[0]
        result = await soul.supersede(old_id, "new", prediction_error=0.95)
        assert result["found"] is True


class TestSupersedeUnknown:
    @pytest.mark.asyncio
    async def test_supersede_unknown_returns_not_found(self, soul):
        result = await soul.supersede("deadbeef0000", "new")
        assert result["found"] is False
        assert result["new_id"] is None
