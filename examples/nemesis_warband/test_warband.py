# test_warband.py — Deterministic proof of the Nemesis-System warband engine
#   (NEM-1 warband.py + NEM-2 nemesis_director.py), all on the unchanged
#   soul_protocol.profiles.game package.
#
# Created: 2026-07-05 (feat/nemesis-warband) — pytest-asyncio tests against the
#   REAL Soul (no mocks, no LLM, no network — templated dialogue engine only).
#   asyncio_mode = "auto" in pyproject, so no per-test marker is needed.
#   Coverage:
#     * forge builds N members with the right ranks and shows the seeded
#       NPC<->NPC rivalries on the board.
#     * clash player_won -> the member's grudge rises and it is demoted; a grunt
#       is KILLED and a rival is promoted to fill the gap.
#     * clash member_won -> the member RISES a rank and records a fresh grudge.
#     * a promotion triggers a same-rank rival's JEALOUSY grudge (the rival's
#       board entry now lists the riser).
#     * recruit reads the player's PORTABLE reputation: after the player wrongs
#       members, a fresh recruit's first line cites the notoriety (NOTORIOUS).
#     * director revenge selection == the highest-grudge alive member; RELAX
#       suppresses revenge; a power struggle promotes the winner and updates the
#       loser's rank.
#     * export/awaken a MEMBER round-trips its grudge (a portable nemesis).
#
# Run:  uv run pytest examples/nemesis_warband/test_warband.py -v

from __future__ import annotations

from pathlib import Path

import pytest

from examples.nemesis_warband import Warband, WarbandDirector
from examples.nemesis_warband.warband import CAPTAIN, GRUNT, WARLORD
from soul_protocol.profiles.game import (
    GRUDGING,
    NOTORIOUS,
    PEAK,
    RELAX,
    SLIGHTED,
    DirectorEngine,
    GrudgeKernel,
    PlayerSoul,
)

pytestmark = pytest.mark.asyncio

SEED = 1337


async def _player(name: str = "Talion") -> PlayerSoul:
    return await PlayerSoul.birth(name=name)


# ---------------------------------------------------------------------------
# forge
# ---------------------------------------------------------------------------


async def test_forge_builds_members_with_ranks_and_seeded_rivalries() -> None:
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    # N members, exactly one Warlord, at least one Captain, the rest Grunts.
    assert len(wb.members) == 6
    ranks = [m.rank for m in wb.members]
    assert ranks.count(WARLORD) == 1
    assert ranks.count(CAPTAIN) >= 1
    assert ranks.count(GRUNT) >= 1

    # The board renders the seeded NPC<->NPC rivalries: at least one member holds
    # a grudge against another member (rivalries list is non-empty somewhere).
    board = await wb.board()
    assert len(board) == 6
    total_rivalries = sum(len(row["rivalries"]) for row in board)
    assert total_rivalries >= 2, f"expected >=2 seeded rivalries, board={board}"

    # Every rivalry name is a real member name (NPC<->NPC, not the player).
    member_names = {m.name for m in wb.members}
    for row in board:
        for rival in row["rivalries"]:
            assert rival in member_names
            assert rival != row["name"]  # nobody rivals themself


# ---------------------------------------------------------------------------
# clash — player wins
# ---------------------------------------------------------------------------


async def test_clash_player_won_raises_grudge_and_demotes_captain() -> None:
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    captain = next(m for m in wb.members if m.rank == CAPTAIN)
    start_rank = captain.rank
    start_bond = captain.kernel.bond_strength(player.did)

    beat = await wb.clash(captain.did, player.did, player_won=True, note="in the pit")

    assert beat["outcome"] == "player_won"
    assert beat["rank_change"] == -1
    assert not beat["killed"]
    assert captain.rank == start_rank - 1  # demoted a rank
    assert captain.alive

    # The humiliation is remembered: a grievance exists and the bond dropped.
    grievances = await captain.kernel.grievances(player.did)
    assert len(grievances) >= 1
    assert captain.kernel.bond_strength(player.did) < start_bond


async def test_clash_player_won_kills_grunt_and_promotes_a_rival() -> None:
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    grunt = next(m for m in wb.members if m.rank == GRUNT)
    # A surviving member who is eligible to be promoted (alive, below Warlord).
    promotable_before = {
        m.did: m.rank for m in wb.members if m.alive and m.did != grunt.did and m.rank < WARLORD
    }

    beat = await wb.clash(grunt.did, player.did, player_won=True, note="skull-first")

    assert beat["outcome"] == "player_won"
    assert beat["killed"] is True
    assert grunt.alive is False

    # Exactly one surviving member was promoted to close ranks.
    promoted = [
        m
        for m in wb.members
        if m.did in promotable_before and m.rank == promotable_before[m.did] + 1
    ]
    assert len(promoted) == 1, f"expected exactly one promotion, got {[m.name for m in promoted]}"


# ---------------------------------------------------------------------------
# clash — member wins
# ---------------------------------------------------------------------------


async def test_clash_member_won_rises_and_records_grudge() -> None:
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    grunt = next(m for m in wb.members if m.rank == GRUNT)
    start_rank = grunt.rank

    beat = await wb.clash(grunt.did, player.did, player_won=False, note="left them bleeding")

    assert beat["outcome"] == "member_won"
    assert beat["rank_change"] == 1
    assert grunt.rank == start_rank + 1  # rose a rank
    assert grunt.alive

    # The win is banked as a fresh grudge toward the player.
    grievances = await grunt.kernel.grievances(player.did)
    assert len(grievances) >= 1


async def test_member_promotion_triggers_rival_jealousy_grudge() -> None:
    """A member rising a rank makes a same-rank rival record a jealousy grudge —
    the rival's board entry must then list the riser as a rivalry."""
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    # Pick a Grunt to promote; there are several Grunts, so a same-rank peer
    # exists to get jealous.
    grunts = [m for m in wb.members if m.rank == GRUNT and m.alive]
    assert len(grunts) >= 2
    riser = grunts[0]

    beat = await wb.clash(riser.did, player.did, player_won=False, note="climbed a rung")
    assert beat["rank_change"] == 1
    jealous_name = beat["rivalry_triggered"]
    assert jealous_name is not None, "a same-rank rival should have gotten jealous"

    # The jealous rival's board row now lists the riser among its rivalries.
    board = await wb.board()
    jealous_row = next(row for row in board if row["name"] == jealous_name)
    assert riser.name in jealous_row["rivalries"], (
        f"{jealous_name} should hold a jealousy grudge against {riser.name}; row={jealous_row}"
    )


# ---------------------------------------------------------------------------
# recruit — reads portable reputation
# ---------------------------------------------------------------------------


async def test_recruit_reads_player_reputation() -> None:
    """After the player wrongs members, a fresh recruit's FIRST line already
    reacts to the player's notoriety (reputation flows in from the player.soul,
    unmet)."""
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    # The player wrongs two members (two clash wins => two deeds on player.soul
    # => NOTORIOUS). Two distinct grunts so both clashes land as fresh deeds.
    grunts = [m for m in wb.members if m.rank == GRUNT]
    await wb.clash(grunts[0].did, player.did, player_won=True, note="one")
    await wb.clash(grunts[1].did, player.did, player_won=True, note="two")

    reputation_deeds, notoriety = await player.reputation()
    assert notoriety == NOTORIOUS
    assert reputation_deeds  # non-empty portable reputation

    rec = await wb.recruit("Zog", "the Newcomer")
    assert rec["notoriety"] == NOTORIOUS
    # The recruit's first line is the NOTORIOUS reputation branch, which names
    # the recruit and cites hearsay about the player.
    assert "Zog" in rec["first_line"]
    assert ("Word travels" in rec["first_line"]) or ("know who you are" in rec["first_line"])


# ---------------------------------------------------------------------------
# director — revenge selection + RELAX suppression
# ---------------------------------------------------------------------------


async def test_director_revenge_selects_highest_grudge_alive_member() -> None:
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    grunts = [m for m in wb.members if m.rank == GRUNT and m.alive]
    angriest, milder = grunts[0], grunts[1]

    # The angriest member wins TWICE => 2 grievances => GRUDGING, and it stays
    # alive (a member win RISES the member, it does not die). A second member
    # wins ONCE => SLIGHTED — a real but weaker grudge — so the selection has to
    # pick the HIGHER grudge, not merely any grudge-holder.
    await wb.clash(angriest.did, player.did, player_won=False, note="win 1")
    await wb.clash(angriest.did, player.did, player_won=False, note="win 2")
    await wb.clash(milder.did, player.did, player_won=False, note="one win")
    assert await angriest.kernel.grudge_level(player.did) == GRUDGING
    assert await milder.kernel.grudge_level(player.did) == SLIGHTED

    director = WarbandDirector()
    chosen = await director.revenge_candidate(wb, player.did)
    assert chosen is not None
    assert chosen.did == angriest.did, f"expected {angriest.name}, got {chosen.name}"


async def test_director_revenge_fires_at_peak_and_relax_suppresses() -> None:
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    # Give a captain a real grudge so a revenge beat has an actor.
    captain = next(m for m in wb.members if m.rank == CAPTAIN)
    await wb.clash(captain.did, player.did, player_won=True, note="beat")
    assert await captain.kernel.grudge_level(player.did) in (SLIGHTED, GRUDGING)

    # A director whose pacing we can drive deterministically: peak after one hot
    # beat, a short peak, then a RELAX window. High struggle cadence so power
    # struggles don't interfere with the revenge assertions.
    engine = DirectorEngine(peak_threshold=0.5, peak_beats=1, fade_beats=1, relax_beats=3)
    director = WarbandDirector(director=engine, struggle_every=999)

    saw_revenge_at_peak = False
    saw_relax = False
    for _ in range(10):
        beat = await director.tick(wb, player.did)
        if beat["phase"] == PEAK:
            assert beat["revenge"] is not None, "PEAK must emit a revenge beat"
            assert beat["revenge"]["member"] == captain.name
            saw_revenge_at_peak = True
        if beat["phase"] == RELAX:
            saw_relax = True
            # THE BREATHER: no revenge during RELAX, no matter how hot the grudge.
            assert beat["revenge"] is None, "RELAX must suppress revenge"

    assert saw_revenge_at_peak, "the run should have reached PEAK and fired revenge"
    assert saw_relax, "the run should have reached RELAX"


# ---------------------------------------------------------------------------
# director — power struggle
# ---------------------------------------------------------------------------


async def test_power_struggle_promotes_winner_and_updates_loser() -> None:
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    # Build a MUTUAL grudge between two same-rank Grunts so they are an eligible
    # rival pair. Give one the stronger grudge (more grievances) so the outcome
    # is deterministic: the stronger-grudge member wins.
    grunts = [m for m in wb.members if m.rank == GRUNT and m.alive]
    a, b = grunts[0], grunts[1]
    assert a.rank == b.rank == GRUNT

    # a holds TWO grudges against b; b holds ONE against a => a is the winner.
    await a.kernel.record(b.did, "You crossed me once.", kind="insult")
    await a.kernel.record(b.did, "And you crossed me twice.", kind="insult")
    await b.kernel.record(a.did, "You started it.", kind="insult")

    director = WarbandDirector()
    result = await director.resolve_power_struggle(wb)

    assert result is not None, "a mutual same-rank rivalry should yield a struggle"
    assert result["winner"] == a.name
    assert result["loser"] == b.name

    # Winner rose from Grunt to Captain; loser (a Grunt) was killed and rank held.
    assert a.rank == CAPTAIN
    assert result["winner_rose"] is True
    assert result["loser_killed"] is True
    assert b.alive is False


# ---------------------------------------------------------------------------
# portability — a member's grudge round-trips through .soul
# ---------------------------------------------------------------------------


async def test_member_grudge_survives_export_awaken_roundtrip(tmp_path: Path) -> None:
    """A warband member is a portable nemesis: export its .soul, awaken a fresh
    kernel, and the grudge toward the player comes back."""
    player = await _player()
    wb = await Warband.forge(player, size=6, seed=SEED)

    # A captain takes two beatings => GRUDGING with citable grievances.
    captain = next(m for m in wb.members if m.rank == CAPTAIN)
    await wb.clash(captain.did, player.did, player_won=True, note="first")
    await wb.clash(captain.did, player.did, player_won=True, note="second")

    level_before = await captain.kernel.grudge_level(player.did)
    count_before = len(await captain.kernel.grievances(player.did))
    assert level_before == GRUDGING

    soul_path = tmp_path / "nemesis.soul"
    await captain.kernel.export(str(soul_path))
    assert soul_path.exists() and soul_path.stat().st_size > 0

    # Awaken a FRESH kernel from the file — the grudge persists.
    revived = await GrudgeKernel.awaken(str(soul_path))
    assert await revived.grudge_level(player.did) == level_before
    assert len(await revived.grievances(player.did)) == count_before
