# test_compaction.py — Tests for runtime/context/compaction.py three-level escalation.
# Created: v0.3.0 — Zero-cost path, Level 1 SUMMARY, Level 2 BULLETS, Level 3 TRUNCATED,
# guaranteed convergence, edge cases, and CognitiveEngine integration.

from __future__ import annotations

import pytest

from soul_protocol.runtime.context.compaction import ThreeLevelCompactor, _estimate_tokens
from soul_protocol.runtime.context.store import SQLiteContextStore
from soul_protocol.spec.context.models import (
    CompactionLevel,
    ContextMessage,
    ContextNode,
)


class MockCognitiveEngine:
    """Mock CognitiveEngine that returns predictable summaries."""

    def __init__(self, summary_text: str = "Summary.", bullets_text: str = "- Point 1"):
        self.summary_text = summary_text
        self.bullets_text = bullets_text
        self.calls: list[str] = []

    async def think(self, prompt: str) -> str:
        self.calls.append(prompt)
        if "[TASK:context_summary]" in prompt:
            return self.summary_text
        if "[TASK:context_bullets]" in prompt:
            return self.bullets_text
        return "Unknown task"


class FailingCognitiveEngine:
    """CognitiveEngine that always raises."""

    async def think(self, prompt: str) -> str:
        raise RuntimeError("LLM unavailable")


@pytest.fixture
async def store():
    s = SQLiteContextStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def mock_engine():
    return MockCognitiveEngine()


async def _fill_store(store: SQLiteContextStore, count: int, token_count: int = 100):
    """Add count messages with given token_count each."""
    for i in range(count):
        await store.append_message(
            ContextMessage(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message number {i} with some content to fill tokens",
                token_count=token_count,
            )
        )


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    def test_basic_estimate(self):
        assert _estimate_tokens("hello world") >= 1

    def test_empty_string(self):
        assert _estimate_tokens("") == 1  # Minimum 1

    def test_longer_text(self):
        text = "a" * 400
        assert _estimate_tokens(text) == 100


# ---------------------------------------------------------------------------
# Zero-cost path
# ---------------------------------------------------------------------------


class TestZeroCostPath:
    async def test_no_compaction_when_under_budget(self, store, mock_engine):
        await _fill_store(store, 5, token_count=10)
        compactor = ThreeLevelCompactor(store, mock_engine)
        saved = await compactor.compact(token_budget=1000)
        assert saved == 0
        assert len(mock_engine.calls) == 0

    async def test_empty_store_no_compaction(self, store, mock_engine):
        compactor = ThreeLevelCompactor(store, mock_engine)
        saved = await compactor.compact(token_budget=100)
        assert saved == 0


# ---------------------------------------------------------------------------
# Level 1: SUMMARY
# ---------------------------------------------------------------------------


class TestLevel1Summary:
    async def test_summarizes_oldest_batch(self, store, mock_engine):
        await _fill_store(store, 20, token_count=100)
        compactor = ThreeLevelCompactor(store, mock_engine, summary_batch_size=10)
        saved = await compactor.compact(token_budget=500)
        assert saved > 0
        assert any("[TASK:context_summary]" in c for c in mock_engine.calls)

    async def test_creates_summary_node(self, store, mock_engine):
        await _fill_store(store, 20, token_count=100)
        compactor = ThreeLevelCompactor(store, mock_engine, summary_batch_size=10)
        await compactor.compact(token_budget=500)
        nodes = await store.get_nodes_by_level(CompactionLevel.SUMMARY)
        assert len(nodes) >= 1
        assert nodes[0].content == "Summary."

    async def test_summary_node_has_children(self, store, mock_engine):
        await _fill_store(store, 20, token_count=100)
        compactor = ThreeLevelCompactor(store, mock_engine, summary_batch_size=10)
        await compactor.compact(token_budget=500)
        nodes = await store.get_nodes_by_level(CompactionLevel.SUMMARY)
        assert len(nodes[0].children_ids) == 10

    async def test_skips_when_too_few_messages(self, store, mock_engine):
        await _fill_store(store, 5, token_count=100)
        compactor = ThreeLevelCompactor(store, mock_engine, summary_batch_size=10)
        # Budget is tight but not enough messages for a batch
        saved = await compactor._compact_level1(token_budget=100)
        assert saved == 0

    async def test_summary_node_seq_range(self, store, mock_engine):
        await _fill_store(store, 20, token_count=100)
        compactor = ThreeLevelCompactor(store, mock_engine, summary_batch_size=10)
        await compactor.compact(token_budget=500)
        nodes = await store.get_nodes_by_level(CompactionLevel.SUMMARY)
        assert nodes[0].seq_start == 1
        assert nodes[0].seq_end == 10


# ---------------------------------------------------------------------------
# Level 2: BULLETS
# ---------------------------------------------------------------------------


class TestLevel2Bullets:
    async def test_compresses_summaries_to_bullets(self, store):
        engine = MockCognitiveEngine(
            summary_text="A long summary that takes many tokens " * 10,
            bullets_text="- Point 1",
        )
        await _fill_store(store, 20, token_count=100)
        compactor = ThreeLevelCompactor(store, engine, summary_batch_size=10)

        # First, create a summary node manually
        await store.insert_node(
            ContextNode(
                id="sum1",
                level=CompactionLevel.SUMMARY,
                content="A long summary " * 50,
                token_count=500,
                seq_start=1,
                seq_end=10,
            )
        )

        saved = await compactor._compact_level2(token_budget=100)
        assert saved > 0
        bullets = await store.get_nodes_by_level(CompactionLevel.BULLETS)
        assert len(bullets) >= 1

    async def test_bullets_node_links_to_summary(self, store):
        engine = MockCognitiveEngine(bullets_text="- Compact point")
        await store.insert_node(
            ContextNode(
                id="sum1",
                level=CompactionLevel.SUMMARY,
                content="Long summary text " * 20,
                token_count=200,
                seq_start=1,
                seq_end=10,
            )
        )
        compactor = ThreeLevelCompactor(store, engine)
        await compactor._compact_level2(token_budget=50)
        bullets = await store.get_nodes_by_level(CompactionLevel.BULLETS)
        if bullets:
            assert "sum1" in bullets[0].children_ids


# ---------------------------------------------------------------------------
# Level 3: TRUNCATED
# ---------------------------------------------------------------------------


class TestLevel3Truncated:
    async def test_truncates_without_engine(self, store):
        await _fill_store(store, 20, token_count=100)
        compactor = ThreeLevelCompactor(store, engine=None)
        saved = await compactor.compact(token_budget=500)
        assert saved > 0

    async def test_creates_truncated_node(self, store):
        await _fill_store(store, 20, token_count=100)
        compactor = ThreeLevelCompactor(store, engine=None)
        await compactor.compact(token_budget=500)
        nodes = await store.get_nodes_by_level(CompactionLevel.TRUNCATED)
        assert len(nodes) >= 1

    async def test_truncated_has_descriptive_content(self, store):
        await _fill_store(store, 20, token_count=100)
        compactor = ThreeLevelCompactor(store, engine=None)
        await compactor.compact(token_budget=500)
        nodes = await store.get_nodes_by_level(CompactionLevel.TRUNCATED)
        assert "truncated" in nodes[0].content.lower()

    async def test_guaranteed_convergence(self, store):
        """Level 3 must always bring tokens under budget."""
        await _fill_store(store, 100, token_count=100)
        compactor = ThreeLevelCompactor(store, engine=None)
        budget = 500
        await compactor.compact(token_budget=budget)
        current = await compactor._current_context_tokens()
        assert current <= budget

    async def test_convergence_tiny_budget(self, store):
        """Even with a very small budget, Level 3 converges."""
        await _fill_store(store, 50, token_count=100)
        compactor = ThreeLevelCompactor(store, engine=None)
        budget = 50
        await compactor.compact(token_budget=budget)
        current = await compactor._current_context_tokens()
        assert current <= budget

    async def test_falling_back_from_failing_engine(self, store):
        """When engine fails, should fall through to Level 3."""
        await _fill_store(store, 20, token_count=100)
        engine = FailingCognitiveEngine()
        compactor = ThreeLevelCompactor(store, engine, summary_batch_size=10)
        saved = await compactor.compact(token_budget=500)
        assert saved > 0


# ---------------------------------------------------------------------------
# Compaction helpers
# ---------------------------------------------------------------------------


class TestCompactionHelpers:
    async def test_is_seq_covered(self):
        ranges = [(1, 5), (10, 15)]
        assert ThreeLevelCompactor._is_seq_covered(3, ranges) is True
        assert ThreeLevelCompactor._is_seq_covered(7, ranges) is False
        assert ThreeLevelCompactor._is_seq_covered(10, ranges) is True
        assert ThreeLevelCompactor._is_seq_covered(15, ranges) is True
        assert ThreeLevelCompactor._is_seq_covered(16, ranges) is False

    async def test_current_context_tokens_empty(self, store):
        compactor = ThreeLevelCompactor(store, engine=None)
        assert await compactor._current_context_tokens() == 0

    async def test_current_context_tokens_messages_only(self, store):
        await _fill_store(store, 5, token_count=100)
        compactor = ThreeLevelCompactor(store, engine=None)
        assert await compactor._current_context_tokens() == 500

    async def test_current_context_tokens_with_compacted_nodes(self, store):
        await _fill_store(store, 10, token_count=100)
        # Compact first 5 messages into a summary node
        await store.insert_node(
            ContextNode(
                id="s1",
                level=CompactionLevel.SUMMARY,
                content="Summary",
                token_count=50,
                seq_start=1,
                seq_end=5,
            )
        )
        compactor = ThreeLevelCompactor(store, engine=None)
        tokens = await compactor._current_context_tokens()
        # 5 uncovered messages (100 each) + 1 summary node (50) = 550
        assert tokens == 550


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestCompactionEdgeCases:
    async def test_single_message_no_compaction(self, store, mock_engine):
        await store.append_message(ContextMessage(role="user", content="solo", token_count=10))
        compactor = ThreeLevelCompactor(store, mock_engine)
        saved = await compactor.compact(token_budget=100)
        assert saved == 0

    async def test_exact_budget_no_compaction(self, store, mock_engine):
        await _fill_store(store, 10, token_count=10)
        compactor = ThreeLevelCompactor(store, mock_engine)
        saved = await compactor.compact(token_budget=100)  # Exactly fits
        assert saved == 0

    async def test_multiple_compaction_rounds(self, store, mock_engine):
        """Compacting twice doesn't double-compact already-compacted content."""
        await _fill_store(store, 30, token_count=100)
        compactor = ThreeLevelCompactor(store, mock_engine, summary_batch_size=10)
        saved1 = await compactor.compact(token_budget=1000)
        saved2 = await compactor.compact(token_budget=1000)
        # Second round should save less or nothing
        assert saved2 <= saved1
