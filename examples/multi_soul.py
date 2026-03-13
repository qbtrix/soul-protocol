# multi_soul.py — Demonstrates multi-soul management introduced in v0.2.3.
#
# Shows how to create, manage, and switch between multiple souls,
# track bond strength, and use memory categories.
#
# Usage:
#   python examples/multi_soul.py

from __future__ import annotations

import asyncio

from soul_protocol import Interaction, MemoryType, Soul


async def main() -> None:
    # -- Create two souls with different personalities
    aria = await Soul.birth(
        name="Aria",
        archetype="The Thoughtful Companion",
        values=["curiosity", "empathy", "honesty"],
    )

    luna = await Soul.birth(
        name="Luna",
        archetype="The Creative Writer",
        values=["creativity", "imagination", "wit"],
    )

    print(f"Born: {aria.name} (DID: {aria.did[:20]}...)")
    print(f"Born: {luna.name} (DID: {luna.did[:20]}...)")

    # -- Interact with Aria
    await aria.observe(
        Interaction(
            user_input="I'm working on a machine learning project",
            agent_output="That sounds exciting! What kind of ML are you exploring?",
            channel="demo",
        )
    )
    print(f"\n{aria.name}: mood={aria.state.mood.value}, energy={aria.state.energy:.0f}%")

    # -- Interact with Luna
    await luna.observe(
        Interaction(
            user_input="Can you help me write a short story?",
            agent_output="I'd love to! What genre are you thinking?",
            channel="demo",
        )
    )
    print(f"{luna.name}: mood={luna.state.mood.value}, energy={luna.state.energy:.0f}%")

    # -- Store memories with different categories
    await aria.remember(
        "User is working on a machine learning project",
        type=MemoryType.SEMANTIC,
        importance=7,
    )
    await luna.remember(
        "User wants help writing a short story",
        type=MemoryType.SEMANTIC,
        importance=6,
    )

    # -- Recall across souls
    aria_memories = await aria.recall("machine learning", limit=3)
    luna_memories = await luna.recall("story", limit=3)
    print(f"\nAria recalls {len(aria_memories)} memory(ies) about ML")
    print(f"Luna recalls {len(luna_memories)} memory(ies) about stories")

    # -- Export both souls
    await aria.export("aria.soul")
    await luna.export("luna.soul")
    print("\nExported: aria.soul, luna.soul")

    # -- Awaken and verify persistence
    aria2 = await Soul.awaken("aria.soul")
    memories = await aria2.recall("machine learning", limit=3)
    print(f"Reloaded {aria2.name}: {len(memories)} ML memory(ies) preserved")


if __name__ == "__main__":
    asyncio.run(main())
