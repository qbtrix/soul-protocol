# test_graph/test_progressive_loading.py — Pagination + token budget tests.
# Created: 2026-04-29 (#108) — Verifies that:
#   1. Recall with graph_walk paginates when more than ``limit`` results
#      are reachable, exposing ``next_page_token``.
#   2. ``page_token`` round-trips: passing the previous token resumes from
#      the right offset.
#   3. ``token_budget`` switches overflow entries to their L0 abstract.
#   4. Mismatched (query, walk) on a token raises ValueError.

from __future__ import annotations

import pytest

from soul_protocol import MemoryEntry, MemoryType, RecallResults, Soul


async def _seed_soul(num_entities: int = 30) -> Soul:
    """Soul with N entities all reachable from 'Hub' plus N memories that
    mention each entity. Used to drive the pagination + budget tests."""
    soul = await Soul.birth(name="ProgTest", archetype="The Companion")
    g = soul._memory._graph
    g.add_entity("Hub", "concept")
    sem = soul._memory._semantic
    for i in range(num_entities):
        name = f"Node{i}"
        g.add_entity(name, "concept")
        g.add_relationship("Hub", name, "mentions")
        await sem.add(
            MemoryEntry(
                id=f"m{i}",
                type=MemoryType.SEMANTIC,
                content=f"This memory mentions {name} in some longer text. " * 4,
                entities=[name],
                # Add an L0 abstract so the budget overflow path can swap it
                abstract=f"{name} abstract.",
            )
        )
    return soul


# ============ Pagination ============


class TestPagination:
    @pytest.mark.asyncio
    async def test_first_page_has_token_when_more_available(self) -> None:
        soul = await _seed_soul(num_entities=20)
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Hub", "depth": 1},
            limit=5,
        )
        assert isinstance(results, RecallResults)
        assert len(results) == 5
        assert results.next_page_token is not None
        # Total estimate covers all reachable memories
        assert results.total_estimate is not None
        assert results.total_estimate >= 20

    @pytest.mark.asyncio
    async def test_no_token_when_under_limit(self) -> None:
        soul = await _seed_soul(num_entities=3)
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Hub", "depth": 1},
            limit=10,
        )
        assert results.next_page_token is None

    @pytest.mark.asyncio
    async def test_page_token_resumes_from_offset(self) -> None:
        soul = await _seed_soul(num_entities=20)
        first = await soul.recall(
            "anything",
            graph_walk={"start": "Hub", "depth": 1},
            limit=5,
        )
        first_ids = {r.id for r in first}

        second = await soul.recall(
            "anything",
            graph_walk={"start": "Hub", "depth": 1},
            limit=5,
            page_token=first.next_page_token,
        )
        second_ids = {r.id for r in second}
        # No overlap between pages
        assert first_ids.isdisjoint(second_ids)

    @pytest.mark.asyncio
    async def test_token_returns_remaining_pages(self) -> None:
        soul = await _seed_soul(num_entities=12)
        all_ids: set[str] = set()
        token: str | None = None
        for _ in range(5):
            page = await soul.recall(
                "anything",
                graph_walk={"start": "Hub", "depth": 1},
                limit=5,
                page_token=token,
            )
            for r in page:
                all_ids.add(r.id)
            token = page.next_page_token
            if token is None:
                break
        # All 12 reachable memories collected
        assert len(all_ids) == 12

    @pytest.mark.asyncio
    async def test_mismatched_token_raises(self) -> None:
        soul = await _seed_soul(num_entities=12)
        first = await soul.recall(
            "anything",
            graph_walk={"start": "Hub", "depth": 1},
            limit=5,
        )
        token = first.next_page_token
        # Try to use the token with a different walk — should raise
        with pytest.raises(ValueError):
            await soul.recall(
                "anything",
                graph_walk={"start": "Hub", "depth": 2},  # different depth
                limit=5,
                page_token=token,
            )

    @pytest.mark.asyncio
    async def test_malformed_token_raises(self) -> None:
        soul = await _seed_soul(num_entities=3)
        with pytest.raises(ValueError):
            await soul.recall(
                "anything",
                graph_walk={"start": "Hub", "depth": 1},
                limit=5,
                page_token="not-a-real-token",
            )


# ============ Token budget ============


class TestTokenBudget:
    @pytest.mark.asyncio
    async def test_budget_swaps_overflow_to_abstract(self) -> None:
        soul = await _seed_soul(num_entities=10)
        # Each memory content is ~100+ chars; budget of 50 tokens (~200 chars)
        # should fit ~1 full entry, the rest become abstracts.
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Hub", "depth": 1},
            limit=10,
            token_budget=50,
        )
        assert isinstance(results, RecallResults)
        assert results.truncated_for_budget is True
        # At least one entry was truncated to its abstract
        truncated = [r for r in results if r.is_summarized]
        assert len(truncated) > 0

    @pytest.mark.asyncio
    async def test_budget_zero_means_unlimited(self) -> None:
        soul = await _seed_soul(num_entities=5)
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Hub", "depth": 1},
            limit=10,
            token_budget=0,
        )
        # Budget=0 short-circuits — no truncation
        assert results.truncated_for_budget is False

    @pytest.mark.asyncio
    async def test_budget_without_graph_walk(self) -> None:
        # token_budget can be applied even without a graph walk
        soul = await _seed_soul(num_entities=5)
        results = await soul.recall(
            "Node0",  # query that matches at least one memory
            limit=10,
            token_budget=20,
        )
        assert isinstance(results, RecallResults)


# ============ Combined budget + pagination ============


class TestBudgetAndPagination:
    @pytest.mark.asyncio
    async def test_budget_applies_per_page(self) -> None:
        soul = await _seed_soul(num_entities=20)
        # Walk through pages with a tiny budget — every page should overflow
        results = await soul.recall(
            "anything",
            graph_walk={"start": "Hub", "depth": 1},
            limit=5,
            token_budget=20,
        )
        assert results.truncated_for_budget is True
        token = results.next_page_token
        assert token is not None

        next_page = await soul.recall(
            "anything",
            graph_walk={"start": "Hub", "depth": 1},
            limit=5,
            page_token=token,
            token_budget=20,
        )
        assert next_page.truncated_for_budget is True
