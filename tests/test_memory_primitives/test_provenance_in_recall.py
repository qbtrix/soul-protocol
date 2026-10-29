# test_provenance_in_recall.py — Recall provenance walks the supersedes chain.
# Created: 2026-04-29 (#192) — verifies that recall builds the full chain in
# Soul.last_recall_provenance for entries that have a supersedes back-edge,
# and that include_superseded=True surfaces older entries with their chain.

from __future__ import annotations

import pytest


class TestProvenance:
    @pytest.mark.asyncio
    async def test_chain_built_for_superseded_entry(self, soul_with_facts):
        soul = soul_with_facts
        first_id = soul._seed_ids[0]
        # Two-hop supersede chain: first -> mid -> latest
        first_super = await soul.supersede(
            first_id, "Project Atlas ships in July", reason="date slipped"
        )
        latest = await soul.supersede(
            first_super["new_id"],
            "Project Atlas ships in October",
            reason="slipped again",
        )
        # Recall the latest entry — it should carry the full chain back to first.
        results = await soul.recall("Project Atlas")
        latest_id = latest["new_id"]
        assert any(r.id == latest_id for r in results)
        chain = soul.last_recall_provenance.get(latest_id)
        assert chain is not None
        assert len(chain) == 2
        # First hop targets the mid entry
        assert chain[0]["target_id"] == first_super["new_id"]
        # Second hop targets the original entry
        assert chain[1]["target_id"] == first_id

    @pytest.mark.asyncio
    async def test_no_chain_for_fresh_entry(self, soul_with_facts):
        soul = soul_with_facts
        await soul.recall("Aria")
        # Fresh entries with no supersedes back-edge produce no provenance.
        # The provenance map is keyed only by entries that have a chain.
        for _, chain in soul.last_recall_provenance.items():
            assert chain  # if we keyed it, the chain is non-empty

    @pytest.mark.asyncio
    async def test_include_superseded_surfaces_old(self, soul_with_facts):
        """include_superseded=True returns the older versions alongside the latest."""
        soul = soul_with_facts
        first_id = soul._seed_ids[0]
        await soul.supersede(first_id, "Project Atlas ships in July", reason="moved")
        # Default recall hides the old entry
        default_results = await soul.recall("Project Atlas ships in May")
        assert all(r.id != first_id for r in default_results)
        # include_superseded=True surfaces it
        wide = await soul.recall("Project Atlas ships in May", include_superseded=True)
        assert any(r.id == first_id for r in wide)
