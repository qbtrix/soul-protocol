# test_world.py — Deterministic tests for GameWorld (world.py): composition +
#   the engine-neutral session event stream (state-stream v0).
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — Six pytest-asyncio
#   tests against the REAL Soul (no mocks of the profile, no LLM, no network,
#   no randomness):
#     * test_scripted_session_event_sequence — a scripted 6-beat session
#       produces the EXACT event-type sequence (beat/speech/bond_change every
#       beat; grudge_change only on the two level transitions) with t a
#       strictly increasing 1..N counter, and the transitions carry the right
#       old -> new levels.
#     * test_grudge_change_fires_exactly_once_when_slighted — one insult among
#       neutrals trips NONE -> SLIGHTED exactly once; no further grudge_change
#       without a second wrong.
#     * test_session_jsonl_roundtrips — the session.jsonl mirror parses back
#       byte-for-value equal to events().
#     * test_snapshot_shape_routing_and_move — snapshot carries zones/phase/
#       per-NPC per-player state; beats route to the NAMED npc (Astrid takes
#       the insult, Bjorn stays clean); move() re-homes a soul and emits a
#       move event.
#     * test_cost_tick_only_when_meter_attached — cost_tick events appear only
#       after attach_meter(); absent otherwise.
#     * test_director_phase_event_on_transition — a hard world (challenge=1.0)
#       peaks on one hot beat and emits director_phase BUILD_UP -> PEAK.
#
# Run:  uv run pytest tests/profiles/game/test_world.py -v

from __future__ import annotations

import json
from pathlib import Path

from soul_protocol.profiles.game import (
    BUILD_UP,
    DEFAULT_ZONE,
    GRUDGING,
    NONE,
    PEAK,
    SLIGHTED,
    CostMeter,
    Dials,
    GameWorld,
    GrudgeKernel,
    PlayerSoul,
)


async def _tavern(
    tmp_path: Path | None = None,
    dials: Dials | None = None,
    with_astrid: bool = False,
) -> tuple[GameWorld, PlayerSoul]:
    """A fresh world: Bjorn (+ optionally Astrid) and player Ragnar."""
    npcs = [await GrudgeKernel.birth(name="Bjorn", archetype="The Butcher")]
    if with_astrid:
        npcs.append(
            await GrudgeKernel.birth(
                name="Astrid",
                archetype="The Innkeeper",
                persona="I am Astrid, the sharp-eyed innkeeper. I miss nothing.",
            )
        )
    ragnar = await PlayerSoul.birth(name="Ragnar")
    session_path = tmp_path / "session.jsonl" if tmp_path is not None else None
    world = GameWorld(npcs, [ragnar], dials=dials, session_path=session_path)
    return world, ragnar


async def test_scripted_session_event_sequence(tmp_path: Path) -> None:
    """The exact event-type run of a 6-beat scripted session, replay-safe t."""
    world, ragnar = await _tavern(tmp_path)
    script = ["neutral", "neutral", "insult", "neutral", "theft", "neutral"]
    for kind in script:
        await world.beat(ragnar.did, "Ragnar", f"a {kind} act", kind=kind)

    types = [e["type"] for e in world.events()]
    assert types == [
        # beat 1 (neutral)
        "beat",
        "speech",
        "bond_change",
        # beat 2 (neutral)
        "beat",
        "speech",
        "bond_change",
        # beat 3 (insult) — NONE -> SLIGHTED trips here
        "beat",
        "speech",
        "grudge_change",
        "bond_change",
        # beat 4 (neutral)
        "beat",
        "speech",
        "bond_change",
        # beat 5 (theft) — SLIGHTED -> GRUDGING trips here
        "beat",
        "speech",
        "grudge_change",
        "bond_change",
        # beat 6 (neutral) — the butcher remembers, but no new transition
        "beat",
        "speech",
        "bond_change",
    ]

    # t is a monotonic counter, not wall time: exactly 1..N, strictly rising.
    ts = [e["t"] for e in world.events()]
    assert ts == list(range(1, len(types) + 1))

    changes = [e for e in world.events() if e["type"] == "grudge_change"]
    assert [(c["old"], c["new"]) for c in changes] == [(NONE, SLIGHTED), (SLIGHTED, GRUDGING)]
    assert all(c["npc"] == "Bjorn" and c["did"] == ragnar.did for c in changes)


async def test_grudge_change_fires_exactly_once_when_slighted() -> None:
    """One insult among neutrals: NONE -> SLIGHTED fires exactly once."""
    world, ragnar = await _tavern()
    for kind in ["neutral", "insult", "neutral", "neutral"]:
        await world.beat(ragnar.did, "Ragnar", f"a {kind} act", kind=kind)

    changes = [e for e in world.events() if e["type"] == "grudge_change"]
    assert len(changes) == 1
    assert changes[0]["old"] == NONE
    assert changes[0]["new"] == SLIGHTED


async def test_session_jsonl_roundtrips(tmp_path: Path) -> None:
    """The jsonl mirror reads back exactly equal to events()."""
    world, ragnar = await _tavern(tmp_path)
    world.move("Ragnar", "door")
    for kind in ["neutral", "betrayal", "neutral"]:
        await world.beat(ragnar.did, "Ragnar", f"a {kind} act", kind=kind)

    raw = (tmp_path / "session.jsonl").read_text(encoding="utf-8")
    replayed = [json.loads(line) for line in raw.splitlines() if line.strip()]
    assert replayed == world.events()


async def test_snapshot_shape_routing_and_move() -> None:
    """Snapshot carries zones/phase/per-NPC state; beats route to the NAMED
    npc; move() re-homes a soul and emits a move event."""
    world, ragnar = await _tavern(with_astrid=True)
    snap = world.snapshot()
    assert snap["zones"] == {"Bjorn": DEFAULT_ZONE, "Astrid": DEFAULT_ZONE, "Ragnar": DEFAULT_ZONE}
    assert snap["phase"] == BUILD_UP
    assert [n["name"] for n in snap["npcs"]] == ["Bjorn", "Astrid"]
    assert snap["players"] == [{"name": "Ragnar", "did": ragnar.did, "zone": DEFAULT_ZONE}]

    # Route the insult to Astrid by name — Bjorn must stay clean.
    summary = await world.beat(
        ragnar.did, "Ragnar", "Your ale tastes of dishwater.", kind="insult", npc_name="Astrid"
    )
    assert summary["npc"] == "Astrid"
    speech = [e for e in world.events() if e["type"] == "speech"]
    assert speech[-1]["npc"] == "Astrid"

    world.move("Ragnar", "door")
    snap = world.snapshot()
    assert snap["zones"]["Ragnar"] == "door"
    assert world.events()[-1] == {
        "t": world.events()[-1]["t"],
        "type": "move",
        "name": "Ragnar",
        "zone": "door",
    }

    astrid_state = snap["npcs"][1]["players"][ragnar.did]
    bjorn_state = snap["npcs"][0]["players"][ragnar.did]
    assert astrid_state["grudge"] == SLIGHTED
    assert astrid_state["last_grievance"] == "Your ale tastes of dishwater."
    assert astrid_state["bond"] < 50.0  # the insult cost trust
    assert bjorn_state == {"player": "Ragnar", "grudge": NONE, "bond": 50.0, "last_grievance": None}


async def test_cost_tick_only_when_meter_attached() -> None:
    """cost_tick rides the stream only once a CostMeter is attached."""
    world, ragnar = await _tavern()
    await world.beat(ragnar.did, "Ragnar", "Morning, butcher.", kind="neutral")
    assert "cost_tick" not in {e["type"] for e in world.events()}

    async def generate(prompt: str) -> str:  # never called (templated engine)
        return "a line"

    world.attach_meter(CostMeter(generate, model="claude-cli"))
    await world.beat(ragnar.did, "Ragnar", "Fine day for a trade.", kind="neutral")
    ticks = [e for e in world.events() if e["type"] == "cost_tick"]
    assert len(ticks) == 1
    assert ticks[0]["model"] == "claude-cli"
    assert ticks[0]["calls"] == 0  # templated dialogue never hit the meter
    assert ticks[0]["total_cost"] == 0.0


async def test_director_phase_event_on_transition() -> None:
    """A hard world (challenge=1.0) peaks on one hot beat: director_phase
    BUILD_UP -> PEAK is emitted, and the summary reports the new phase."""
    world, ragnar = await _tavern(dials=Dials(challenge=1.0))
    summary = await world.beat(
        ragnar.did, "Ragnar", "I sold your secrets to the guard.", kind="betrayal"
    )
    assert summary["phase"] == PEAK
    phase_events = [e for e in world.events() if e["type"] == "director_phase"]
    assert phase_events == [
        {"t": phase_events[0]["t"], "type": "director_phase", "phase": PEAK, "old": BUILD_UP}
    ]
