# memory_categories.py — Demonstrates v0.2.3 memory extraction taxonomy and content layers.
#
# Shows the 7 memory categories, salience scoring, dedup pipeline,
# and progressive content loading (L0/L1/L2).
#
# Usage:
#   python examples/memory_categories.py

from __future__ import annotations

import asyncio

from soul_protocol import Interaction, Soul


async def main() -> None:
    soul = await Soul.birth(
        name="Echo",
        archetype="The Knowledge Curator",
        values=["accuracy", "organization", "learning"],
    )

    # -- Feed several interactions to trigger the observe pipeline
    interactions = [
        ("My name is Alex and I'm a data engineer at Acme Corp", "Nice to meet you, Alex!"),
        ("I prefer Python over Java for data pipelines", "Python is great for that use case."),
        (
            "We had an outage last Tuesday — the ETL job crashed",
            "That sounds stressful. What caused it?",
        ),
        (
            "The fix was to add retry logic with exponential backoff",
            "Smart — that's a common pattern for resilience.",
        ),
        (
            "I really like working with Apache Spark",
            "Spark is powerful for large-scale data processing.",
        ),
    ]

    print(f"Born: {soul.name}\n")
    print("Observing 5 interactions...")

    for user_msg, agent_msg in interactions:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg, channel="demo"))

    # -- Recall and inspect memory metadata
    print("\n--- All memories about the user ---")
    memories = await soul.recall("Alex data engineer", limit=10)
    for m in memories:
        cat = f" [{m.category.value}]" if hasattr(m, "category") and m.category else ""
        sal = f" salience={m.salience:.2f}" if hasattr(m, "salience") and m.salience else ""
        print(f"  [{m.type.value}]{cat}{sal} {m.content[:80]}")

    print("\n--- Recall: 'Python' ---")
    py_memories = await soul.recall("Python", limit=5)
    for m in py_memories:
        print(f"  [{m.type.value}] {m.content[:80]}")

    print("\n--- Recall: 'outage' ---")
    outage_memories = await soul.recall("outage crash", limit=5)
    for m in outage_memories:
        print(f"  [{m.type.value}] {m.content[:80]}")

    # -- Show state after processing
    s = soul.state
    print(f"\nFinal state: mood={s.mood.value}, energy={s.energy:.0f}%")


if __name__ == "__main__":
    asyncio.run(main())
