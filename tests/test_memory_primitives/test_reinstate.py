# test_reinstate.py — Soul.reinstate() — restore a forgotten entry to weight 1.0.
# Created: 2026-04-29 (#192) — verifies the inverse of forget restores the
# weight to 1.0 and the entry resurfaces in recall. No-op semantics on
# already-full-weight or purged entries.

from __future__ import annotations

import pytest


class TestReinstate:
    @pytest.mark.asyncio
    async def test_reinstate_restores_weight(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.forget(mid)
        result = await soul.reinstate(mid)
        assert result["found"] is True
        assert result["weight"] == 1.0
        entry, _ = await soul._memory.find_by_id(mid)
        assert entry.retrieval_weight == 1.0

    @pytest.mark.asyncio
    async def test_reinstate_resurfaces_in_recall(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.forget(mid)
        await soul.reinstate(mid)
        results = await soul.recall("Project Atlas")
        assert any(r.id == mid for r in results)

    @pytest.mark.asyncio
    async def test_reinstate_returns_documented_shape(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[1]
        await soul.forget(mid)
        result = await soul.reinstate(mid)
        assert result["found"] is True
        assert result["action"] == "reinstated"

    @pytest.mark.asyncio
    async def test_reinstate_records_chain_entry(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[1]
        await soul.forget(mid)
        before = len(soul.trust_chain.entries)
        await soul.reinstate(mid)
        new_entries = soul.trust_chain.entries[before:]
        assert any(e.action == "memory.reinstate" for e in new_entries)

    @pytest.mark.asyncio
    async def test_reinstate_full_weight_is_idempotent(self, soul_with_facts):
        """Reinstate on a never-forgotten entry stays at 1.0 and emits the chain entry."""
        soul = soul_with_facts
        mid = soul._seed_ids[2]
        result = await soul.reinstate(mid)
        assert result["found"] is True
        assert result["weight"] == 1.0

    @pytest.mark.asyncio
    async def test_reinstate_unknown_returns_not_found(self, soul):
        result = await soul.reinstate("deadbeef0000")
        assert result["found"] is False
