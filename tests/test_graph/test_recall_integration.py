# test_graph/test_recall_integration.py — recall(graph_walk=...) tests.
# Created: 2026-04-29 (#108) — Verifies that the graph_walk parameter on
# Soul.recall correctly filters memories to those linked to entities reachable
# from a starting node, that ``depth`` and ``edge_types`` filters are honored,
# and that the ranking surfaces close-distance entities first.

from __future__ import annotations

import pytest

from soul_protocol import MemoryEntry, MemoryType, Soul


async def _make_soul_with_graph() -> Soul:
    """Birth a soul, then directly populate the graph + memory stores so we
    can exercise graph_walk without depending on the LLM extractor."""
    soul = await Soul.birth(name="GraphTest", archetype="The Companion")

    g = soul._memory._graph
    g.add_entity("Alice", "person")
    g.add_entity("Bob", "person")
    g.add_entity("Acme", "org")
    g.add_entity("Python", "tool")
    g.add_entity("Lonely", "concept")  # not connected to anything
    g.add_relationship("Alice", "Bob", "mentions")
    g.add_relationship("Alice", "Acme", "owned_by")
    g.add_relationship("Acme", "Python", "depends_on")

    # Seed semantic memories that mention specific entities
    sem = soul._memory._semantic
    await sem.add(
        MemoryEntry(
            id="m-alice",
            type=MemoryType.SEMANTIC,
            content="Alice is the founder",
            entities=["Alice"],
        )
    )
    await sem.add(
        MemoryEntry(
            id="m-bob",
            type=MemoryType.SEMANTIC,
            content="Bob writes Python code",
            entities=["Bob", "Python"],
        )
    )
    await sem.add(
        MemoryEntry(
            id="m-acme",
            type=MemoryType.SEMANTIC,
            content="Acme uses Python in production",
            entities=["Acme", "Python"],
        )
    )
    await sem.add(
        MemoryEntry(
            id="m-python",
            type=MemoryType.SEMANTIC,
            content="Python is a programming language",
            entities=["Python"],
        )
    )
    await sem.add(
        MemoryEntry(
            id="m-lonely",
            type=MemoryType.SEMANTIC,
            content="Lonely concept that nobody references",
            entities=["Lonely"],
        )
    )
    return soul


# ============ graph_walk filter ============


class TestGraphWalkFilter:
    @pytest.mark.asyncio
    async def test_walk_returns_only_reachable_memories(self) -> None:
        soul = await _make_soul_with_graph()
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Alice", "depth": 2},
            limit=20,
        )
        ids = {r.id for r in results}
        # Reachable: Alice (start), Bob (1 hop), Acme (1 hop), Python (2 hops)
        # Unreachable: Lonely
        assert "m-alice" in ids
        assert "m-bob" in ids
        assert "m-acme" in ids
        assert "m-python" in ids
        assert "m-lonely" not in ids

    @pytest.mark.asyncio
    async def test_depth_limits_walk(self) -> None:
        soul = await _make_soul_with_graph()
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Alice", "depth": 1},
            limit=20,
        )
        ids = {r.id for r in results}
        # Only Alice + 1-hop neighbors (Bob, Acme), not Python (2 hops)
        assert "m-alice" in ids
        assert "m-bob" in ids
        assert "m-acme" in ids
        assert "m-python" not in ids

    @pytest.mark.asyncio
    async def test_unknown_start_returns_empty(self) -> None:
        soul = await _make_soul_with_graph()
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Ghost", "depth": 2},
            limit=20,
        )
        assert list(results) == []

    @pytest.mark.asyncio
    async def test_edge_type_filter(self) -> None:
        """``edge_types`` should restrict which relations the walk follows."""
        soul = await _make_soul_with_graph()
        # Only follow 'mentions' edges — that means we visit Alice and Bob,
        # but not Acme (which connects via 'owned_by').
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Alice", "depth": 2, "edge_types": ["mentions"]},
            limit=20,
        )
        ids = {r.id for r in results}
        assert "m-alice" in ids
        assert "m-bob" in ids
        assert "m-acme" not in ids
        assert "m-python" not in ids

    @pytest.mark.asyncio
    async def test_returns_recall_results(self) -> None:
        from soul_protocol import RecallResults

        soul = await _make_soul_with_graph()
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Alice", "depth": 1},
            limit=20,
        )
        assert isinstance(results, RecallResults)
        # No truncation expected
        assert results.next_page_token is None


# ============ Ranking by graph distance ============


class TestRankingByGraphDistance:
    @pytest.mark.asyncio
    async def test_closer_entities_rank_first(self) -> None:
        soul = await _make_soul_with_graph()
        results = await soul.recall(
            "production",  # the 'Acme uses Python' content has 'production'
            graph_walk={"start": "Alice", "depth": 3},
            limit=20,
        )
        # Alice's own memory is at distance 0; should beat Bob's (1 hop)
        # and Python's (2 hops)
        first_id = results[0].id
        assert first_id == "m-alice"


# ============ Without graph_walk — back-compat ============


class TestBackCompat:
    @pytest.mark.asyncio
    async def test_recall_without_graph_walk_returns_plain_list(self) -> None:
        soul = await _make_soul_with_graph()
        results = await soul.recall("python", limit=5)
        # Plain list — no RecallResults wrapping
        from soul_protocol import RecallResults

        assert not isinstance(results, RecallResults)
        assert isinstance(results, list)
