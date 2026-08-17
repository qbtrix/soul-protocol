# dialogue.py — Pluggable DialogueEngine seam for the npc.soul grudge kernel.
#
# Created: 2026-07-01 (experiment/npc-soul-grudge-kernel) — Extracts the NPC's
#   spoken reaction behind a Protocol so it can be swapped from the deterministic
#   template (free, offline, the DEFAULT that keeps the existing tests green) to
#   a REAL LLM without touching the grudge logic. Mirrors Soul Protocol's own
#   cognitive-adapter pattern: a narrow Protocol + a zero-dependency fallback +
#   an optional real backend, with the real backend falling back to the template
#   on any failure so the demo never crashes.
#
#   Engines:
#     * TemplatedDialogueEngine — the ORIGINAL deterministic reaction, lifted
#       verbatim out of GrudgeKernel._render/_name_wrong. Default. No LLM, no
#       network, no cost.
#     * LLMDialogueEngine(generate) — builds a strong in-character prompt from
#       (persona + OCEAN + grudge level + grievances + player line), calls the
#       injected async `generate(prompt) -> str`, returns its line. On empty
#       output or ANY exception it FALLS BACK to the templated engine.
#     * claude_cli_generate — a working no-key `generate` for THIS environment:
#       shells out to `claude -p "<prompt>"` (verified: text out, exit 0, no
#       ANTHROPIC_API_KEY needed here). ~10s/call.
#
#   soul-protocol also ships real adapters at
#   src/soul_protocol/runtime/cognitive/adapters/ (ollama.py, anthropic.py,
#   litellm.py, _callable.py, _auto.py). Any of those can back `generate` when a
#   key/endpoint exists — but claude_cli_generate is the one that works here
#   with no configuration.
#
# Updated: 2026-07-01 (experiment/npc-soul-grudge-kernel) — PLAYER.SOUL SYMMETRY.
#   Added speak_reputation(...) to the DialogueEngine seam: how a FRESH NPC (who
#   never met this player, so holds no personal grudge) voices its reaction to
#   the player's PORTABLE REPUTATION read off their player.soul. It is distinct
#   from speak(): the tone is "I've heard of you" (hearsay), not "you wronged ME"
#   (personal), and it is NPC-name-aware + trade-neutral so ANY npc.soul (Astrid
#   the innkeeper, not just Bjorn the butcher) reads right. speak() is untouched
#   — byte-for-byte identical — so the original 7 tests stay green. The templated
#   engine renders reputation deterministically; the LLM engine builds a
#   reputation-specific prompt (persona + OCEAN + notoriety + the deeds) and,
#   like speak(), falls back to the template on empty/any error.
#
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel) — GRADUATED from
#   examples/npc_soul_grudge/ into soul_protocol.profiles.game (git mv, history
#   preserved). Sibling imports converted to package-relative (from .grudge /
#   .player import ...); behavior unchanged. Spec: spec/profiles/game.md.

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

# Grudge-level constants live in grudge.py; import them so the templated engine
# renders the exact same three branches the kernel always did.
from .grudge import GRUDGING, NONE, SLIGHTED, Grievance

# Notoriety bands live in player.py (the reputation side of the ledger). Imported
# so the reputation engine renders the UNKNOWN / KNOWN / NOTORIOUS branches. This
# import is acyclic: player.py imports only SEVERITY from grudge.py, and grudge.py
# imports dialogue/player lazily (inside methods), never at module top.
from .player import KNOWN, NOTORIOUS, UNKNOWN


@runtime_checkable
class DialogueEngine(Protocol):
    """How an NPC turns its state into a spoken line.

    The whole grudge machinery (bond, grievances, persistence) is unchanged —
    this seam only decides how the *words* are produced. A templated engine is
    deterministic and free; an LLM engine is vivid and in-character.
    """

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
        """Return the NPC's spoken reaction.

        ``grievances`` are human-readable grievance descriptions (worst first),
        already scoped to this player. ``player_line`` is what the player just
        said. ``grudge_level`` is one of NONE / SLIGHTED / GRUDGING.
        """
        ...

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
        """Return a FRESH NPC's reaction to a player's PORTABLE REPUTATION.

        The NPC has never met this player, so this is hearsay, not a personal
        grudge: it reacts to ``notoriety`` (UNKNOWN / KNOWN / NOTORIOUS) and, when
        the record is dirty, cites ``reputation_deeds`` (worst-first descriptions
        read off the player's ``player.soul``). ``npc_name`` lets any NPC — not
        just Bjorn — voice it.
        """
        ...


class TemplatedDialogueEngine:
    """The ORIGINAL deterministic reaction, extracted into an engine.

    This is the default so the existing behavior — and the existing 5 tests —
    stay exactly as they were, at zero cost. The three branches (NONE /
    SLIGHTED / GRUDGING) and the "name the wrong" phrasing are lifted verbatim
    from the pre-seam GrudgeKernel.
    """

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
        who = player_name or "stranger"

        if grudge_level == NONE:
            return (
                f"Bjorn wipes his hands and smiles. 'Welcome to my stall, {who}! "
                "Finest cuts in town.'"
            )

        if grudge_level == SLIGHTED:
            return (
                f"Bjorn's smile thins. He keeps one eye on {who}. "
                "'...You again. State your business and be quick about it.'"
            )

        # GRUDGING — cite the remembered wrongs, worst first. ``grievances`` is
        # already worst-first and pre-phrased ("how you betrayed me", ...).
        cited = ", ".join(grievances[:3]) if grievances else "what you did"
        return (
            f"Bjorn's cleaver thuds into the block. 'You have the gall to show "
            f"your face here, {who}? I remember {cited}. You'll get nothing from "
            "me but the door.'"
        )

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
        """Deterministic reputation reaction — NPC-name-aware and trade-neutral.

        Distinct from :meth:`speak`: the wording is hearsay ("word travels",
        "I've heard how you...") because this NPC never met the player. Mapped
        off notoriety, which the kernel derived from the player's PUBLIC deeds.
        """
        who = player_name or "stranger"

        if notoriety == UNKNOWN:
            return (
                f"{npc_name} looks up with an easy nod. 'Welcome, {who} — "
                "haven't seen your face before. Sit, you're among friends.'"
            )

        if notoriety == KNOWN:
            return (
                f"{npc_name} pauses, wiping the counter, and studies {who}. "
                "'...I've heard your name, and not in praise. Mind yourself under my roof.'"
            )

        # NOTORIOUS — cite the reputation the player carries with them.
        cited = ", ".join(reputation_deeds[:3]) if reputation_deeds else "what you've done"
        return (
            f"{npc_name} sets down the jug, hard. 'I know who you are, {who}. "
            f"Word travels — they say you {cited}. We want no trouble like that "
            "here. Move along.'"
        )


class LLMDialogueEngine:
    """Produce the NPC's line with a REAL LLM via an injected async callable.

    ``generate`` is any ``async (prompt: str) -> str`` — an adapter, an SDK
    call, or :func:`claude_cli_generate`. The engine's job is only to (a) build
    a strong in-character prompt from the NPC's full state and (b) fall back to
    the templated engine on empty output or ANY error, so a flaky model or a
    missing binary never crashes the game loop.
    """

    def __init__(self, generate) -> None:
        self._generate = generate
        self._fallback = TemplatedDialogueEngine()

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
        prompt = self.build_prompt(
            persona=persona,
            ocean=ocean,
            grudge_level=grudge_level,
            grievances=grievances,
            player_line=player_line,
            player_name=player_name,
        )
        try:
            line = await self._generate(prompt)
        except Exception:
            # Never crash the demo/game on a model or transport failure — the
            # deterministic template is always available.
            return await self._fallback.speak(
                persona=persona,
                ocean=ocean,
                grudge_level=grudge_level,
                grievances=grievances,
                player_line=player_line,
                player_name=player_name,
            )

        line = (line or "").strip()
        if not line:
            return await self._fallback.speak(
                persona=persona,
                ocean=ocean,
                grudge_level=grudge_level,
                grievances=grievances,
                player_line=player_line,
                player_name=player_name,
            )
        return line

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
        """LLM reaction to a player's PORTABLE REPUTATION (see the Protocol).

        Builds a reputation-specific prompt (the deeds are HEARSAY the NPC never
        witnessed) and, exactly like :meth:`speak`, falls back to the templated
        reputation reaction on empty output or ANY error.
        """
        prompt = self.build_reputation_prompt(
            npc_name=npc_name,
            persona=persona,
            ocean=ocean,
            notoriety=notoriety,
            reputation_deeds=reputation_deeds,
            player_line=player_line,
            player_name=player_name,
        )
        try:
            line = await self._generate(prompt)
        except Exception:
            return await self._fallback.speak_reputation(
                npc_name=npc_name,
                persona=persona,
                ocean=ocean,
                notoriety=notoriety,
                reputation_deeds=reputation_deeds,
                player_line=player_line,
                player_name=player_name,
            )

        line = (line or "").strip()
        if not line:
            return await self._fallback.speak_reputation(
                npc_name=npc_name,
                persona=persona,
                ocean=ocean,
                notoriety=notoriety,
                reputation_deeds=reputation_deeds,
                player_line=player_line,
                player_name=player_name,
            )
        return line

    # -- prompt construction (pure; unit-testable via the spy) ---------------

    @staticmethod
    def build_prompt(
        *,
        persona: str,
        ocean: dict[str, float],
        grudge_level: str,
        grievances: list[str],
        player_line: str,
        player_name: str | None = None,
    ) -> str:
        """Build the in-character prompt fed to the model.

        Kept static and side-effect-free so a test can assert the exact context
        the LLM *would* receive (grievance content + grudge level) without any
        model call.
        """
        ocean_desc = _describe_ocean(ocean)
        if grievances:
            history = "Your history with this person: " + "; ".join(grievances) + "."
        else:
            history = "Your history with this person: no history — a stranger."

        feeling = _describe_feeling(grudge_level)
        who = player_name or "this person"

        return (
            "You are Bjorn, a proud, gruff medieval butcher. You keep an honest "
            "stall and a long memory.\n"
            f"Your OCEAN personality: {ocean_desc}.\n"
            f"{history}\n"
            f"Your current feeling toward {who}: {feeling}.\n"
            f"They just said: '{player_line}'.\n"
            f"Respond IN CHARACTER as Bjorn in 1-2 sentences. If you hold a "
            "grudge, be cold or hostile and reference specifically what they did. "
            "If they are a stranger, be gruff but fair. Output ONLY Bjorn's "
            "spoken words, no narration, no quotation marks, no stage directions."
        )

    @staticmethod
    def build_reputation_prompt(
        *,
        npc_name: str,
        persona: str,
        ocean: dict[str, float],
        notoriety: str,
        reputation_deeds: list[str],
        player_line: str,
        player_name: str | None = None,
    ) -> str:
        """Build the reputation prompt fed to the model.

        Persona-driven and NPC-name-aware (this path serves any NPC, e.g. Astrid
        the innkeeper), and frames the deeds as HEARSAY — the NPC never met this
        player. Static + side-effect-free so the spy test can assert the model
        receives the notoriety AND the reputation deeds without a model call.
        """
        ocean_desc = _describe_ocean(ocean)
        who = player_name or "this stranger"
        standing = _describe_notoriety(notoriety)

        if reputation_deeds:
            rumor = (
                f"You have NEVER met {who}, but their reputation precedes them. "
                "Word around the region is that they have: " + "; ".join(reputation_deeds) + "."
            )
        else:
            rumor = (
                f"You have never met {who}, and you have heard nothing ill of "
                "them — their name carries no bad reputation."
            )

        return (
            f"{persona}\n"
            f"Your name is {npc_name}.\n"
            f"Your OCEAN personality: {ocean_desc}.\n"
            f"{rumor}\n"
            f"Your standing toward {who} based on their reputation alone: {standing}.\n"
            f"They just said: '{player_line}'.\n"
            f"Respond IN CHARACTER as {npc_name} in 1-2 sentences. You are "
            "reacting to their REPUTATION, not to anything they did to you "
            "personally. If their reputation is bad, be wary or cold and allude "
            "to what you have heard they did. If their name is clean, be warm and "
            f"welcoming. Output ONLY {npc_name}'s spoken words, no narration, no "
            "quotation marks, no stage directions."
        )


def _describe_ocean(ocean: dict[str, float]) -> str:
    """Render OCEAN traits as a compact natural-language descriptor for the
    prompt (e.g. 'low openness, high conscientiousness, ...')."""
    order = [
        ("openness", "openness"),
        ("conscientiousness", "conscientiousness"),
        ("extraversion", "extraversion"),
        ("agreeableness", "agreeableness"),
        ("neuroticism", "neuroticism"),
    ]
    parts: list[str] = []
    for key, label in order:
        if key not in ocean:
            continue
        v = ocean[key]
        band = "high" if v >= 0.66 else "low" if v <= 0.33 else "moderate"
        parts.append(f"{band} {label} ({v:.2f})")
    return ", ".join(parts) if parts else "balanced"


def _describe_feeling(grudge_level: str) -> str:
    return {
        NONE: "neutral — no grudge, you have no quarrel with them",
        SLIGHTED: "wary and cool — they have wronged you once and you have not forgotten",
        GRUDGING: "cold and hostile — they have wronged you badly and repeatedly",
    }.get(grudge_level, grudge_level)


def _describe_notoriety(notoriety: str) -> str:
    return {
        UNKNOWN: "neutral — you have heard nothing about them, they are a clean stranger",
        KNOWN: "guarded — their name carries some ill repute you have caught wind of",
        NOTORIOUS: "cold and unwelcoming — they are infamous for the wrongs they have done",
    }.get(notoriety, notoriety)


# ---------------------------------------------------------------------------
# A working no-key backend for THIS environment.
# ---------------------------------------------------------------------------
async def claude_cli_generate(prompt: str) -> str:
    """Generate text via the local ``claude`` CLI — no API key required here.

    Verified in this environment: ``claude -p "<prompt>" </dev/null`` returns
    text on stdout with exit 0 and needs no ANTHROPIC_API_KEY. ~10s per call.
    Raises on non-zero exit or empty output so LLMDialogueEngine's fallback can
    take over cleanly.
    """
    proc = await asyncio.create_subprocess_exec(
        "claude",
        "-p",
        prompt,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0 or not out.strip():
        raise RuntimeError(f"claude cli failed: {err.decode()[:200]}")
    return out.decode().strip()


def phrase_grievances(grievances: list[Grievance]) -> list[str]:
    """Turn recovered Grievance records into human-readable phrases, worst
    first — the shared shape both engines consume via ``speak(grievances=...)``.

    Reuses the original "name the wrong" phrasing so the templated branch is
    byte-for-byte unchanged, while the LLM engine gets the same clean history
    line to weave into its prompt.
    """
    worst = sorted(grievances, key=lambda g: g.severity, reverse=True)
    return [_name_wrong(g.kind) for g in worst]


def _name_wrong(kind: str) -> str:
    return {
        "insult": "how you mocked me",
        "theft": "what you stole from my stall",
        "betrayal": "how you betrayed me",
    }.get(kind, f"the {kind}")
