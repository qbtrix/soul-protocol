# grudge.py — Experimental "npc.soul grudge kernel" on top of the real Soul Protocol.
#
# Created: 2026-07-01 (experiment/npc-soul-grudge-kernel) — A thin, deterministic,
#   zero-LLM / zero-network wrapper around ONE real Soul that turns it into a
#   game NPC who holds a grudge. A player who wrongs the NPC weakens its bond and
#   plants episodic "grievance" memories; those memories survive a .soul
#   export -> awaken round-trip, so the NPC still remembers and reacts with
#   hostility in the NEXT session. Reuses Soul unchanged — no core files touched.
#
# Updated: 2026-07-01 (experiment/npc-soul-grudge-kernel) — react() now delegates
#   its SPOKEN line to a pluggable DialogueEngine (dialogue.py). The default is
#   TemplatedDialogueEngine (the original deterministic branches, verbatim), so
#   behavior and the existing tests are unchanged and it still runs free. Pass a
#   dialogue_engine=LLMDialogueEngine(generate) to get REAL in-character lines.
#   All grudge state (bond, grievances, persistence) is untouched by the seam.
#
# Design notes (API verified against soul-protocol source, 2026-07-01):
#   * The runtime MemoryEntry has NO free-form `.metadata` dict, and
#     Soul.remember() takes no `metadata=` kwarg (extra kwargs are silently
#     dropped by Pydantic's default extra="ignore"). So grievance tags are
#     carried on the REAL fields that DO persist: `entities` (kind + player_did
#     + a "grudge" marker), `user_id` (per-player attribution — Soul's native
#     per-user scoping, which also gives each player their own Bond), and a
#     machine-parseable marker embedded in `content`.
#   * Grievances are stored with visibility=PUBLIC. This is deliberate: recall()
#     filters BONDED memories out once bond_strength < bond_threshold (default
#     30). Since wronging the NPC WEAKENS the bond below 30, storing grievances
#     as BONDED would hide them exactly when the grudge peaks. PUBLIC always
#     passes filter_by_visibility(), and it's semantically right — a butcher's
#     grudge is a hostile fact he acts on openly, not a tender bonded secret.
#   * Per-player bond: Soul.bond is a BondRegistry. `bond.for_user(did)` /
#     `bond_for(did)` returns a per-player Bond seeded at strength=50;
#     `bond.weaken(amount, user_id=did)` routes to it. `soul.observe(...,
#     user_id=did)` strengthens the same per-player bond. Both survive
#     export via SoulConfig.bonds_per_user.

from __future__ import annotations

import re
from dataclasses import dataclass

from soul_protocol import Interaction, MemoryType, MemoryVisibility, Soul

# ---------------------------------------------------------------------------
# Transgression taxonomy — deterministic severity + emotion per kind.
# ---------------------------------------------------------------------------
# "neutral" is the only non-grievance kind: it is observed (strengthens the
# bond a little via the normal pipeline) but plants no grudge memory.
SEVERITY: dict[str, float] = {
    "neutral": 0.0,
    "insult": 0.4,
    "theft": 0.7,
    "betrayal": 0.9,
}

# Emotion label stamped on the grievance memory. Deterministic, no LLM.
EMOTION: dict[str, str] = {
    "insult": "offended",
    "theft": "angry",
    "betrayal": "betrayed",
}

# How hard each transgression weakens the per-player bond (linear, sharp —
# matches Bond.weaken which is linear by design). Scaled from severity so a
# betrayal costs far more trust than an insult.
BOND_DAMAGE: dict[str, float] = {
    "insult": 12.0,
    "theft": 20.0,
    "betrayal": 30.0,
}

# Marker embedded in grievance content so it's machine-recoverable after a
# round-trip even though MemoryEntry carries no structured metadata field.
# e.g. "[GRUDGE kind=betrayal severity=0.90]"
_MARKER_RE = re.compile(r"\[GRUDGE kind=(?P<kind>\w+) severity=(?P<sev>[0-9.]+)\]")

# Entity tag that marks a memory as a grievance (in addition to the kind and
# the player_did, both also stored as entities). Lets recall()/filters find
# grievances by entity without parsing content.
GRUDGE_TAG = "grudge"

# Grudge-level thresholds. Tuned so:
#   - 0 grievances                              -> NONE
#   - >=1 grievance but low cumulative severity -> SLIGHTED
#   - >=2 grievances OR high cumulative severity -> GRUDGING
_SLIGHTED_MIN_COUNT = 1
_GRUDGING_MIN_COUNT = 2
_GRUDGING_MIN_TOTAL_SEVERITY = 1.0

NONE = "NONE"
SLIGHTED = "SLIGHTED"
GRUDGING = "GRUDGING"


@dataclass
class Grievance:
    """A remembered wrong, recovered from a stored episodic memory."""

    memory_id: str
    kind: str
    severity: float
    content: str


class GrudgeKernel:
    """A thin grudge layer over ONE real Soul.

    Construct via :meth:`birth` (fresh NPC) or :meth:`awaken` (restore a
    previously exported ``.soul`` — the whole point of the experiment).
    """

    # Canonical persona text for the dialogue prompt. The `persona=` kwarg to
    # Soul.birth() is not retained on the runtime Soul (dropped by Pydantic's
    # extra="ignore"), so the kernel carries it explicitly for the LLM prompt.
    DEFAULT_PERSONA = (
        "I am Bjorn, a proud, gruff medieval butcher. I keep an honest stall and a long memory."
    )

    def __init__(
        self,
        soul: Soul,
        dialogue_engine=None,
        persona: str | None = None,
    ) -> None:
        self.soul = soul
        self.persona = persona or self.DEFAULT_PERSONA
        # Default to the deterministic templated engine (free, offline, keeps
        # the existing tests green). Imported lazily to avoid a circular import:
        # dialogue.py imports the grudge-level constants and Grievance from here.
        if dialogue_engine is None:
            from dialogue import TemplatedDialogueEngine

            dialogue_engine = TemplatedDialogueEngine()
        self._dialogue = dialogue_engine

    # ---- lifecycle -------------------------------------------------------

    @classmethod
    async def birth(
        cls,
        name: str = "Bjorn",
        archetype: str = "The Butcher",
        persona: str = DEFAULT_PERSONA,
        dialogue_engine=None,
    ) -> GrudgeKernel:
        """Birth a fresh NPC soul. Deterministic: no engine (HeuristicEngine),
        no network, no API key.

        Pass ``dialogue_engine`` to swap how the NPC's spoken line is produced
        (default: templated). The grudge machinery is identical either way.
        ``persona`` is carried on the kernel for the LLM prompt (Soul.birth does
        not retain it).
        """
        soul = await Soul.birth(
            name=name,
            archetype=archetype,
            values=["honesty", "fair trade", "loyalty", "respect"],
            ocean={
                "openness": 0.4,
                "conscientiousness": 0.8,
                "extraversion": 0.5,
                "agreeableness": 0.7,  # warm by default — has room to sour
                "neuroticism": 0.6,  # holds a grudge
            },
            communication={"warmth": "high", "formality": "low"},
            persona=persona,
        )
        return cls(soul, dialogue_engine=dialogue_engine, persona=persona)

    @classmethod
    async def awaken(
        cls,
        path: str,
        dialogue_engine=None,
        persona: str = DEFAULT_PERSONA,
    ) -> GrudgeKernel:
        """Awaken an NPC from an exported ``.soul`` file — grievances and
        per-player bonds come back with it. ``dialogue_engine`` optionally swaps
        the spoken-line backend (default: templated); ``persona`` restores the
        prompt persona text (not persisted in the ``.soul``)."""
        soul = await Soul.awaken(path)
        return cls(soul, dialogue_engine=dialogue_engine, persona=persona)

    async def export(self, path: str) -> None:
        """Export the NPC to a portable ``.soul`` archive."""
        await self.soul.export(path)

    # ---- bond introspection ---------------------------------------------

    def bond_strength(self, player_did: str) -> float:
        """Current bond strength (0-100) with this player. Reading via
        ``bond_for`` lazily creates the per-player bond at the default 50."""
        return self.soul.bond_for(player_did).bond_strength

    # ---- the loop --------------------------------------------------------

    async def record(self, player_did: str, text: str, kind: str = "neutral") -> None:
        """Record one player action.

        ``kind`` in {"neutral", "insult", "theft", "betrayal"}.

        Always observes the interaction (so the NPC 'lived' it and the normal
        pipeline runs). For a non-neutral kind, ALSO plants a high-importance
        episodic grievance (tagged, PUBLIC-visible, attributed to player_did)
        and weakens the per-player bond.
        """
        if kind not in SEVERITY:
            raise ValueError(f"unknown kind {kind!r}; expected one of {sorted(SEVERITY)}")

        # 1. The NPC always observes what happened, attributed to this player.
        #    A short in-character acknowledgement keeps the transcript readable.
        reply = self._observe_reply(kind)
        await self.soul.observe(
            Interaction.from_pair(user_input=text, agent_output=reply, channel="game"),
            user_id=player_did,
        )

        if kind == "neutral":
            return

        # 2. Plant the grievance as a durable, recoverable episodic memory.
        severity = SEVERITY[kind]
        marker = f"[GRUDGE kind={kind} severity={severity:.2f}]"
        content = f"{marker} {player_did} wronged me: {text}"
        await self.soul.remember(
            content,
            type=MemoryType.EPISODIC,
            importance=9,
            emotion=EMOTION[kind],
            entities=[GRUDGE_TAG, kind, player_did],
            visibility=MemoryVisibility.PUBLIC,  # survives a weakened bond
            user_id=player_did,
        )

        # 3. Weaken the per-player bond. Sharp + linear (Bond.weaken).
        self.soul.bond.weaken(BOND_DAMAGE[kind], user_id=player_did)

    async def grievances(self, player_did: str) -> list[Grievance]:
        """Recall this player's grievances from episodic memory.

        Recall is keyword/activation based (no metadata query), so we pull a
        wide episodic pool scoped to this player, then keep only entries that
        carry the grudge marker for this exact player_did.
        """
        results = await self.soul.recall(
            "grudge betrayal insult theft wronged",
            limit=50,
            types=[MemoryType.EPISODIC],
            user_id=player_did,
            # Read as the soul itself (requester_id=None => full visibility),
            # so this internal check never trips the bond gate. Grievances are
            # PUBLIC anyway, but this keeps the accessor robust.
        )
        out: list[Grievance] = []
        for entry in results:
            if GRUDGE_TAG not in entry.entities or player_did not in entry.entities:
                continue
            m = _MARKER_RE.search(entry.content)
            if not m:
                continue
            out.append(
                Grievance(
                    memory_id=entry.id,
                    kind=m.group("kind"),
                    severity=float(m.group("sev")),
                    content=entry.content,
                )
            )
        return out

    async def grudge_level(self, player_did: str) -> str:
        """Compute the grudge level from grievance count + cumulative severity."""
        grievances = await self.grievances(player_did)
        return self._level_from(grievances)

    async def react(
        self,
        player_did: str,
        player_name: str | None = None,
        player_line: str = "",
    ) -> str:
        """The NPC's spoken reaction, produced by the configured DialogueEngine.

        Tone follows the grudge level and, when GRUDGING, references the
        remembered wrongs. With the default TemplatedDialogueEngine this is the
        original deterministic string (no LLM). With an LLMDialogueEngine it is
        a real in-character line generated from the same state. ``player_line``
        (what the player just said) is only used by the LLM engine; the
        templated engine ignores it, so old call sites keep working.
        """
        from dialogue import phrase_grievances

        grievances = await self.grievances(player_did)
        level = self._level_from(grievances)
        return await self._dialogue.speak(
            persona=self.persona,
            ocean=self._ocean_dict(),
            grudge_level=level,
            grievances=phrase_grievances(grievances),
            player_line=player_line,
            player_name=player_name,
        )

    def _ocean_dict(self) -> dict[str, float]:
        """Bjorn's OCEAN traits as a plain dict for the dialogue prompt.

        Reads the real personality off the Soul (``soul.dna.personality``) so
        the LLM prompt reflects the actual trait vector (openness,
        conscientiousness, extraversion, agreeableness, neuroticism) that
        round-trips through ``.soul`` export, not a hardcoded copy.
        """
        p = self.soul.dna.personality
        return {
            "openness": p.openness,
            "conscientiousness": p.conscientiousness,
            "extraversion": p.extraversion,
            "agreeableness": p.agreeableness,
            "neuroticism": p.neuroticism,
        }

    # ---- pure helpers (deterministic) -----------------------------------

    @staticmethod
    def _level_from(grievances: list[Grievance]) -> str:
        count = len(grievances)
        total_sev = sum(g.severity for g in grievances)
        if count == 0:
            return NONE
        if count >= _GRUDGING_MIN_COUNT or total_sev >= _GRUDGING_MIN_TOTAL_SEVERITY:
            return GRUDGING
        if count >= _SLIGHTED_MIN_COUNT:
            return SLIGHTED
        return NONE

    @staticmethod
    def _observe_reply(kind: str) -> str:
        return {
            "neutral": "Aye, welcome. What'll it be?",
            "insult": "Mind your tongue in my shop.",
            "theft": "Thief! Put that back!",
            "betrayal": "You... after all I gave you.",
        }[kind]

    # The spoken reaction itself now lives behind the DialogueEngine seam
    # (dialogue.py): TemplatedDialogueEngine holds the original NONE/SLIGHTED/
    # GRUDGING branches, and phrase_grievances() the "name the wrong" phrasing.
    # react() delegates to self._dialogue.speak(...).
