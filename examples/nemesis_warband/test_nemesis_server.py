# test_nemesis_server.py — NEM-4: in-process smoke tests for the SAURON'S ARMY
#   server (server.py), no browser and no sockets.
#
# Created: 2026-07-05 (feat/nemesis-warband) — drives DemoState directly (it owns
#   the background asyncio loop + the Warband + the director + the event log), so
#   the tests exercise the exact code paths the HTTP handlers call, without
#   binding a port. templated engine only => deterministic, $0.
#   Coverage:
#     * /board shape: player block (name/notoriety/deeds), members carry did +
#       rank_label + grudge/bond/rivalries, phase + engine + cursor present.
#     * /confront advances a member's rank AND plants a grudge, and the returned
#       taunt is the warband voice (the member's name, never "Bjorn").
#     * /tick, after building heat, returns a revenge OR power-struggle beat and
#       logs an event.
#
# Run:  uv run pytest examples/nemesis_warband/test_nemesis_server.py -v

from __future__ import annotations

import pytest

from examples.nemesis_warband.server import DemoState

# These tests spin a real background event loop per DemoState; they are sync
# functions that call state.run(...) (which marshals onto that loop), so they
# must NOT be collected as asyncio coroutine tests.
pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture()
def state():
    """A fresh templated-engine DemoState, torn down after the test."""
    st = DemoState(engine="templated")
    try:
        yield st
    finally:
        st.close()


def test_board_shape(state: DemoState) -> None:
    board = state.run(state.board())

    # Player block.
    assert board["player"]["name"] == "Talion"
    assert board["player"]["notoriety"] in {"UNKNOWN", "KNOWN", "NOTORIOUS"}
    assert isinstance(board["player"]["deeds"], list)

    # Six members, each with the fields the UI needs.
    assert len(board["members"]) == 6
    for row in board["members"]:
        assert row["did"]  # targetable for confront / export
        assert row["name"]
        assert row["epithet"]
        assert row["rank_label"] in {"Grunt", "Captain", "Warlord"}
        assert isinstance(row["alive"], bool)
        assert row["grudge_level"] in {"NONE", "SLIGHTED", "GRUDGING"}
        assert isinstance(row["rivalries"], list)

    # Exactly one Warlord at the top of the army.
    assert sum(1 for r in board["members"] if r["rank_label"] == "Warlord") == 1

    # Director + engine + cursor.
    assert board["phase"]
    assert board["engine"] == "templated"
    assert isinstance(board["cursor"], int)


def test_confront_advances_rank_and_grudge(state: DemoState) -> None:
    board = state.run(state.board())
    # Confront a Grunt and LOSE (player_won=False) => the member RISES a rank and
    # banks a fresh grudge. (Winning would demote/kill — we assert the rise.)
    grunt = next(r for r in board["members"] if r["rank_label"] == "Grunt")
    before = grunt["rank_label"]

    beat = state.run(state.confront(grunt["did"], player_won=False))

    assert beat["outcome"] == "member_won"
    assert beat["rank_change"] == 1
    assert beat["rank_label"] != before  # advanced off Grunt

    # The member now holds a grudge toward the player, visible on the board.
    after = next(r for r in beat["board"]["members"] if r["did"] == grunt["did"])
    assert after["grudge_level"] in {"SLIGHTED", "GRUDGING"}
    assert after["rank_label"] != before

    # The taunt is the warband voice: the member's own name, never "Bjorn".
    assert grunt["name"] in beat["taunt"]
    assert "Bjorn" not in beat["taunt"]

    # An event was logged for the confront.
    events = state.run(state.events_since(0))
    assert any(e["kind"] == "confront" for e in events)


def test_tick_returns_a_beat_after_building_heat(state: DemoState) -> None:
    board = state.run(state.board())

    # Build heat: pick two Grunts, have EACH win twice so both hold a real grudge
    # (GRUDGING) AND stay alive — a member win rises the member, it does not die.
    # That guarantees the director has an angry actor to send hunting, and enough
    # ticks will cross into PEAK (revenge) and/or hit the power-struggle cadence.
    grunts = [r for r in board["members"] if r["rank_label"] == "Grunt"]
    a, b = grunts[0], grunts[1]
    for did in (a["did"], b["did"]):
        state.run(state.confront(did, player_won=False))
        state.run(state.confront(did, player_won=False))

    saw_beat = False
    for _ in range(12):
        beat = state.run(state.tick())
        if beat.get("revenge") is not None or beat.get("power_struggle") is not None:
            saw_beat = True
            break

    assert saw_beat, "after building heat, some tick must fire a revenge or power struggle"

    # And the firing was logged as an event.
    events = state.run(state.events_since(0))
    assert any(e["kind"] in {"revenge", "power_struggle"} for e in events)
