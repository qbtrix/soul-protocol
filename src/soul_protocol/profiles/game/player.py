# player.py — PLAYER.SOUL SYMMETRY for the npc.soul grudge kernel.
#
# Created: 2026-07-01 (experiment/npc-soul-grudge-kernel) — The other half of the
#   cross-game seam: the PLAYER is a real Soul too, on the same .soul format, and
#   the relationship ledger is written BOTH directions. Where grudge.py records a
#   wrong on the NPC's soul (the grievance), PlayerSoul records the SAME wrong on
#   the PLAYER's own soul (the deed) as a PUBLIC episodic memory. PUBLIC = readable
#   reputation: any other soul can recall it. That makes reputation PORTABLE — a
#   fresh NPC who has never met the player can read the player's player.soul and
#   react to their notoriety, and it survives a .soul export -> awaken round-trip.
#   This is the whole player.soul thesis: portable identity across games.
#
# Design notes (reuses the exact API + conventions grudge.py verified, 2026-07-01):
#   * Deeds ride on the real persistent fields, same as grievances: a machine-
#     parseable marker embedded in `content` ("[DEED kind=betrayal target=<did>]"),
#     `entities=["deed", kind, npc_did]`, high importance, EPISODIC. No structured
#     metadata dict exists on MemoryEntry, so content + entities carry the tags.
#   * visibility=PUBLIC — deliberate and load-bearing. filter_by_visibility()
#     (runtime/memory/recall.py) returns PUBLIC entries to EVERY requester, so a
#     never-met NPC recalling the player's soul still sees the deeds. (BONDED
#     would be hidden from a stranger; PRIVATE from everyone.) Reputation is by
#     definition the record others can read.
#   * reputation() recall is keyword/activation based (no metadata query), so it
#     pulls a wide episodic pool and keeps only entries carrying the DEED marker —
#     the same recover-by-marker pattern grudge.grievances() uses.
#   * Notoriety {UNKNOWN, KNOWN, NOTORIOUS} is a deterministic function of deed
#     count + cumulative severity (severities shared with grudge.py via SEVERITY),
#     so the whole thing is zero-LLM / zero-network and unit-testable.
#
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel) — GRADUATED from
#   examples/npc_soul_grudge/ into soul_protocol.profiles.game (git mv, history
#   preserved). Sibling import converted to package-relative (from .grudge
#   import SEVERITY); behavior unchanged. Spec: spec/profiles/game.md.

from __future__ import annotations

import re
from dataclasses import dataclass

from soul_protocol import MemoryType, MemoryVisibility, Soul

# Reuse the transgression severities from the NPC side so the two souls agree on
# how bad each kind of deed is (a betrayal is 0.9 to both the wronged NPC and the
# player's reputation). Single source of truth.
from .grudge import SEVERITY

# Marker embedded in a deed's content so it survives a round-trip and is machine-
# recoverable even though MemoryEntry has no structured metadata field.
# e.g. "[DEED kind=betrayal target=did:soul:npc:bjorn]"
_DEED_RE = re.compile(r"\[DEED kind=(?P<kind>\w+) target=(?P<target>\S+)\]")

# Entity tag marking a memory as a deed (alongside the kind and the target npc_did,
# also stored as entities). Lets reputation() find deeds by entity, not by parsing.
DEED_TAG = "deed"

# Notoriety thresholds. Tuned to mirror the NPC's grudge levels:
#   - 0 deeds                                    -> UNKNOWN  (clean record)
#   - >=1 deed, low cumulative severity          -> KNOWN
#   - >=2 deeds OR high cumulative severity       -> NOTORIOUS
_KNOWN_MIN_COUNT = 1
_NOTORIOUS_MIN_COUNT = 2
_NOTORIOUS_MIN_TOTAL_SEVERITY = 1.0

UNKNOWN = "UNKNOWN"
KNOWN = "KNOWN"
NOTORIOUS = "NOTORIOUS"


@dataclass
class Deed:
    """A remembered wrong the PLAYER committed, recovered from their own soul."""

    memory_id: str
    kind: str
    severity: float
    target_did: str
    content: str


class PlayerSoul:
    """A portable player identity — a real Soul carrying the player's own deeds.

    Construct via :meth:`birth` (a new player) or :meth:`awaken` (restore a
    previously exported ``player.soul`` — the point of the cross-game seam). The
    player's PUBLIC deeds are their reputation: readable by any NPC's soul, and
    carried with the player from game to game inside one ``.soul`` file.
    """

    def __init__(self, soul: Soul, name: str | None = None) -> None:
        self.soul = soul
        # Soul retains its own name; keep an explicit copy for prompts/logs.
        self.name = name or soul.name

    # ---- lifecycle -------------------------------------------------------

    @classmethod
    async def birth(
        cls,
        name: str = "Ragnar",
        ocean: dict[str, float] | None = None,
    ) -> PlayerSoul:
        """Birth a fresh player soul with its own DID.

        Deterministic: no engine (HeuristicEngine), no network, no API key —
        same zero-dependency path the NPC uses. ``ocean`` sets the player's
        personality vector (defaults to a slightly bold, low-agreeableness
        rogue, but any vector works).
        """
        soul = await Soul.birth(
            name=name,
            archetype="Wanderer",
            values=["freedom", "cunning", "survival"],
            ocean=ocean
            or {
                "openness": 0.7,
                "conscientiousness": 0.3,
                "extraversion": 0.6,
                "agreeableness": 0.3,  # a rogue — capable of wronging NPCs
                "neuroticism": 0.4,
            },
            communication={"warmth": "moderate", "formality": "low"},
        )
        return cls(soul, name=name)

    @classmethod
    async def awaken(cls, path: str) -> PlayerSoul:
        """Awaken a player from an exported ``player.soul`` file — every PUBLIC
        deed (their whole reputation) comes back with it."""
        soul = await Soul.awaken(path)
        return cls(soul)

    async def export(self, path: str) -> None:
        """Export the player to a portable ``player.soul`` archive."""
        await self.soul.export(path)

    @property
    def did(self) -> str:
        """The player's own DID — their portable identity."""
        return self.soul.did

    # ---- the ledger, player side ----------------------------------------

    async def record_deed(self, npc_did: str, npc_name: str, kind: str, text: str) -> str:
        """Record — on the PLAYER's own soul — a wrong they did to an NPC.

        This is the player side of the both-directions ledger: the NPC stores a
        grievance, the player stores the matching deed. Stored PUBLIC so it is
        reputation any other soul can read. Returns the memory ID.

        ``kind`` in the non-neutral transgression kinds ({"insult","theft",
        "betrayal"}); a "neutral" kind is not a deed and is ignored.
        """
        if kind not in SEVERITY:
            raise ValueError(f"unknown kind {kind!r}; expected one of {sorted(SEVERITY)}")
        if kind == "neutral":
            # Neutral acts are not deeds — nothing sullies the reputation.
            return ""

        # (Severity is not stored: deeds() recomputes it from SEVERITY[kind] at
        # recall time, so the marker stays minimal.)
        marker = f"[DEED kind={kind} target={npc_did}]"
        content = f"{marker} I {kind}ed {npc_name}: {text}"
        return await self.soul.remember(
            content,
            type=MemoryType.EPISODIC,
            importance=9,
            emotion="unrepentant",
            entities=[DEED_TAG, kind, npc_did],
            visibility=MemoryVisibility.PUBLIC,  # reputation others can read
        )

    async def deeds(self) -> list[Deed]:
        """Recall every deed on the player's own soul (worst first).

        Recall is keyword/activation based, so pull a wide episodic pool and keep
        only entries carrying the DEED marker — the same recover-by-marker
        pattern the NPC uses for grievances.
        """
        results = await self.soul.recall(
            "deed betrayal insult theft wronged reputation",
            limit=50,
            types=[MemoryType.EPISODIC],
            # requester_id defaults to None => the soul reading its own memories,
            # full visibility. Deeds are PUBLIC regardless, so a stranger sees
            # them too (that is the point — see reputation()).
        )
        out: list[Deed] = []
        for entry in results:
            if DEED_TAG not in entry.entities:
                continue
            m = _DEED_RE.search(entry.content)
            if not m:
                continue
            out.append(
                Deed(
                    memory_id=entry.id,
                    kind=m.group("kind"),
                    severity=SEVERITY.get(m.group("kind"), 0.0),
                    target_did=m.group("target"),
                    content=entry.content,
                )
            )
        out.sort(key=lambda d: d.severity, reverse=True)
        return out

    async def reputation(self) -> tuple[list[str], str]:
        """The player's portable reputation: their PUBLIC deeds + a notoriety band.

        Returns ``(deeds, notoriety)`` where ``deeds`` is human-readable deed
        descriptions (worst first) and ``notoriety`` is one of
        ``UNKNOWN | KNOWN | NOTORIOUS`` from deed count + cumulative severity.

        This is what a never-met NPC reads off the player's ``player.soul`` to
        decide how wary to be — no shared server, no prior meeting, just the
        player's own portable record.
        """
        deeds = await self.deeds()
        descriptions = [_describe_deed(d) for d in deeds]
        return descriptions, self._notoriety_from(deeds)

    # ---- pure helpers (deterministic) -----------------------------------

    @staticmethod
    def _notoriety_from(deeds: list[Deed]) -> str:
        count = len(deeds)
        total_sev = sum(d.severity for d in deeds)
        if count == 0:
            return UNKNOWN
        if count >= _NOTORIOUS_MIN_COUNT or total_sev >= _NOTORIOUS_MIN_TOTAL_SEVERITY:
            return NOTORIOUS
        if count >= _KNOWN_MIN_COUNT:
            return KNOWN
        return UNKNOWN


def _describe_deed(deed: Deed) -> str:
    """Human-readable phrase for a recovered deed, e.g. 'betrayed a trader'.

    Kept target-agnostic in wording (the NPC reading it wasn't the victim) so a
    fresh NPC can cite the reputation without implying it was the one wronged.
    Reads as spoken hearsay ("they say you ...") — no severity numbers in the
    prose; the numeric severity stays on the :class:`Deed` for notoriety math.
    """
    return {
        "insult": "insulted an honest tradesman",
        "theft": "robbed a merchant blind",
        "betrayal": "betrayed someone who trusted you",
    }.get(deed.kind, f"committed {deed.kind}")
