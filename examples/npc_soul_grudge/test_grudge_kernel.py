# test_grudge_kernel.py — Proof that the npc.soul grudge kernel holds a grudge
#   across a real .soul export -> awaken round-trip.
#
# Created: 2026-07-01 (experiment/npc-soul-grudge-kernel) — pytest-asyncio tests
#   asserting the whole loop against the REAL Soul (no mocks, no LLM, no
#   network):
#     * test_bond_weakens_and_grudge_builds — after 2+ wrongs the per-player
#       bond strictly decreased, grievances are stored, level == "GRUDGING",
#       and react() returns the hostile branch citing a remembered wrong.
#     * test_grudge_survives_soul_roundtrip (THE KILLER TEST) — export the soul
#       to a .soul file, awaken a FRESH kernel from that file, and the grudge +
#       grievances + weakened bond all persist.
#     * test_grudge_is_player_specific — a different player with no wrongs gets
#       level "NONE" and a warm reaction, proving the grudge isn't global.
#     * test_neutral_only_never_grudges — neutral interactions alone never
#       produce a grudge and never weaken the bond below its start.
#
# Run:  uv run pytest examples/npc_soul_grudge/test_grudge_kernel.py -v

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the sibling grudge.py importable whether pytest is run from the repo
# root or from inside the folder.
sys.path.insert(0, str(Path(__file__).parent))

from grudge import GRUDGING, NONE, SLIGHTED, GrudgeKernel  # noqa: E402

pytestmark = pytest.mark.asyncio

RAGNAR = "did:soul:player:ragnar"
ASTRID = "did:soul:player:astrid"

# Starting bond strength for a brand-new per-player bond (Soul default).
START_BOND = 50.0


async def _wronged_kernel() -> GrudgeKernel:
    """Bjorn after Ragnar greets, trades, betrays, and steals."""
    kernel = await GrudgeKernel.birth()
    await kernel.record(RAGNAR, "Good morning, butcher!", kind="neutral")
    await kernel.record(RAGNAR, "Two shanks please.", kind="neutral")
    await kernel.record(RAGNAR, "I framed you to the guards.", kind="betrayal")
    await kernel.record(RAGNAR, "*steals sausages*", kind="theft")
    return kernel


async def test_bond_weakens_and_grudge_builds() -> None:
    kernel = await _wronged_kernel()

    # Bond strictly decreased from the starting point.
    bond = kernel.bond_strength(RAGNAR)
    assert bond < START_BOND, f"expected bond < {START_BOND}, got {bond}"

    # Grievances were stored (betrayal + theft = 2).
    grievances = await kernel.grievances(RAGNAR)
    assert len(grievances) >= 2
    kinds = {g.kind for g in grievances}
    assert "betrayal" in kinds
    assert "theft" in kinds

    # Level is GRUDGING.
    assert await kernel.grudge_level(RAGNAR) == GRUDGING

    # react() returns the hostile branch and cites a specific remembered wrong.
    reaction = await kernel.react(RAGNAR, player_name="Ragnar")
    assert "gall to show your face" in reaction
    assert ("betrayed" in reaction) or ("stole" in reaction) or ("mocked" in reaction)


async def test_grudge_survives_soul_roundtrip(tmp_path: Path) -> None:
    """THE KILLER TEST: export -> awaken preserves the grudge."""
    kernel = await _wronged_kernel()

    bond_before = kernel.bond_strength(RAGNAR)
    level_before = await kernel.grudge_level(RAGNAR)
    count_before = len(await kernel.grievances(RAGNAR))
    assert level_before == GRUDGING

    # Export to a real .soul file, then drop the in-memory object.
    soul_path = tmp_path / "bjorn.soul"
    await kernel.export(str(soul_path))
    assert soul_path.exists() and soul_path.stat().st_size > 0
    del kernel

    # Awaken a completely fresh kernel from the file.
    reborn = await GrudgeKernel.awaken(str(soul_path))

    # The grudge, the grievances, and the weakened bond all came back.
    assert await reborn.grudge_level(RAGNAR) == GRUDGING
    grievances = await reborn.grievances(RAGNAR)
    assert len(grievances) == count_before >= 2
    assert {g.kind for g in grievances} == {"betrayal", "theft"}

    bond_after = reborn.bond_strength(RAGNAR)
    assert bond_after == pytest.approx(bond_before), (
        f"bond changed across round-trip: {bond_before} -> {bond_after}"
    )
    assert bond_after < START_BOND

    # And he's still hostile, still naming the wrongs, in the new session.
    reaction = await reborn.react(RAGNAR, player_name="Ragnar")
    assert "gall to show your face" in reaction
    assert ("betrayed" in reaction) or ("stole" in reaction)


async def test_grudge_is_player_specific(tmp_path: Path) -> None:
    """A player Bjorn was never wronged by stays warm — before AND after a
    round-trip — proving the grudge is per-player, not global."""
    kernel = await _wronged_kernel()
    # Astrid only ever greets him.
    await kernel.record(ASTRID, "Hello, first time here!", kind="neutral")

    assert await kernel.grudge_level(ASTRID) == NONE
    assert len(await kernel.grievances(ASTRID)) == 0

    warm = await kernel.react(ASTRID, player_name="Astrid")
    assert "Welcome to my stall" in warm
    assert "gall to show your face" not in warm

    # Ragnar is GRUDGING at the same time — two players, two relationships.
    assert await kernel.grudge_level(RAGNAR) == GRUDGING

    # Survives the round-trip too.
    soul_path = tmp_path / "bjorn.soul"
    await kernel.export(str(soul_path))
    reborn = await GrudgeKernel.awaken(str(soul_path))
    assert await reborn.grudge_level(ASTRID) == NONE
    assert await reborn.grudge_level(RAGNAR) == GRUDGING


async def test_neutral_only_never_grudges() -> None:
    """Neutral interactions never plant a grudge and never weaken the bond."""
    kernel = await GrudgeKernel.birth()
    await kernel.record(ASTRID, "Morning!", kind="neutral")
    await kernel.record(ASTRID, "Nice weather.", kind="neutral")
    await kernel.record(ASTRID, "A pound of beef, please.", kind="neutral")

    assert await kernel.grudge_level(ASTRID) == NONE
    assert len(await kernel.grievances(ASTRID)) == 0
    # Neutral observes strengthen (never weaken) the bond.
    assert kernel.bond_strength(ASTRID) >= START_BOND


async def test_single_insult_is_only_slighted() -> None:
    """One low-severity wrong yields SLIGHTED, not full GRUDGING — the levels
    are graded, not binary."""
    kernel = await GrudgeKernel.birth()
    await kernel.record(RAGNAR, "Your apron is filthy, old man.", kind="insult")

    assert await kernel.grudge_level(RAGNAR) == SLIGHTED
    reaction = await kernel.react(RAGNAR, player_name="Ragnar")
    assert "smile thins" in reaction
