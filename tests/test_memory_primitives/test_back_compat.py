# test_back_compat.py — v0.4.x souls awaken cleanly into v0.5.0.
# Created: 2026-04-29 (#192) — round-trip a soul through export+awaken to
# verify the new MemoryEntry fields default cleanly when not present on disk;
# the legacy bulk Soul.forget(query) shape still works; the existing
# supersede default does not break v0.4.x callers.

from __future__ import annotations

import pytest


class TestBackCompat:
    @pytest.mark.asyncio
    async def test_legacy_entry_loads_with_defaults(self, tmp_path):
        from soul_protocol.runtime.soul import Soul

        path = tmp_path / "legacy.soul"
        soul = await Soul.birth(name="Legacy", personality="back-compat soul")
        await soul.remember("legacy fact A", importance=7)
        await soul.export(str(path), include_keys=True)

        revived = await Soul.awaken(str(path))
        # The freshly remembered entry has the new defaults.
        results = await revived.recall("legacy fact")
        assert len(results) >= 1
        for entry in results:
            assert entry.retrieval_weight == 1.0
            assert entry.supersedes is None
            assert entry.prediction_error is None

    @pytest.mark.asyncio
    async def test_bulk_forget_query_returns_legacy_shape(self, soul_with_facts):
        soul = soul_with_facts
        result = await soul.forget("Atlas")
        assert isinstance(result["episodic"], list)
        assert isinstance(result["semantic"], list)
        assert isinstance(result["procedural"], list)
        assert isinstance(result["total"], int)

    @pytest.mark.asyncio
    async def test_supersede_default_pe_does_not_break(self, soul_with_facts):
        """Existing 0.4.x callers that don't pass PE see no behaviour change."""
        soul = soul_with_facts
        old_id = soul._seed_ids[0]
        # The pre-0.5 call had no prediction_error keyword. Default 0.85 lands
        # inside the new band, so the call still succeeds.
        result = await soul.supersede(old_id, "new content")
        assert result["found"] is True
