# nemesis_director.py — NEM-2: a WarbandDirector that schedules DRAMA over a
#   warband, wrapping the Game Profile's DirectorEngine (imported as-is; the
#   package is under PR review and NOT modified here).
#
# Created: 2026-07-05 (feat/nemesis-warband) — The director sits above the
#   Warband and paces two kinds of beat, all as PURE deterministic functions of
#   grudge/rank state (no LLM in the selection; taunts go through the kernel's
#   templated dialogue engine):
#     * REVENGE (tick): each tick feeds the hottest member->player relationship
#       into the wrapped DirectorEngine (advancing its BUILD_UP->PEAK->FADE->RELAX
#       clock), then — only when the scene is at PEAK — SELECTS the alive member
#       with the highest grudge toward the player and returns a revenge beat: that
#       member hunts the player, its taunt citing the SPECIFIC history via
#       kernel.react(player_did, ...). During RELAX no revenge fires (the L4D
#       mandatory breather is respected). Selection is a pure argmax over grudge
#       state, so it's fully unit-testable.
#     * POWER STRUGGLE (cadence): every ``struggle_every`` ticks, pick two
#       same-rank rivals who hold a MUTUAL grudge and have one challenge the
#       other for rank — winner promotes, loser demotes or (if a grunt) dies.
#       This runs whether or not the player acted: the warband lives on its own.
#
#   REUSE: the wrapped DirectorEngine.observe_beat/.phase give the L4D pacing for
#   free; the warband's own grudge store (GrudgeKernel.grievances / grudge_level)
#   IS the selection signal, so no new persistence is introduced here.
#
# Traps handled: everything the kernel exposes is async (awaited here); selection
#   is deterministic (argmax + stable tie-breaks, no randomness in the choice);
#   power-struggle outcomes are decided by a pure rule, not a coin flip; imports
#   are added with their first use so the format hook can't strip them.

from __future__ import annotations

from soul_protocol.profiles.game import GRUDGING, NONE, PEAK, RELAX, SLIGHTED, DirectorEngine

from .warband import CLASH_WRONG_KIND, GRUNT, JEALOUSY_KIND, Member, Warband

# Grudge level -> a numeric rank so we can argmax "who hates the player most".
# Ties are then broken by bond (lower bond = angrier) and stable member order.
_LEVEL_ORDER: dict[str, int] = {NONE: 0, SLIGHTED: 1, GRUDGING: 2}


class WarbandDirector:
    """Schedules revenge beats and power struggles over a :class:`Warband`.

    Wraps a :class:`DirectorEngine` for the pacing clock. The two beat generators
    (:meth:`tick` for revenge, the power-struggle cadence inside it) select their
    actors by pure functions of grudge/rank state, so the whole thing is
    deterministic and unit-testable. Taunts are produced by each member's kernel
    dialogue engine (templated by default => no LLM, no network).
    """

    def __init__(
        self,
        director: DirectorEngine | None = None,
        struggle_every: int = 3,
    ) -> None:
        # A snappy default director so a short demo actually reaches PEAK: a low
        # peak_threshold means a couple of hot (grudge-amplified) beats crest the
        # scene. Callers can inject their own tuned DirectorEngine.
        self._director = director or DirectorEngine(peak_threshold=1.0, relax_beats=2)
        if struggle_every < 1:
            raise ValueError(f"struggle_every must be >= 1, got {struggle_every}")
        self._struggle_every = struggle_every
        self._ticks = 0

    # ---- readouts ---------------------------------------------------------

    @property
    def phase(self) -> str:
        """The wrapped director's current pacing phase."""
        return self._director.phase

    @property
    def ticks(self) -> int:
        """How many times :meth:`tick` has run."""
        return self._ticks

    # ---- the beat clock ---------------------------------------------------

    async def tick(self, warband: Warband, player_did: str) -> dict:
        """Advance the director one beat and, at PEAK, emit a revenge beat.

        Each tick:
          1. Find the alive member with the highest grudge toward the player.
          2. Feed that relationship's heat into the wrapped DirectorEngine
             (kind = a ``betrayal``-weight beat, amplified by its grudge level),
             which advances the BUILD_UP->PEAK->FADE->RELAX clock.
          3. If the scene is now at PEAK, that member HUNTS the player: return a
             revenge beat whose taunt cites the specific history via
             ``kernel.react``. In RELAX (or any non-PEAK phase) no revenge fires —
             the mandatory breather is honored.
          4. On the power-struggle cadence, ALSO resolve a power struggle between
             two same-rank rivals (independent of the player).

        Returns a beat dict::

            {
              "phase": <str>,
              "revenge": {member, taunt, grudge_level, bond} | None,
              "power_struggle": {challenger, defender, winner, loser, ...} | None,
            }
        """
        self._ticks += 1

        target = await self._angriest_alive(warband, player_did)

        # Feed the hottest relationship into the pacing clock. With no angry
        # member yet, feed a neutral beat so the clock still turns.
        if target is not None:
            level = await target.kernel.grudge_level(player_did)
            self._director.observe_beat(player_did, CLASH_WRONG_KIND, level)
        else:
            self._director.observe_beat(player_did, "neutral", NONE)

        phase = self._director.phase

        revenge: dict | None = None
        # Revenge only at PEAK, and NEVER during the mandatory RELAX breather.
        # (PEAK and RELAX are distinct phases; the explicit RELAX guard documents
        # the L4D breather contract even though PEAK already excludes it.)
        if phase == PEAK and phase != RELAX and target is not None:
            taunt = await target.kernel.react(
                player_did,
                player_name=warband.player_name,
                player_line="(hunts you down)",
            )
            revenge = {
                "member": target.name,
                "epithet": target.epithet,
                "grudge_level": await target.kernel.grudge_level(player_did),
                "bond": round(target.kernel.bond_strength(player_did), 1),
                "taunt": taunt,
            }

        power_struggle: dict | None = None
        if self._ticks % self._struggle_every == 0:
            power_struggle = await self.resolve_power_struggle(warband)

        return {"phase": phase, "revenge": revenge, "power_struggle": power_struggle}

    # ---- revenge selection (pure) ----------------------------------------

    async def _angriest_alive(self, warband: Warband, player_did: str) -> Member | None:
        """The alive member with the highest grudge toward the player.

        Pure argmax: (grudge-level rank, then LOWER bond = angrier, then stable
        member order). Returns None if no alive member holds any grudge.
        """
        best: Member | None = None
        best_key: tuple[int, float, int] | None = None
        for idx, member in enumerate(warband.members):
            if not member.alive:
                continue
            level = await member.kernel.grudge_level(player_did)
            level_rank = _LEVEL_ORDER.get(level, 0)
            if level_rank == 0:
                continue  # no grudge at all — not a revenge candidate
            bond = member.kernel.bond_strength(player_did)
            # Higher level wins; on a tie, lower bond (angrier); then lower index.
            key = (level_rank, -bond, -idx)
            if best_key is None or key > best_key:
                best_key = key
                best = member
        return best

    async def revenge_candidate(self, warband: Warband, player_did: str) -> Member | None:
        """Public alias for the revenge selection — the alive member who would
        hunt the player next. Exposed for tests and UIs; pure, no side effects.
        """
        return await self._angriest_alive(warband, player_did)

    # ---- power struggles (pure selection, deterministic outcome) ---------

    async def resolve_power_struggle(self, warband: Warband) -> dict | None:
        """Pick two same-rank rivals with a MUTUAL grudge and settle it for rank.

        Selection is deterministic: scan members in order, find the first pair
        (a, b) that are both alive, share the same rank, and hold grudges against
        EACH OTHER (mutual bad blood). The winner is the one who holds the
        STRONGER grudge (more grievances) against the other — a pure rule, no
        randomness. Winner promotes (capped at Warlord); loser demotes, or dies
        if already a Grunt, and the loser's death lets the warband close ranks.

        Returns the power-struggle beat, or None if no eligible rival pair exists.
        """
        pair = await self._find_mutual_rivals(warband)
        if pair is None:
            return None
        a, b = pair

        # Winner = stronger grudge (more grievances) against the other; tie ->
        # the higher-index member (stable, arbitrary but deterministic).
        a_g = len(await a.kernel.grievances(b.did))
        b_g = len(await b.kernel.grievances(a.did))
        if a_g >= b_g:
            winner, loser = a, b
        else:
            winner, loser = b, a

        # Winner rises (the challenge succeeds), if not already at the top.
        winner_rose = warband._promote(winner.did)

        # Loser falls — or dies if a grunt, and the band closes ranks.
        loser_killed = False
        if loser.rank <= GRUNT:
            loser.alive = False
            loser_killed = True
            warband._promote_a_rival(exclude_did=loser.did)
        else:
            warband._demote(loser.did)

        # The winner gloats over the beaten rival (records a fresh rivalry grudge).
        await winner.kernel.record(
            loser.did,
            f"I put {loser.name} in the dirt where they belong.",
            kind=JEALOUSY_KIND,
        )

        return {
            "challenger": winner.name,
            "defender": loser.name,
            "winner": winner.name,
            "winner_rank": winner.rank_label,
            "winner_rose": winner_rose,
            "loser": loser.name,
            "loser_rank": loser.rank_label,
            "loser_killed": loser_killed,
        }

    async def _find_mutual_rivals(self, warband: Warband) -> tuple[Member, Member] | None:
        """First (a, b) pair, in stable order, that are both alive, same rank,
        and hold grudges against each other. Pure selection over grudge state.
        """
        members = warband.members
        for i in range(len(members)):
            a = members[i]
            if not a.alive:
                continue
            for j in range(i + 1, len(members)):
                b = members[j]
                if not b.alive or b.rank != a.rank:
                    continue
                a_holds = bool(await a.kernel.grievances(b.did))
                b_holds = bool(await b.kernel.grievances(a.did))
                if a_holds and b_holds:
                    return a, b
        return None
