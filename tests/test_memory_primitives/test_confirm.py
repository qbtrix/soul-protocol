# test_confirm.py — Soul.confirm() — refresh activation on a verified memory.
# Created: 2026-04-29 (#192) — verifies the confirm verb bumps last_access,
# clamps weight back toward 1.0 if it had decayed (but stayed above the
# floor), records the chain entry, and returns the documented shape.

from __future__ import annotations

import pytest


class TestConfirm:
    @pytest.mark.asyncio
    async def test_confirm_bumps_access_metadata(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        before, _ = await soul._memory.find_by_id(mid)
        before_count = before.access_count
        result = await soul.confirm(mid)
        after, _ = await soul._memory.find_by_id(mid)
        assert result["found"] is True
        assert result["action"] == "confirmed"
        assert after.access_count == before_count + 1
        assert after.last_accessed is not None

    @pytest.mark.asyncio
    async def test_confirm_records_chain_entry(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[1]
        before_len = len(soul.trust_chain.entries) if soul.trust_chain else 0
        await soul.confirm(mid)
        after = soul.trust_chain.entries
        assert any(e.action == "memory.confirm" for e in after[before_len:])

    @pytest.mark.asyncio
    async def test_confirm_returns_weight(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        result = await soul.confirm(mid)
        assert result["weight"] == 1.0

    @pytest.mark.asyncio
    async def test_confirm_unknown_id_no_chain_entry(self, soul):
        before_len = len(soul.trust_chain.entries) if soul.trust_chain else 0
        result = await soul.confirm("deadbeef0000")
        assert result["found"] is False
        assert len(soul.trust_chain.entries) == before_len

    @pytest.mark.asyncio
    async def test_confirm_restores_decayed_weight(self, soul_with_facts):
        """A weight that decayed but stayed above the floor is bumped back to 1.0."""
        soul = soul_with_facts
        mid = soul._seed_ids[2]
        entry, _ = await soul._memory.find_by_id(mid)
        entry.retrieval_weight = 0.5  # somehow decayed but still recallable
        result = await soul.confirm(mid)
        assert result["weight"] == 1.0
