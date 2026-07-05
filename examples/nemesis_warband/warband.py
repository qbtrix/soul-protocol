# warband.py — NEM-1: a Shadow-of-Mordor "Nemesis System" warband composed of
#   N living souls, built ENTIRELY on soul_protocol.profiles.game (imported
#   as-is; the package is under PR review and NOT modified here).
#
# Created: 2026-07-05 (feat/nemesis-warband) — A Warband is N Members, each a
#   GrudgeKernel (a real .soul). Ranks (Grunt/Captain/Warlord) sit ON TOP of the
#   souls; the grudge state IS the drama.
#     * KEY REUSE: GrudgeKernel.record(subject_did, ...) takes ANY DID as the
#       subject, so passing another MEMBER's did makes NPC<->NPC grudges for free
#       (the "rivalry" ledger) with zero new persistence code. Member A records a
#       betrayal against Member B's did => A now holds a grudge toward B, exactly
#       the same machinery a player-grudge uses.
#     * clash(member, player, player_won, note) is the core loop: a player win is
#       remembered as a humiliation (a beating maps onto the EXISTING "betrayal"
#       severity — we never touch the package SEVERITY dict) that climbs the
#       grudge and DEMOTES (or, for a grunt, KILLS) the member; a member win
#       RISES the member a rank, they gloat, and a same-rank rival records a
#       jealousy grudge against the riser (more NPC<->NPC drama).
#     * recruit(name, epithet) reads the player's PORTABLE reputation via
#       react_to_reputation(player) so a new member's FIRST line already fears a
#       notorious player — reputation flows in from the player.soul, unmet.
#     * board() is the "Sauron's Army" snapshot: every member with rank, alive,
#       grudge-toward-player (level + bond + last grievance line) and the list of
#       members they hold rivalries against.
#   All rank/selection logic is deterministic and unit-testable; every taunt goes
#   through the kernel's dialogue engine (templated by default => no LLM/network).
#
# Traps handled: GrudgeKernel is fully async (everything awaited); clash outcomes
#   are mapped onto EXISTING kinds {neutral,insult,theft,betrayal}; imports are
#   added together with their first use so the format hook can't strip them.

from __future__ import annotations

import random
from dataclasses import dataclass, field

from soul_protocol.profiles.game import GrudgeKernel, PlayerSoul

# ---------------------------------------------------------------------------
# Ranks — the warband hierarchy that sits on top of the souls.
# ---------------------------------------------------------------------------
GRUNT = 0
CAPTAIN = 1
WARLORD = 2

RANK_LABELS: dict[int, str] = {GRUNT: "Grunt", CAPTAIN: "Captain", WARLORD: "Warlord"}
MIN_RANK = GRUNT
MAX_RANK = WARLORD


def rank_label(rank: int) -> str:
    """Human-readable label for a rank int (clamped to the known band)."""
    return RANK_LABELS.get(max(MIN_RANK, min(MAX_RANK, rank)), "Grunt")


# ---------------------------------------------------------------------------
# Clash outcome -> transgression kind. We map onto the package's EXISTING
# SEVERITY kinds (never touch that dict): a player BEATING a member is the
# gravest wrong the member remembers, so it lands as a "betrayal"-severity
# grudge (0.9). A single such wrong already tips grudge_level toward GRUDGING
# on the next wrong, and cumulative beatings compound. NPC<->NPC jealousy from a
# rival's promotion is an "insult"-severity slight (0.4) — real, but lighter
# than being beaten in the dirt.
# ---------------------------------------------------------------------------
CLASH_WRONG_KIND = "betrayal"  # a beating, remembered as the deepest wrong
RIVALRY_SEED_KIND = "betrayal"  # the seeded pre-existing bad blood between members
JEALOUSY_KIND = "insult"  # a rival's promotion stings, but less than a beating


# ---------------------------------------------------------------------------
# Member archetypes — varied souls so the warband has brutes, schemers, cowards.
# Each entry: (archetype, persona, traits). Cycled over the requested size.
# ---------------------------------------------------------------------------
_ARCHETYPES: list[tuple[str, str, list[str]]] = [
    (
        "The Brute",
        "I am a hulking orc brute. I settle everything with my fists and I never forget a beating.",
        ["brutal", "stubborn", "proud"],
    ),
    (
        "The Schemer",
        "I am a cunning orc schemer. I smile, I flatter, and I remember every slight to repay it cold.",
        ["cunning", "patient", "treacherous"],
    ),
    (
        "The Coward",
        "I am a sniveling orc coward. I bluster loud and run fast, but a grudge I nurse forever.",
        ["cowardly", "loud", "spiteful"],
    ),
    (
        "The Beast",
        "I am a feral orc beast-master. I speak little and bite hard, and I hunt what wrongs me.",
        ["feral", "relentless", "silent"],
    ),
    (
        "The Zealot",
        "I am a fanatic orc zealot. I fight for glory and I take every defeat as a debt of blood.",
        ["fanatic", "fearless", "vengeful"],
    ),
    (
        "The Warlord",
        "I am a battle-scarred orc warlord. I have climbed on the backs of rivals and I mean to stay on top.",
        ["commanding", "ruthless", "ambitious"],
    ),
]

# Flavourful epithets ("the Cleaver") cycled alongside the archetypes.
_EPITHETS: list[str] = [
    "the Cleaver",
    "the Whisper",
    "the Runner",
    "the Hound",
    "the Zealous",
    "the Bloody",
    "Skull-Splitter",
    "the Vile",
]

# Orkish-sounding names cycled for the members.
_NAMES: list[str] = [
    "Gûl",
    "Ratbag",
    "Krimp",
    "Muzgash",
    "Grishnákh",
    "Lug",
    "Skarn",
    "Ushak",
]


@dataclass
class Member:
    """One warband member: a living soul with a rank, an epithet, and a pulse.

    ``kernel`` is a real :class:`GrudgeKernel` (an npc.soul). ``did`` is its DID
    — the identity other members record their rivalries against. ``alive`` flips
    to False when a grunt is killed in a clash. ``traits`` are flavour only.
    """

    kernel: GrudgeKernel
    did: str
    name: str
    epithet: str
    rank: int
    alive: bool = True
    traits: list[str] = field(default_factory=list)

    @property
    def rank_label(self) -> str:
        return rank_label(self.rank)


class Warband:
    """A Nemesis-System warband: N :class:`Member` souls with ranks and grudges.

    Build one with :meth:`forge`. Drive the drama with :meth:`clash` (the core
    player-vs-member loop), :meth:`recruit` (a new member reads the player's
    reputation on arrival), and read the whole army with :meth:`board`.

    Selection/rank logic is deterministic; taunts flow through each member's
    kernel dialogue engine (templated by default, so no LLM and no network).
    """

    def __init__(self, members: list[Member], player: PlayerSoul, rng: random.Random) -> None:
        self._members = members
        self._player = player
        self._rng = rng

    # ---- construction -----------------------------------------------------

    @classmethod
    async def forge(
        cls,
        player: PlayerSoul,
        size: int = 6,
        seed: int = 1337,
    ) -> Warband:
        """Forge a warband of ``size`` members with varied archetypes, starting
        ranks (one Warlord, ~a third Captains, the rest Grunts), and 2-3 seeded
        NPC<->NPC rivalries.

        Deterministic: a seeded ``random.Random`` drives every choice, so a
        given (size, seed) always forges the same warband. No LLM, no network —
        births use the Soul heuristic path.
        """
        if size < 2:
            raise ValueError(f"a warband needs at least 2 members, got {size}")

        rng = random.Random(seed)
        members: list[Member] = []
        for i in range(size):
            archetype, persona, traits = _ARCHETYPES[i % len(_ARCHETYPES)]
            name = _NAMES[i % len(_NAMES)]
            epithet = _EPITHETS[i % len(_EPITHETS)]
            kernel = await GrudgeKernel.birth(
                name=name,
                archetype=archetype,
                persona=persona,
            )
            members.append(
                Member(
                    kernel=kernel,
                    did=kernel.npc_did,
                    name=name,
                    epithet=epithet,
                    rank=GRUNT,  # ranks assigned below, deterministically
                    traits=list(traits),
                )
            )

        warband = cls(members, player, rng)
        warband._assign_starting_ranks()
        await warband._seed_rivalries()
        return warband

    def _assign_starting_ranks(self) -> None:
        """Deterministically assign the opening hierarchy: the last member is the
        Warlord, roughly a third are Captains, the remainder Grunts."""
        n = len(self._members)
        # One Warlord (the highest-index seed, "The Warlord" archetype when the
        # size lands on 6), then about a third Captains.
        self._members[-1].rank = WARLORD
        n_captains = max(1, (n - 1) // 3)
        for m in self._members[:-1]:
            m.rank = GRUNT
        for m in self._members[:n_captains]:
            m.rank = CAPTAIN

    async def _seed_rivalries(self) -> None:
        """Seed 2-3 pre-existing NPC<->NPC grudges: member A records a wrong
        against member B's DID. This uses the SAME GrudgeKernel.record machinery
        as a player-grudge — only the subject is another member's DID — so the
        rivalry is a first-class, persisted, round-trippable grudge.
        """
        members = self._members
        n = len(members)
        if n < 2:
            return

        # Deterministic distinct (attacker, target) pairs. Up to 3 rivalries.
        pairs: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        attempts = 0
        target_count = min(3, n - 1)
        while len(pairs) < target_count and attempts < 50:
            attempts += 1
            a = self._rng.randrange(n)
            b = self._rng.randrange(n)
            if a == b or (a, b) in seen or (b, a) in seen:
                continue
            seen.add((a, b))
            pairs.append((a, b))

        seed_lines = [
            "You stole my kill at the bridge.",
            "You left me to the archers at the black gate.",
            "You took the captain's favor that was mine.",
        ]
        for idx, (a, b) in enumerate(pairs):
            attacker = members[a]
            target = members[b]
            line = seed_lines[idx % len(seed_lines)]
            # attacker holds the grudge AGAINST target's DID.
            await attacker.kernel.record(target.did, line, kind=RIVALRY_SEED_KIND)

    # ---- the core loop ----------------------------------------------------

    async def clash(
        self,
        member_did: str,
        player_did: str,
        player_won: bool,
        note: str,
    ) -> dict:
        """Resolve one clash between a member and the player. The heart of the
        Nemesis System.

        * ``player_won`` — the member is humiliated: it records the beating as a
          ``betrayal``-severity grudge against the player (the grudge climbs),
          and it is DEMOTED — unless it is already a Grunt, in which case it is
          KILLED and a surviving rival is promoted to fill the gap.
        * member won — the member RISES one rank (capped at Warlord), gloats, and
          records the win as a fresh grudge against the player ("you'll pay ...").
          Its promotion makes a same-rank RIVAL record a jealousy grudge against
          it (NPC<->NPC drama).

        Returns a beat dict: ``member``, ``outcome`` ("player_won"/"member_won"),
        ``rank_change`` (-1/0/+1), ``killed`` (bool), ``taunt`` (spoken via the
        kernel), and ``rivalry_triggered`` (the rival name whose jealousy fired,
        or None).
        """
        member = self._require_member(member_did)
        player_name = self._player.name

        rank_change = 0
        killed = False
        rivalry_triggered: str | None = None

        if player_won:
            # 1. The member remembers the humiliation — a beating is a betrayal.
            await member.kernel.record(
                player_did,
                f"You beat me down: {note}",
                kind=CLASH_WRONG_KIND,
                player_soul=self._player,  # write the player's reputation too
            )
            # 2. Demote, or kill if already a grunt.
            if member.rank <= GRUNT:
                member.alive = False
                killed = True
                rank_change = 0
                self._promote_a_rival(exclude_did=member.did)
            else:
                self._demote(member.did)
                rank_change = -1
            outcome = "player_won"
        else:
            # 1. The member RISES and gloats; the win becomes a fresh grudge.
            rose = self._promote(member.did)
            rank_change = 1 if rose else 0
            await member.kernel.record(
                player_did,
                f"You'll pay for what you did, then you crawled away: {note}",
                kind=CLASH_WRONG_KIND,
                player_soul=self._player,
            )
            # 2. A same-rank rival gets jealous of the riser (NPC<->NPC drama).
            if rose:
                rivalry_triggered = await self._trigger_jealousy(member)
            outcome = "member_won"

        # The member's spoken reaction, citing its history with the player.
        taunt = await member.kernel.react(
            player_did,
            player_name=player_name,
            player_line=note,
        )

        return {
            "member": member.name,
            "epithet": member.epithet,
            "outcome": outcome,
            "rank_change": rank_change,
            "rank_label": member.rank_label,
            "killed": killed,
            "alive": member.alive,
            "taunt": taunt,
            "rivalry_triggered": rivalry_triggered,
        }

    async def _trigger_jealousy(self, riser: Member) -> str | None:
        """After ``riser`` is promoted, the first alive same-rank member (other
        than the riser) records a jealousy grudge against the riser's DID. Pure
        selection: the lowest-index eligible rival, so it's deterministic.
        Returns the jealous rival's name, or None if there is no same-rank peer.
        """
        for other in self._members:
            if other.did == riser.did or not other.alive:
                continue
            if other.rank == riser.rank:
                await other.kernel.record(
                    riser.did,
                    f"{riser.name} {riser.epithet} climbed over me. That will not stand.",
                    kind=JEALOUSY_KIND,
                )
                return other.name
        return None

    # ---- recruitment ------------------------------------------------------

    async def recruit(self, name: str, epithet: str) -> dict:
        """A NEW member joins and immediately reads the player's PORTABLE
        reputation off their player.soul (``react_to_reputation``). If the player
        is notorious, the recruit's very FIRST line already fears/hates them —
        reputation flows in unmet, straight from the player's own soul.

        Returns a beat dict: ``member``, ``epithet``, ``rank`` (joins as Grunt),
        ``first_line`` (the reputation reaction), and ``notoriety``.
        """
        # A fresh recruit uses the next archetype in the cycle for flavour.
        i = len(self._members)
        archetype, persona, traits = _ARCHETYPES[i % len(_ARCHETYPES)]
        kernel = await GrudgeKernel.birth(name=name, archetype=archetype, persona=persona)
        member = Member(
            kernel=kernel,
            did=kernel.npc_did,
            name=name,
            epithet=epithet,
            rank=GRUNT,
            traits=list(traits),
        )
        self._members.append(member)

        # The recruit reads who the player has been — before ever meeting them.
        first_line, notoriety = await member.kernel.react_to_reputation(self._player)

        return {
            "member": name,
            "epithet": epithet,
            "rank": member.rank_label,
            "first_line": first_line,
            "notoriety": notoriety,
        }

    # ---- the "Sauron's Army" snapshot ------------------------------------

    async def board(self) -> list[dict]:
        """A snapshot of the whole warband — the "Sauron's Army" screen.

        Each entry carries: name, epithet, rank (label), alive, the member's
        grudge toward the player (level + bond + last grievance line), and the
        list of member NAMES they hold rivalries against (NPC<->NPC grudges).
        """
        player_did = self._player.did
        rows: list[dict] = []
        # DID -> name so we can render rivalries as names, not raw DIDs.
        by_did = {m.did: m for m in self._members}

        for member in self._members:
            grievances = await member.kernel.grievances(player_did)
            level = await member.kernel.grudge_level(player_did)
            bond = member.kernel.bond_strength(player_did)
            last_line = grievances[0].content if grievances else None

            rivalries = await self._rivalries_of(member, by_did)

            rows.append(
                {
                    "name": member.name,
                    "epithet": member.epithet,
                    "rank": member.rank_label,
                    "alive": member.alive,
                    "grudge_level": level,
                    "bond": round(bond, 1),
                    "last_grievance": last_line,
                    "rivalries": rivalries,
                }
            )
        return rows

    async def _rivalries_of(self, member: Member, by_did: dict[str, Member]) -> list[str]:
        """Names of the members ``member`` holds a grudge against (its rivalries).

        Checks the member's grudge toward every OTHER member's DID — the same
        grievance store, just keyed on a member DID instead of the player's.
        """
        out: list[str] = []
        for other in self._members:
            if other.did == member.did:
                continue
            grievances = await member.kernel.grievances(other.did)
            if grievances:
                out.append(other.name)
        return out

    # ---- rank helpers (deterministic) ------------------------------------

    def _promote(self, member_did: str) -> bool:
        """Raise a member one rank (capped at Warlord). Returns True if it moved."""
        member = self._require_member(member_did)
        if member.rank >= MAX_RANK:
            return False
        member.rank += 1
        return True

    def _demote(self, member_did: str) -> bool:
        """Lower a member one rank (floored at Grunt). Returns True if it moved."""
        member = self._require_member(member_did)
        if member.rank <= MIN_RANK:
            return False
        member.rank -= 1
        return True

    def _promote_a_rival(self, exclude_did: str) -> str | None:
        """Fill a gap left by a killed/demoted member: promote the highest-ranked
        alive member below Warlord (deterministic tie-break: lowest index). This
        is the warband closing ranks over a fallen member. Returns the promoted
        member's name, or None if nobody is eligible.
        """
        candidates = [
            m for m in self._members if m.alive and m.did != exclude_did and m.rank < MAX_RANK
        ]
        if not candidates:
            return None
        # Highest current rank first; stable index order breaks ties.
        best = max(candidates, key=lambda m: (m.rank, -self._members.index(m)))
        best.rank += 1
        return best.name

    # ---- introspection ----------------------------------------------------

    @property
    def members(self) -> list[Member]:
        """The live member list (order is stable, includes the dead)."""
        return self._members

    @property
    def player_name(self) -> str:
        """The player's name (used to address them in taunts)."""
        return self._player.name

    @property
    def player_did(self) -> str:
        """The player's DID — the subject of every member's player-grudge."""
        return self._player.did

    def member(self, member_did: str) -> Member:
        """Look up a member by DID (raises if unknown)."""
        return self._require_member(member_did)

    def _require_member(self, member_did: str) -> Member:
        for m in self._members:
            if m.did == member_did:
                return m
        raise KeyError(f"no member with did {member_did!r}")
