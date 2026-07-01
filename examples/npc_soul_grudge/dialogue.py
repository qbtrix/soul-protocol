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

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

# Grudge-level constants live in grudge.py; import them so the templated engine
# renders the exact same three branches the kernel always did.
from grudge import GRUDGING, NONE, SLIGHTED, Grievance


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
