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
# Run:  uv run python examples/npc_soul_grudge/demo.py

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

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


if __name__ == "__main__":
    asyncio.run(main())
