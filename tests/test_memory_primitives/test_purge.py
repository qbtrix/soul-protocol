# test_purge.py — Soul.purge() — explicit hard delete with audit hash.
# Created: 2026-04-29 (#192) — purge() is the GDPR/safety path that removes
# the entry, records the prior payload hash, and prevents reinstate.

from __future__ import annotations

import pytest


class TestPurge:
    @pytest.mark.asyncio
    async def test_purge_removes_entry(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.purge(mid)
        entry, _ = await soul._memory.find_by_id(mid)
        assert entry is None

    @pytest.mark.asyncio
    async def test_purge_returns_documented_shape(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        result = await soul.purge(mid)
        assert result["found"] is True
        assert result["action"] == "purged"
        assert "prior_payload_hash" in result
        assert len(result["prior_payload_hash"]) == 64  # sha256 hex

    @pytest.mark.asyncio
    async def test_purge_records_chain_entry(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        before = len(soul.trust_chain.entries)
        await soul.purge(mid)
        new_entries = soul.trust_chain.entries[before:]
        assert any(e.action == "memory.purge" for e in new_entries)

    @pytest.mark.asyncio
    async def test_purge_then_reinstate_is_no_op(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.purge(mid)
        result = await soul.reinstate(mid)
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_purge_unknown_returns_not_found(self, soul):
        result = await soul.purge("deadbeef0000")
        assert result["found"] is False
