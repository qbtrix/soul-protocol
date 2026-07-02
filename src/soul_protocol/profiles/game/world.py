# world.py — GameWorld: composition root + the engine-neutral session event
#   stream (state-stream v0) of the Game Profile.
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — Composes the whole
#   profile: N GrudgeKernels (npcs) + N PlayerSouls (players) + one Pulse
#   DirectorEngine + the four fun dials, and emits every observable state
#   change as one JSON event per line (session.jsonl) so ANY renderer — a
#   canvas client, a terminal, a game engine — can replay or live-follow the
#   session without importing Python. Design rules:
#     * REPLAY-SAFE: no wall clock, no randomness. Every event carries
#       t = a monotonic int counter (1, 2, 3, ...), unique and strictly
#       increasing, so `since`-cursor polling and file replay are exact.
#     * beat() is the one verb: route the player action to the named NPC
#       (default: first), (1) director.observe_beat with the PRE-beat grudge
#       level, (2) kernel.record (both-directions ledger when the player's
#       own PlayerSoul is in the world), (3) dials — progress.on_beat
#       (succeeded = the beat was neutral), spark observe + variation check,
#       (4) kernel.react for the spoken line, then emit the event run:
#       beat -> speech -> grudge_change (only on a level transition) ->
#       bond_change (every beat, current value — the HUD's meter) ->
#       director_phase (only on a phase transition) -> cost_tick (only when
#       a CostMeter is attached via attach_meter()).
#     * Zone model v0: zones = {soul-name: zone-string}, everyone starts in
#       DEFAULT_ZONE ("tavern"); move() re-homes a soul and emits a "move"
#       event. Zones are labels, not geometry — the renderer owns layout.
#     * snapshot() is SYNC (grudge levels are cached per (npc, player) as
#       beats compute them; bonds read live off the kernels) — the HUD's
#       late-joiner bootstrap: zones, director phase, per-NPC per-player
#       bond/grudge/last-grievance.
#     * session_path is truncated fresh at construction so the invariant
#       "read the file back == events()" holds for the world's lifetime.
#   Zero core files touched. Spec: spec/profiles/game.md.

"""GameWorld — the Game Profile's composition root and state stream.

One :class:`GameWorld` runs one scene: it owns the NPCs (:class:`GrudgeKernel`),
the players (:class:`PlayerSoul`), one :class:`DirectorEngine`, the built fun
dials, and a zone map — and narrates everything that happens as an append-only,
engine-neutral event stream (``{"t": <counter>, "type": ..., ...}`` per line).
Feed player actions through :meth:`GameWorld.beat`; read the stream back with
:meth:`GameWorld.events` (or the ``session.jsonl`` mirror) and bootstrap a HUD
with :meth:`GameWorld.snapshot`.
"""

from __future__ import annotations

import json
from pathlib import Path

from .costmeter import CostMeter
from .dials import BuiltDials, Dials
from .director import DirectorEngine
from .grudge import NONE, SEVERITY, GrudgeKernel
from .player import PlayerSoul

# Every soul starts here until move() re-homes it. A zone is a plain string
# label — geometry belongs to the renderer, not the world.
DEFAULT_ZONE = "tavern"


class GameWorld:
    """Composition root: souls + director + dials + zones -> one event stream.

    Construct with at least one NPC. ``director`` and ``dials`` default to the
    profile's tuned baseline — ``Dials().build()`` wires a
    :class:`DirectorEngine` that consumes the ChallengeDial. Pass
    ``session_path`` to mirror every event to a jsonl file (truncated fresh at
    construction, one JSON object per line, append-only afterwards).
    """

    def __init__(
        self,
        npcs: list[GrudgeKernel],
        players: list[PlayerSoul],
        director: DirectorEngine | None = None,
        dials: Dials | None = None,
        session_path: str | Path | None = None,
    ) -> None:
        if not npcs:
            raise ValueError("GameWorld needs at least one NPC (GrudgeKernel)")
        self.npcs = list(npcs)
        self.players = list(players)
        built: BuiltDials = (dials or Dials()).build()
        self.dials = built
        self.director = director if director is not None else built.director

        # Zone model v0: soul-name -> zone label; everyone starts in the tavern.
        self.zones: dict[str, str] = {kernel.npc_name: DEFAULT_ZONE for kernel in self.npcs}
        for player in self.players:
            self.zones[player.name] = DEFAULT_ZONE

        self.session_path = Path(session_path) if session_path is not None else None
        if self.session_path is not None:
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            # Fresh stream per world: the file always equals events().
            self.session_path.write_text("", encoding="utf-8")

        self._events: list[dict] = []
        self._t = 0  # monotonic event counter — NOT wall time (replay-safe)
        self._meter: CostMeter | None = None
        # Caches that keep snapshot() sync: last computed grudge level and the
        # last grievance line, keyed by (npc_name, player_did).
        self._grudge_levels: dict[tuple[str, str], str] = {}
        self._last_grievance: dict[tuple[str, str], str] = {}

    # ---- wiring ------------------------------------------------------------

    def attach_meter(self, meter: CostMeter) -> None:
        """Attach a :class:`CostMeter`; every beat then emits a ``cost_tick``
        event carrying the meter's running totals."""
        self._meter = meter

    # ---- zones ---------------------------------------------------------------

    def move(self, name: str, zone: str) -> dict:
        """Re-home a soul (by name) to ``zone`` and emit a ``move`` event."""
        if name not in self.zones:
            raise ValueError(f"unknown soul {name!r}; known: {sorted(self.zones)}")
        self.zones[name] = zone
        return self._emit("move", name=name, zone=zone)

    # ---- the one verb --------------------------------------------------------

    async def beat(
        self,
        player_did: str,
        player_name: str,
        line: str,
        kind: str = "neutral",
        npc_name: str | None = None,
    ) -> dict:
        """One player action against one NPC; returns the beat summary.

        Routes to the named NPC (default: the first), runs director ->
        record -> dials -> react, and appends the event run to the stream
        (see the module header for the exact event order). ``kind`` must be
        one of the profile's transgression kinds.
        """
        if kind not in SEVERITY:
            raise ValueError(f"unknown kind {kind!r}; expected one of {sorted(SEVERITY)}")
        kernel = self._kernel_named(npc_name)
        key = (kernel.npc_name, player_did)

        # Pre-beat state — the director paces off the level as it stood, and
        # grudge_change needs the old -> new transition.
        old_level = await kernel.grudge_level(player_did)
        old_phase = self.director.phase

        # (1) The director observes the beat (frequency governor ticks).
        self.director.observe_beat(player_did, kind, old_level)

        # (2) The NPC records it — both directions when the player's own soul
        # is in this world (portable reputation).
        player_soul = next((p for p in self.players if p.did == player_did), None)
        await kernel.record(player_did, line, kind, player_soul=player_soul)

        # (3) Dials: progress (a neutral beat counts as a success), spark.
        progress_advanced = self.dials.progress.on_beat(kind, succeeded=kind == "neutral")
        self.dials.spark.observe(kind)
        needs_variation = self.dials.spark.needs_variation()

        # (4) The NPC speaks.
        reaction = await kernel.react(player_did, player_name=player_name, player_line=line)

        # Post-beat state.
        new_level = await kernel.grudge_level(player_did)
        self._grudge_levels[key] = new_level
        if kind != "neutral":
            self._last_grievance[key] = line
        bond = kernel.bond_strength(player_did)

        # (5) The event run — one beat's narration, in a fixed order.
        self._emit(
            "beat", player=player_name, did=player_did, line=line, kind=kind, npc=kernel.npc_name
        )
        self._emit("speech", npc=kernel.npc_name, text=reaction, zone=self.zones[kernel.npc_name])
        if new_level != old_level:
            self._emit(
                "grudge_change", npc=kernel.npc_name, did=player_did, old=old_level, new=new_level
            )
        self._emit("bond_change", npc=kernel.npc_name, did=player_did, value=bond)
        if self.director.phase != old_phase:
            self._emit("director_phase", phase=self.director.phase, old=old_phase)
        if self._meter is not None:
            self._emit(
                "cost_tick",
                model=self._meter.model,
                calls=self._meter.calls,
                cached_calls=self._meter.cached_calls,
                total_cost=self._meter.total_cost,
            )

        return {
            "npc": kernel.npc_name,
            "player": player_name,
            "did": player_did,
            "kind": kind,
            "line": line,
            "reaction": reaction,
            "grudge_level": new_level,
            "bond": bond,
            "phase": self.director.phase,
            "pacing": self.director.suggest_pacing(player_did),
            "yes_and": self.director.yes_and(kind),
            "progress": progress_advanced,
            "spark": {
                "needs_variation": needs_variation,
                "twist": self.dials.spark.twist(kind) if needs_variation else None,
            },
        }

    # ---- readbacks -----------------------------------------------------------

    def events(self) -> list[dict]:
        """The full event stream so far (a copy — safe to mutate)."""
        return list(self._events)

    def snapshot(self) -> dict:
        """The HUD bootstrap: zones, director phase, per-NPC relationship state.

        Sync by design — grudge levels are the cached values the beats
        computed (``NONE`` for a pair never beaten), bonds read live off the
        kernels, and ``last_grievance`` is the most recent wronging line.
        """
        npcs = []
        for kernel in self.npcs:
            per_player = {}
            for player in self.players:
                key = (kernel.npc_name, player.did)
                per_player[player.did] = {
                    "player": player.name,
                    "grudge": self._grudge_levels.get(key, NONE),
                    "bond": kernel.bond_strength(player.did),
                    "last_grievance": self._last_grievance.get(key),
                }
            npcs.append(
                {
                    "name": kernel.npc_name,
                    "did": kernel.npc_did,
                    "zone": self.zones[kernel.npc_name],
                    "players": per_player,
                }
            )
        return {
            "zones": dict(self.zones),
            "phase": self.director.phase,
            "npcs": npcs,
            "players": [
                {"name": p.name, "did": p.did, "zone": self.zones[p.name]} for p in self.players
            ],
        }

    # ---- internals -----------------------------------------------------------

    def _kernel_named(self, npc_name: str | None) -> GrudgeKernel:
        """The named NPC, or the first when no name was given."""
        if npc_name is None:
            return self.npcs[0]
        for kernel in self.npcs:
            if kernel.npc_name == npc_name:
                return kernel
        known = sorted(k.npc_name for k in self.npcs)
        raise ValueError(f"unknown npc {npc_name!r}; known: {known}")

    def _emit(self, event_type: str, **fields) -> dict:
        """Append one event to the stream (and its jsonl mirror)."""
        self._t += 1
        event = {"t": self._t, "type": event_type, **fields}
        self._events.append(event)
        if self.session_path is not None:
            with self.session_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event) + "\n")
        return event
