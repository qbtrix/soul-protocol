# warband_voice.py — NEM-3: the WARBAND'S OWN VOICE. A DialogueEngine
#   implementation that gives each orc member a grimdark, NAME/EPITHET/RANK-aware
#   spoken line — WITHOUT touching soul_protocol.profiles.game (under PR review).
#
# Created: 2026-07-05 (feat/nemesis-warband) — The package ships
#   TemplatedDialogueEngine, but it hardcodes butcher flavour and the literal
#   name "Bjorn". That is by design: DialogueEngine is a PLUGGABLE PROTOCOL so
#   every game brings its own voice. This module is the Nemesis game's voice.
#
#   WarbandDialogueEngine is constructed PER MEMBER with that member's identity
#   baked in — WarbandDialogueEngine(name, epithet, rank_label) — so the same
#   grudge state renders as THAT orc speaking, in his own name, at his own rank:
#     * speak(): deterministic, grimdark orc-captain lines keyed off grudge_level.
#         - NONE     -> wary sizing-up ("bares his teeth. 'Fresh meat...'")
#         - SLIGHTED -> a threat that references the remembered grievance
#         - GRUDGING -> a revenge vow citing the SPECIFIC wrong from `grievances`
#       Tone escalates with rank: a Warlord is contemptuous, a Grunt desperate.
#     * speak_reputation(): name-aware HEARSAY for a fresh recruit reacting to the
#       player's PORTABLE notoriety ("'They say you <deed>. The others fear you.
#       I don't.'").
#
#   The `grievances` list this engine receives is already worst-first and
#   pre-phrased by grudge.phrase_grievances() ("how you betrayed me", "what you
#   stole from my stall", ...) — the same shape the templated engine consumes.
#   We weave grievances[0] into the vow so the line cites the specific wrong the
#   member remembers, per member and per player.
#
# Reuse / no-touch: this file imports NOTHING from the package that it mutates —
#   it only implements the DialogueEngine Protocol structurally (duck-typed;
#   the Protocol is runtime_checkable). warband.forge() wires an instance per
#   member. Zero package edits.

from __future__ import annotations

# Grudge-level + notoriety constants come from the package, read-only, so this
# engine renders the exact same branch set the kernel drives (NONE/SLIGHTED/
# GRUDGING and UNKNOWN/KNOWN/NOTORIOUS). Importing the constants is not a package
# EDIT — it is using the public API the way any consumer would.
from soul_protocol.profiles.game import (
    KNOWN,
    NONE,
    SLIGHTED,
    UNKNOWN,
)

# Rank labels the warband uses. A "Warlord" speaks with more contempt than a
# "Grunt" who is scrabbling to survive; the label drives that tonal shift.
_WARLORD = "Warlord"
_CAPTAIN = "Captain"


class WarbandDialogueEngine:
    """A grimdark orc-captain voice for ONE warband member.

    Implements the :class:`~soul_protocol.profiles.game.DialogueEngine` Protocol
    structurally (duck-typed — the Protocol is ``runtime_checkable`` and this
    class exposes ``speak`` + ``speak_reputation`` with matching signatures).

    Constructed per member with that member's identity baked in, so a single
    grudge state renders as *that orc* speaking — in his own name, wearing his
    own epithet, at his own rank::

        engine = WarbandDialogueEngine("Gûl", "the Cleaver", "Captain")

    Deterministic and offline: no LLM, no network. To get REAL in-character
    lines, wire an ``LLMDialogueEngine`` per member instead (the server's
    ``--engine claude`` path does exactly that).
    """

    def __init__(self, name: str, epithet: str, rank_label: str) -> None:
        self.name = name
        self.epithet = epithet
        self.rank_label = rank_label

    # ---- personal grudge (speak) -----------------------------------------

    async def speak(
        self,
        *,
        persona: str,
        ocean: dict[str, float],
        grudge_level: str,
        grievances: list[str],
        player_line: str,
        player_name: str | None = None,
    ) -> str:
        """The member's spoken reaction to the player, keyed off grudge level.

        ``grievances`` is worst-first and already phrased ("how you betrayed
        me"). ``grudge_level`` is one of NONE / SLIGHTED / GRUDGING. The line is
        deterministic and cites the specific remembered wrong when GRUDGING.
        """
        who = player_name or "wretch"
        name = self.name
        epithet = self.epithet
        contempt = self.rank_label == _WARLORD

        if grudge_level == NONE:
            # Wary sizing-up — a stranger, but the orc is already taking measure.
            if contempt:
                return (
                    f"{name} {epithet} looks down his scarred nose. "
                    f"'Another climber. You're nothing to me yet, {who}. "
                    "Give me a reason and I'll carve one.'"
                )
            return (
                f"{name} {epithet} bares his teeth. 'Fresh meat. I'll remember your face, {who}.'"
            )

        # From here on the member holds a real grievance — cite the worst one.
        wrong = grievances[0] if grievances else "what you did"

        if grudge_level == SLIGHTED:
            # A single wrong: a threat that references the grievance directly.
            if contempt:
                return (
                    f"{name} {epithet} taps the flat of his blade against his palm. "
                    f"'I know {wrong}, {who}. A warlord does not forget an insult "
                    "from something so small. Run while you can.'"
                )
            return (
                f"{name} {epithet} spits at your feet. "
                f"'You. I haven't settled {wrong}, {who}. Watch your back in the dark.'"
            )

        # GRUDGING — a revenge vow that names the SPECIFIC wrong remembered.
        if contempt:
            return (
                f"{name} {epithet} rises from his throne of skulls, slow and cold. "
                f"'You dare stand before me after {wrong}? I have crushed warlords "
                f"for less, {who}. This time you do not walk away.'"
            )
        return (
            f"{name} {epithet} drags his blade across the stone. "
            f"'You. I haven't forgotten {wrong}. This time you don't crawl away, {who}.'"
        )

    # ---- portable reputation (speak_reputation) --------------------------

    async def speak_reputation(
        self,
        *,
        npc_name: str,
        persona: str,
        ocean: dict[str, float],
        notoriety: str,
        reputation_deeds: list[str],
        player_line: str,
        player_name: str | None = None,
    ) -> str:
        """A fresh recruit's HEARSAY reaction to the player's portable notoriety.

        This member has never fought the player — it reacts to ``notoriety``
        (UNKNOWN / KNOWN / NOTORIOUS) read off the player's ``player.soul`` and,
        when the record is dirty, names a ``reputation_deeds`` entry. Name-aware
        via ``npc_name`` (the recruit's own name), so the bravado is personal.
        """
        who = player_name or "stranger"
        # Prefer the identity baked into this engine; fall back to the name the
        # kernel passes (they are the same member — belt and braces).
        name = self.name or npc_name

        if notoriety == UNKNOWN:
            return (
                f"{name} hefts his axe and grins. "
                f"'Never heard of you, {who}. Good. I like breaking in new blood.'"
            )

        if notoriety == KNOWN:
            return (
                f"{name} narrows his eyes. "
                f"'Your name's been in the war-camps, {who}. Some of these curs "
                "flinch at it. Not me. Names don't bleed.'"
            )

        # NOTORIOUS — the recruit cites the rumor and postures against the fear.
        deed = reputation_deeds[0] if reputation_deeds else "cut a bloody road"
        return (
            f"{name} spits. "
            f"'They say you {deed}, {who}. The others fear you. I don't. "
            "Come find out what that costs.'"
        )
