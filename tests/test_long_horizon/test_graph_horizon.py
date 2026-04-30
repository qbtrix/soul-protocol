# test_long_horizon/test_graph_horizon.py — 200-interaction graph horizon test.
# Created: 2026-04-29 (#108, #190) — Drives a soul through 200 interactions
# with mixed entity references and verifies:
#   1. The graph grows monotonically (no spurious entity loss).
#   2. Traversal queries are deterministic across multiple recall calls.
#   3. Trust chain entries reflect every entity addition.
#   4. The token-budget overflow path keeps working at scale.

from __future__ import annotations

import pytest

from soul_protocol import Interaction, RecallResults, Soul

# A small entity vocabulary. Each interaction picks one user-side entity
# and references one or two related entities — the soul's heuristic
# extractor should pick at least the user-side ones up via KNOWN_TECH.
_ENTITIES = [
    "Python",
    "Rust",
    "Go",
    "Docker",
    "Kubernetes",
    "Postgres",
    "Redis",
    "Anthropic",
    "OpenAI",
    "Claude",
]


def _interaction(turn: int) -> Interaction:
    primary = _ENTITIES[turn % len(_ENTITIES)]
    secondary = _ENTITIES[(turn + 3) % len(_ENTITIES)]
    user_input = f"Today I worked with {primary} and explored {secondary} integrations"
    agent_output = f"Got it — sounds like {primary} is the main focus."
    return Interaction(user_input=user_input, agent_output=agent_output)


@pytest.mark.asyncio
async def test_long_horizon_graph_grows_monotonically() -> None:
    soul = await Soul.birth(name="HorizonGraph", archetype="The Companion")
    # Disable significance-based skipping so every observe runs the
    # extraction pipeline. Without this the graph plateaus quickly.
    soul._memory._settings.skip_deep_processing_on_low_significance = False

    sizes: list[int] = []
    for turn in range(200):
        await soul.observe(_interaction(turn))
        if turn % 25 == 0 or turn == 199:
            sizes.append(len(soul._memory._graph._entities))

    # Every checkpoint should be >= the previous one (no shrinkage).
    for prev, cur in zip(sizes, sizes[1:], strict=False):
        assert cur >= prev, f"Graph shrunk: {prev} -> {cur}"
    # Final graph should contain at least most of the vocabulary
    final_entities = set(soul._memory._graph._entities.keys())
    seen = sum(1 for ent in _ENTITIES if ent in final_entities)
    assert seen >= len(_ENTITIES) // 2, (
        f"Only {seen}/{len(_ENTITIES)} known entities reached the graph"
    )


@pytest.mark.asyncio
async def test_long_horizon_traversal_is_consistent() -> None:
    """Repeated traversals from the same node yield the same neighborhood."""
    soul = await Soul.birth(name="HorizonGraph", archetype="The Companion")
    soul._memory._settings.skip_deep_processing_on_low_significance = False
    for turn in range(120):
        await soul.observe(_interaction(turn))

    # Pick an entity that should be in the graph
    g = soul._memory._graph
    candidates = [name for name in _ENTITIES if name in g._entities]
    if not candidates:
        pytest.skip("No known entities reached the graph")
    start = candidates[0]

    first = soul.graph.neighbors(start, depth=1)
    second = soul.graph.neighbors(start, depth=1)
    third = soul.graph.neighbors(start, depth=1)
    assert {n.id for n in first} == {n.id for n in second} == {n.id for n in third}


@pytest.mark.asyncio
async def test_long_horizon_chain_records_each_new_entity() -> None:
    """Trust chain has at least one ``graph.entity_added`` per unique entity."""
    soul = await Soul.birth(name="HorizonGraph", archetype="The Companion")
    soul._memory._settings.skip_deep_processing_on_low_significance = False
    for turn in range(60):
        await soul.observe(_interaction(turn))

    chain_entries = [
        entry for entry in soul.trust_chain.entries if entry.action == "graph.entity_added"
    ]
    final_entities = soul._memory._graph._entities
    # The chain should record at least as many entity_added events as
    # there are entities in the final graph (one per net-new entity).
    assert len(chain_entries) >= len(final_entities)


@pytest.mark.asyncio
async def test_long_horizon_recall_with_token_budget() -> None:
    soul = await Soul.birth(name="HorizonGraph", archetype="The Companion")
    soul._memory._settings.skip_deep_processing_on_low_significance = False
    for turn in range(60):
        await soul.observe(_interaction(turn))

    # Grab any entity that exists in the graph as the walk anchor
    g = soul._memory._graph
    candidates = [name for name in _ENTITIES if name in g._entities]
    if not candidates:
        pytest.skip("No known entities reached the graph")
    start = candidates[0]

    results = await soul.recall(
        "anything",
        graph_walk={"start": start, "depth": 2},
        limit=5,
        token_budget=200,
    )
    assert isinstance(results, RecallResults)
    assert len(results) <= 5
