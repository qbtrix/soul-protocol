# __init__.py — Demo content for the Game Profile: Bjorn the butcher, the
#   tavern, and a vendor pricing table.
#
# Created: 2026-09-11 (fix/game-profile-demo-defaults) — The profile under
#   soul_protocol.profiles.game ships mechanisms only (grudge kernel, dialogue
#   seam, world, cost meter). Everything that used to be a baked-in default
#   there (the Bjorn name/archetype/persona, his scripted lines, the "tavern"
#   start zone, the $/1M-token vendor rates) lives here so the examples can
#   keep telling the Butcher story without the library carrying it.

from __future__ import annotations

from soul_protocol.profiles.game import NONE, SLIGHTED, GrudgeKernel, TemplatedDialogueEngine

BJORN_NAME = "Bjorn"
BJORN_ARCHETYPE = "The Butcher"
BJORN_PERSONA = (
    "I am Bjorn, a proud, gruff medieval butcher. I keep an honest stall and a long memory."
)

# Every soul starts here until GameWorld.move() re-homes it.
TAVERN = "tavern"

# $ per 1M tokens as (input_rate, output_rate). claude-cli (local, no key) and
# gemini-nano (on-device) are $0; the meter still counts their tokens so
# CostMeter.project() can re-price the same session under a paid model.
PRICING: dict[str, tuple[float, float]] = {
    "deepseek-v3.2": (0.14, 0.28),
    "gemini-flash-lite": (0.10, 0.40),
    "gemini-nano": (0.0, 0.0),
    "claude-cli": (0.0, 0.0),
}


class ButcherDialogueEngine(TemplatedDialogueEngine):
    """Bjorn's scripted lines. Reputation lines fall through to the generic engine."""

    async def speak(
        self,
        *,
        npc_name: str,
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
        cited = ", ".join(grievances[:3]) if grievances else "what you did"
        return (
            f"Bjorn's cleaver thuds into the block. 'You have the gall to show "
            f"your face here, {who}? I remember {cited}. You'll get nothing from "
            "me but the door.'"
        )


async def birth_bjorn(dialogue_engine=None) -> GrudgeKernel:
    """Bjorn the Butcher; templated lines are his own unless an engine is passed."""
    return await GrudgeKernel.birth(
        name=BJORN_NAME,
        archetype=BJORN_ARCHETYPE,
        persona=BJORN_PERSONA,
        dialogue_engine=dialogue_engine or ButcherDialogueEngine(),
    )
