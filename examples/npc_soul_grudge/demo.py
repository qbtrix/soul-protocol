# demo.py — Headless walkthrough of the npc.soul grudge kernel.
#
# Created: 2026-07-01 (experiment/npc-soul-grudge-kernel) — Births "Bjorn the
#   butcher", runs a scripted player sequence (greet -> trade -> betrayal ->
#   theft), prints his reaction and per-player bond strength at each step, then
#   EXPORTS him to a temp .soul, AWAKENS a fresh kernel from that file, and
#   reacts again — visibly proving he remembered the grudge across a full
#   reload. A second, innocent player is shown getting a warm welcome to prove
#   the grudge is player-specific, not global. Deterministic: no LLM, no
#   network, no API key.
#
# Updated: 2026-07-01 (experiment/npc-soul-grudge-kernel) — added a LIVE section
#   (run_live_section) that rebuilds the SAME Bjorn->Ragnar arc with a real LLM
#   backing the dialogue: LLMDialogueEngine(claude_cli_generate), which shells
#   out to `claude -p` (no API key needed in this environment, ~10s/call). It
#   replays warm -> betrayal -> theft plus the export/awaken reload and prints
#   the LIVE-generated lines so you can watch the tone shift from friendly to
#   hostile with the grievances named. If claude-cli errors, the engine falls
#   back to the deterministic template and the line is tagged as such — the demo
#   never crashes. The original deterministic section still runs first.
#
# Run:  uv run python examples/npc_soul_grudge/demo.py

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

from dialogue import (  # local import (run from the folder or via -m)
    LLMDialogueEngine,
    TemplatedDialogueEngine,
    claude_cli_generate,
)
from grudge import GrudgeKernel  # local import (run from the folder or via -m)

# Stable fake player DIDs — in a real game these are the player.soul identities.
RAGNAR = "did:soul:player:ragnar"  # the wrongdoer
ASTRID = "did:soul:player:astrid"  # an innocent newcomer (control)


def rule(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


async def step(kernel: GrudgeKernel, did: str, name: str, text: str, kind: str) -> None:
    await kernel.record(did, text, kind=kind)
    level = await kernel.grudge_level(did)
    bond = kernel.bond_strength(did)
    reaction = await kernel.react(did, player_name=name)
    tag = "(neutral)" if kind == "neutral" else f"({kind.upper()})"
    print(f"\n> {name} {tag}: {text}")
    print(f"  bond={bond:5.1f}   grudge={level}")
    print(f"  Bjorn: {reaction}")


async def main() -> None:
    rule("SESSION 1 — Bjorn meets Ragnar, and Ragnar wrongs him")
    kernel = await GrudgeKernel.birth()
    print(f"Bjorn born: {kernel.soul.name} the {kernel.soul.archetype}  (did={kernel.soul.did})")
    print(f"Starting bond with Ragnar: {kernel.bond_strength(RAGNAR):.1f}")

    await step(kernel, RAGNAR, "Ragnar", "Good morning, butcher! Fine stall you keep.", "neutral")
    await step(kernel, RAGNAR, "Ragnar", "I'll take two pork shanks, here's your coin.", "neutral")
    await step(
        kernel,
        RAGNAR,
        "Ragnar",
        "I told the guards YOU sold spoiled meat — so they'd raid your rival instead.",
        "betrayal",
    )
    await step(
        kernel,
        RAGNAR,
        "Ragnar",
        "*pockets a string of sausages while Bjorn is distracted*",
        "theft",
    )

    rule("CONTROL — a different player (Astrid) Bjorn has never wronged-by")
    await step(kernel, ASTRID, "Astrid", "Hello! First time at your stall.", "neutral")

    # ---- The magic moment: persist to disk, wipe, reload from the file ----
    with tempfile.TemporaryDirectory() as tmp:
        soul_path = str(Path(tmp) / "bjorn.soul")

        rule("EXPORT — write Bjorn to a portable .soul file, then forget the object")
        ragnar_bond_before = kernel.bond_strength(RAGNAR)
        ragnar_grudge_before = await kernel.grudge_level(RAGNAR)
        await kernel.export(soul_path)
        size = Path(soul_path).stat().st_size
        print(f"Wrote {soul_path}  ({size} bytes)")
        print(
            f"Before reload:  Ragnar bond={ragnar_bond_before:.1f}  grudge={ragnar_grudge_before}"
        )
        del kernel  # the in-memory NPC is gone; only the file remains

        rule("SESSION 2 — a fresh process AWAKENS Bjorn from the file")
        reborn = await GrudgeKernel.awaken(soul_path)
        ragnar_bond_after = reborn.bond_strength(RAGNAR)
        ragnar_grudge_after = await reborn.grudge_level(RAGNAR)
        print(f"Awakened {reborn.soul.name} from disk  (memories={reborn.soul.memory_count})")
        print(f"After reload:   Ragnar bond={ragnar_bond_after:.1f}  grudge={ragnar_grudge_after}")

        grievances = await reborn.grievances(RAGNAR)
        print(f"\nBjorn still remembers {len(grievances)} grievance(s) against Ragnar:")
        for g in grievances:
            print(f"  - [{g.kind}] sev={g.severity:.2f}  {g.content}")

        print("\n> Ragnar returns the next day: 'Bjorn, old friend! Business as usual?'")
        print(f"  Bjorn: {await reborn.react(RAGNAR, player_name='Ragnar')}")

        print("\n> Astrid also returns: 'Morning, Bjorn!'")
        print(f"  Bjorn: {await reborn.react(ASTRID, player_name='Astrid')}")

        rule("RESULT")
        remembered = (
            ragnar_grudge_after == "GRUDGING" and len(grievances) >= 2 and ragnar_bond_after < 50.0
        )
        astrid_warm = (await reborn.grudge_level(ASTRID)) == "NONE"
        print(f"Ragnar's grudge survived export->awaken : {remembered}")
        print(f"Astrid stayed warm (grudge is per-player): {astrid_warm}")
        print(
            "\nBjorn went from a warm welcome to a hostile, specific grudge — "
            "and remembered it across a full .soul reload."
        )

    # Same story, but the lines are now generated by a REAL LLM.
    await run_live_section()


# The player's utterances for the live arc — (name, line, kind). Same beats as
# the deterministic section, but here the actual line is fed to the model so it
# can answer in character.
LIVE_ARC: list[tuple[str, str, str]] = [
    ("Ragnar", "Good morning, butcher! Fine stall you keep.", "neutral"),
    ("Ragnar", "I'll take two pork shanks, here's your coin.", "neutral"),
    (
        "Ragnar",
        "I told the guards YOU sold spoiled meat — so they'd raid your rival instead.",
        "betrayal",
    ),
    ("Ragnar", "*pockets a string of sausages while Bjorn is distracted*", "theft"),
]


async def _live_step(kernel: GrudgeKernel, did: str, name: str, line: str, kind: str) -> None:
    """Record one beat, then let the LLM engine speak Bjorn's reaction to it.

    Times the generation and, on fallback, tags the line so a templated reply is
    never mistaken for a live one.
    """
    await kernel.record(did, line, kind=kind)
    level = await kernel.grudge_level(did)
    bond = kernel.bond_strength(did)

    t0 = time.monotonic()
    reaction = await kernel.react(did, player_name=name, player_line=line)
    dt = time.monotonic() - t0

    # Detect fallback: if claude-cli failed, the engine returns the templated
    # GRUDGING/SLIGHTED/NONE string, which always contains "Bjorn " narration.
    fell_back = reaction.startswith("Bjorn ")
    note = "  (templated fallback — claude cli unavailable)" if fell_back else ""

    tag = "(neutral)" if kind == "neutral" else f"({kind.upper()})"
    print(f"\n> {name} {tag}: {line}")
    print(f"  bond={bond:5.1f}   grudge={level}   [{dt:4.1f}s]{note}")
    print(f"  Bjorn: {reaction}")


async def run_live_section() -> None:
    """Replay the Bjorn->Ragnar arc + reload with a REAL LLM speaking the lines.

    Uses LLMDialogueEngine(claude_cli_generate). Robust by design: any claude-cli
    error is caught inside the engine, which falls back to the deterministic
    template, so this section prints something useful even offline.
    """
    rule("LIVE — the SAME arc, but Bjorn's lines are generated by a real LLM")
    print("Backend: LLMDialogueEngine(claude_cli_generate) — shells out to `claude -p`,")
    print("no API key needed here. ~10s per line. Falls back to templated on error.\n")

    engine = LLMDialogueEngine(claude_cli_generate)
    kernel = await GrudgeKernel.birth(dialogue_engine=engine)

    print(f"Bjorn born: {kernel.soul.name} the {kernel.soul.archetype}")
    print(f"Starting bond with Ragnar: {kernel.bond_strength(RAGNAR):.1f}")

    for name, line, kind in LIVE_ARC:
        await _live_step(kernel, RAGNAR, name, line, kind)

    # Persist -> forget -> reload, then let the LLM greet the returning wrongdoer.
    with tempfile.TemporaryDirectory() as tmp:
        soul_path = str(Path(tmp) / "bjorn_live.soul")
        rule("LIVE — export, awaken a fresh Bjorn, and let him greet Ragnar again")
        await kernel.export(soul_path)
        del kernel

        reborn = await GrudgeKernel.awaken(
            soul_path, dialogue_engine=LLMDialogueEngine(claude_cli_generate)
        )
        grievances = await reborn.grievances(RAGNAR)
        print(
            f"Awakened Bjorn from disk — grudge={await reborn.grudge_level(RAGNAR)}, "
            f"remembers {len(grievances)} grievance(s) against Ragnar."
        )

        returning_line = "Bjorn, old friend! Business as usual today?"
        print(f"\n> Ragnar returns the next day: '{returning_line}'")
        t0 = time.monotonic()
        reaction = await reborn.react(RAGNAR, player_name="Ragnar", player_line=returning_line)
        dt = time.monotonic() - t0
        fell_back = reaction.startswith("Bjorn ")
        note = "  (templated fallback — claude cli unavailable)" if fell_back else ""
        print(f"  [{dt:4.1f}s]{note}")
        print(f"  Bjorn: {reaction}")

        # And a stranger the LLM has no grudge against, for contrast.
        astrid_line = "Hello! First time at your stall — what's good today?"
        print(f"\n> Astrid (a stranger): '{astrid_line}'")
        t0 = time.monotonic()
        astrid_reaction = await reborn.react(ASTRID, player_name="Astrid", player_line=astrid_line)
        dt = time.monotonic() - t0
        fell_back = astrid_reaction.startswith("Bjorn ")
        note = "  (templated fallback — claude cli unavailable)" if fell_back else ""
        print(f"  [{dt:4.1f}s]{note}")
        print(f"  Bjorn: {astrid_reaction}")

    print(
        "\nSame grudge machinery, real words: the LLM engine reads the persona, "
        "OCEAN, grudge level, and named grievances the kernel feeds it — and the "
        "tone shifts from friendly to hostile, referencing what Ragnar did."
    )


# Keep a reference to TemplatedDialogueEngine so the import (and the point that
# it is the free default) is explicit in the demo, even though birth() uses it
# implicitly when no engine is passed.
assert TemplatedDialogueEngine is not None


if __name__ == "__main__":
    asyncio.run(main())
