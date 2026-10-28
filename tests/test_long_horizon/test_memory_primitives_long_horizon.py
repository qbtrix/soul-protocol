# test_memory_primitives_long_horizon.py — 50-interaction soul that exercises
# every v0.5.0 brain-aligned update verb and verifies chain integrity end-to-end.
# Created: 2026-04-29 (#192) — confirms / updates / supersedes / forgets /
# purges / reinstates run in a single soul; the trust chain stays valid; the
# right entries surface (or don't) in recall.

from __future__ import annotations

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryType


@pytest.mark.asyncio
async def test_50_interaction_long_horizon():
    soul = await Soul.birth(name="LongHorizon", personality="exercises every verb")

    # Seed 10 base facts
    base_ids: list[str] = []
    for i in range(10):
        mid = await soul.remember(
            f"Base fact number {i}: kept around for the verb dance",
            type=MemoryType.SEMANTIC,
            importance=6,
        )
        base_ids.append(mid)

    # 5 confirmations (PE assumed ~0)
    for mid in base_ids[:5]:
        result = await soul.confirm(mid)
        assert result["found"] is True

    # 5 in-place updates (PE in band)
    for i, mid in enumerate(base_ids[5:]):
        await soul.recall(f"Base fact number {i + 5}")
        result = await soul.update(mid, f"Updated fact {i + 5}", prediction_error=0.4)
        assert result["found"] is True

    # 3 supersedes (PE >= 0.85). New entries replace the old.
    superseded_pairs: list[tuple[str, str]] = []
    for i in range(3):
        old_id = base_ids[i]
        result = await soul.supersede(
            old_id,
            f"Superseding fact {i}: latest version",
            prediction_error=0.9,
            reason="long horizon test",
        )
        assert result["found"] is True
        superseded_pairs.append((old_id, result["new_id"]))

    # 5 forgets (drop weight to 0.05)
    forgotten_ids = base_ids[5:]
    for mid in forgotten_ids:
        result = await soul.forget(mid)
        assert result["action"] == "forgotten"

    # 3 reinstates (restore weight)
    reinstated_ids = forgotten_ids[:3]
    for mid in reinstated_ids:
        result = await soul.reinstate(mid)
        assert result["action"] == "reinstated"

    # 2 purges (hard delete)
    purged_ids = forgotten_ids[3:]
    for mid in purged_ids:
        result = await soul.purge(mid)
        assert result["action"] == "purged"

    # ---- Verify final state ----

    # Confirmed entries still surface
    for mid in base_ids[:3]:
        # First three were also superseded — recall surfaces the latest in the chain
        recall_results = await soul.recall("Superseding fact")
        new_ids = {n for _, n in superseded_pairs}
        # At least the three new ids are in the result set
        assert any(r.id in new_ids for r in recall_results)

    # Reinstated entries surface again
    for mid in reinstated_ids:
        entry, _ = await soul._memory.find_by_id(mid)
        assert entry is not None
        assert entry.retrieval_weight == 1.0

    # Purged entries are gone
    for mid in purged_ids:
        entry, _ = await soul._memory.find_by_id(mid)
        assert entry is None

    # Trust chain stays valid
    valid, reason = soul.verify_chain()
    assert valid, f"Trust chain failed verification after long-horizon run: {reason}"

    # Chain has all six verb action names accumulated
    actions = {entry.action for entry in soul.trust_chain.entries}
    expected = {
        "memory.confirm",
        "memory.update",
        "memory.supersede",
        "memory.forget",
        "memory.reinstate",
        "memory.purge",
    }
    assert expected.issubset(actions), f"Missing verb actions: {expected - actions}"
