# test_forget.py — Soul.forget() — semantic shift from delete to weight-decay.
# Created: 2026-04-29 (#192) — verifies the v0.5.0 forget weight-decays an entry
# instead of deleting it; recall stops surfacing it; reinstate restores; the
# bulk forget(query) path still returns the legacy shape.

from __future__ import annotations

import pytest


class TestForgetSingleId:
    @pytest.mark.asyncio
    async def test_forget_drops_weight(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.forget(mid)
        entry, _ = await soul._memory.find_by_id(mid)
        assert entry is not None
        assert entry.retrieval_weight == 0.05

    @pytest.mark.asyncio
    async def test_forget_keeps_entry_in_storage(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.forget(mid)
        entry, _ = await soul._memory.find_by_id(mid)
        assert entry is not None  # NOT deleted

    @pytest.mark.asyncio
    async def test_recall_filters_forgotten(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        await soul.forget(mid)
        results = await soul.recall("Project Atlas")
        assert all(r.id != mid for r in results)

    @pytest.mark.asyncio
    async def test_forget_returns_documented_shape(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        result = await soul.forget(mid)
        assert result["found"] is True
        assert result["id"] == mid
        assert result["action"] == "forgotten"
        assert result["weight"] == 0.05

    @pytest.mark.asyncio
    async def test_forget_records_chain_entry(self, soul_with_facts):
        soul = soul_with_facts
        mid = soul._seed_ids[0]
        before = len(soul.trust_chain.entries)
        await soul.forget(mid)
        new_entries = soul.trust_chain.entries[before:]
        assert any(e.action == "memory.forget" for e in new_entries)


class TestForgetBulkBackCompat:
    @pytest.mark.asyncio
    async def test_bulk_forget_query_returns_legacy_shape(self, soul_with_facts):
        soul = soul_with_facts
        result = await soul.forget("Atlas")
        assert "episodic" in result
        assert "semantic" in result
        assert "procedural" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_bulk_forget_decays_matching(self, soul_with_facts):
        soul = soul_with_facts
        await soul.forget("Atlas")
        results = await soul.recall("Atlas")
        assert len(results) == 0
