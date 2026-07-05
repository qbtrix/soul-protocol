# test_warband_voice.py — NEM-3: proof of the warband's OWN voice
#   (warband_voice.WarbandDialogueEngine) wired through the real Warband.
#
# Created: 2026-07-05 (feat/nemesis-warband) — deterministic tests, no LLM, no
#   network. Covers:
#     * GRUDGING cites the specific remembered wrong AND names the member AND
#       addresses the player by name (the revenge-vow contract).
#     * NONE is a wary sizing-up that names the member and the player.
#     * rank varies the tone (a Warlord speaks with contempt; a Grunt does not).
#     * the reputation path is name-aware hearsay (the recruit's name + the deed).
#     * live wiring: forge() gives each member a WarbandDialogueEngine by default,
#       and after a real clash the member's taunt is the warband voice (its own
#       name), NOT the package's "Bjorn" butcher template.
#
# Run:  uv run pytest examples/nemesis_warband/test_warband_voice.py -v

from __future__ import annotations

import pytest

from examples.nemesis_warband import Warband
from examples.nemesis_warband.warband import CAPTAIN
from examples.nemesis_warband.warband_voice import WarbandDialogueEngine
from soul_protocol.profiles.game import (
    GRUDGING,
    NONE,
    NOTORIOUS,
    PlayerSoul,
    TemplatedDialogueEngine,
)

pytestmark = pytest.mark.asyncio

SEED = 1337


# ---------------------------------------------------------------------------
# The engine in isolation — deterministic branch behavior.
# ---------------------------------------------------------------------------


async def test_grudging_cites_grievance_and_names_member_and_player() -> None:
    """GRUDGING => a revenge vow that (a) names the member, (b) cites the SPECIFIC
    remembered wrong from `grievances`, and (c) addresses the player by name."""
    engine = WarbandDialogueEngine("Gûl", "the Cleaver", "Captain")
    line = await engine.speak(
        persona="",
        ocean={},
        grudge_level=GRUDGING,
        grievances=["how you betrayed me", "what you stole"],
        player_line="(hunts you down)",
        player_name="Talion",
    )
    assert "Gûl" in line  # the member speaks in its own name
    assert "how you betrayed me" in line  # the SPECIFIC worst wrong, cited
    assert "Talion" in line  # addressed to the player by name
    assert "Bjorn" not in line  # NOT the package butcher template


async def test_none_is_wary_sizing_up_and_names_both() -> None:
    engine = WarbandDialogueEngine("Ratbag", "the Whisper", "Grunt")
    line = await engine.speak(
        persona="",
        ocean={},
        grudge_level=NONE,
        grievances=[],
        player_line="hello",
        player_name="Talion",
    )
    assert "Ratbag" in line
    assert "Talion" in line
    # Grunt sizing-up line, not the contemptuous warlord variant.
    assert "Fresh meat" in line


async def test_rank_changes_the_tone() -> None:
    """A Warlord is contemptuous; a Grunt is not — same state, different rank,
    different words."""
    grunt = WarbandDialogueEngine("Lug", "the Hound", "Grunt")
    warlord = WarbandDialogueEngine("Skarn", "the Bloody", "Warlord")

    grunt_line = await grunt.speak(
        persona="",
        ocean={},
        grudge_level=GRUDGING,
        grievances=["how you betrayed me"],
        player_line="",
        player_name="Talion",
    )
    warlord_line = await warlord.speak(
        persona="",
        ocean={},
        grudge_level=GRUDGING,
        grievances=["how you betrayed me"],
        player_line="",
        player_name="Talion",
    )
    assert grunt_line != warlord_line
    # The warlord's contempt shows: he references crushing warlords / his throne.
    assert ("warlord" in warlord_line.lower()) or ("throne" in warlord_line.lower())
    # The grunt's line does not posture as a throne-sitting warlord.
    assert "throne" not in grunt_line.lower()


async def test_reputation_is_name_aware_hearsay() -> None:
    """speak_reputation for a NOTORIOUS player names the recruit and the deed and
    reads as hearsay ("They say you ...")."""
    engine = WarbandDialogueEngine("Zog", "the Newcomer", "Grunt")
    line = await engine.speak_reputation(
        npc_name="Zog",
        persona="",
        ocean={},
        notoriety=NOTORIOUS,
        reputation_deeds=["betrayed someone who trusted you"],
        player_line="",
        player_name="Talion",
    )
    assert "Zog" in line
    assert "Talion" in line
    assert "They say you" in line
    assert "betrayed someone who trusted you" in line
    assert "fear you" in line


# ---------------------------------------------------------------------------
# Live wiring — forge() defaults to the warband voice, and the "Bjorn" hardcode
# is gone from real member output.
# ---------------------------------------------------------------------------


async def test_forge_wires_warband_voice_by_default() -> None:
    """Every member born by forge() speaks through a WarbandDialogueEngine, not
    the package's TemplatedDialogueEngine."""
    player = await PlayerSoul.birth(name="Talion")
    wb = await Warband.forge(player, size=6, seed=SEED)
    for m in wb.members:
        assert isinstance(m.kernel._dialogue, WarbandDialogueEngine)
        assert not isinstance(m.kernel._dialogue, TemplatedDialogueEngine)


async def test_clash_taunt_is_warband_voice_not_bjorn() -> None:
    """After a real clash, the member's spoken taunt is the warband voice — it
    contains the MEMBER's own name and never the hardcoded 'Bjorn'."""
    player = await PlayerSoul.birth(name="Talion")
    wb = await Warband.forge(player, size=6, seed=SEED)

    captain = next(m for m in wb.members if m.rank == CAPTAIN)
    # Two beatings => GRUDGING => the vow cites a wrong and names the member.
    await wb.clash(captain.did, player.did, player_won=True, note="first")
    beat = await wb.clash(captain.did, player.did, player_won=True, note="second")

    assert await captain.kernel.grudge_level(player.did) == GRUDGING
    taunt = beat["taunt"]
    assert captain.name in taunt  # the member speaks as itself
    assert "Talion" in taunt  # addresses the player
    assert "Bjorn" not in taunt  # the butcher hardcode is GONE
