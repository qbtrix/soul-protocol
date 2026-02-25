# tests/test_memory/test_strategy.py — Tests for SearchStrategy protocol and pluggability.
# Created: v0.2.2 — Covers protocol compliance, TokenOverlapStrategy, custom strategies,
#   integration with recall/activation, and backwards compatibility.

from __future__ import annotations

import pytest

from soul_protocol.memory.activation import compute_activation, spreading_activation
from soul_protocol.memory.manager import MemoryManager
from soul_protocol.memory.recall import RecallEngine
from soul_protocol.memory.search import relevance_score
from soul_protocol.memory.strategy import SearchStrategy, TokenOverlapStrategy
from soul_protocol.soul import Soul
from soul_protocol.types import (
    CoreMemory,
    Interaction,
    MemoryEntry,
    MemorySettings,
    MemoryType,
)


# ---------------------------------------------------------------------------
# Custom strategy for testing
# ---------------------------------------------------------------------------


class ConstantStrategy:
    """Always returns the same score — useful for verifying the strategy is called."""

    def __init__(self, score: float = 0.99) -> None:
        self._score = score
        self.call_count = 0

    def score(self, query: str, content: str) -> float:
        self.call_count += 1
        return self._score


class InvertedStrategy:
    """Returns 1.0 - token_overlap — reverses ranking order."""

    def score(self, query: str, content: str) -> float:
        return 1.0 - relevance_score(query, content)


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestSearchStrategyProtocol:
    """Verify runtime_checkable protocol works with various implementations."""

    def test_token_overlap_satisfies_protocol(self):
        strategy = TokenOverlapStrategy()
        assert isinstance(strategy, SearchStrategy)

    def test_constant_strategy_satisfies_protocol(self):
        strategy = ConstantStrategy()
        assert isinstance(strategy, SearchStrategy)

    def test_inverted_strategy_satisfies_protocol(self):
        strategy = InvertedStrategy()
        assert isinstance(strategy, SearchStrategy)

    def test_lambda_class_satisfies_protocol(self):
        """Any class with score(str, str) -> float satisfies the protocol."""

        class MinimalSearch:
            def score(self, query: str, content: str) -> float:
                return 0.5

        assert isinstance(MinimalSearch(), SearchStrategy)

    def test_object_without_score_does_not_satisfy(self):
        """Objects missing score() do NOT satisfy the protocol."""

        class NotAStrategy:
            def rank(self, query: str, content: str) -> float:
                return 0.5

        assert not isinstance(NotAStrategy(), SearchStrategy)


# ---------------------------------------------------------------------------
# TokenOverlapStrategy correctness
# ---------------------------------------------------------------------------


class TestTokenOverlapStrategy:
    """Verify TokenOverlapStrategy produces identical results to relevance_score."""

    def test_identical_to_relevance_score(self):
        strategy = TokenOverlapStrategy()
        pairs = [
            ("python programming", "I love python programming and data science"),
            ("dark mode", "User prefers dark mode over light"),
            ("hello", "goodbye world"),
            ("machine learning AI", "deep learning and AI research"),
        ]
        for query, content in pairs:
            assert strategy.score(query, content) == relevance_score(query, content)

    def test_empty_query(self):
        strategy = TokenOverlapStrategy()
        assert strategy.score("", "some content") == 0.0

    def test_perfect_overlap(self):
        strategy = TokenOverlapStrategy()
        assert strategy.score("python programming", "python programming") == 1.0

    def test_no_overlap(self):
        strategy = TokenOverlapStrategy()
        assert strategy.score("quantum physics", "banana smoothie recipe") == 0.0


# ---------------------------------------------------------------------------
# Integration: spreading_activation uses strategy
# ---------------------------------------------------------------------------


class TestSpreadingActivationStrategy:
    """Verify spreading_activation() delegates to strategy when provided."""

    def test_no_strategy_uses_relevance_score(self):
        result = spreading_activation("python code", "I love python code")
        expected = relevance_score("python code", "I love python code")
        assert result == expected

    def test_custom_strategy_called(self):
        strategy = ConstantStrategy(0.42)
        result = spreading_activation("anything", "something", strategy=strategy)
        assert result == 0.42
        assert strategy.call_count == 1

    def test_none_strategy_same_as_default(self):
        result_none = spreading_activation("test query", "test content", strategy=None)
        result_default = spreading_activation("test query", "test content")
        assert result_none == result_default


# ---------------------------------------------------------------------------
# Integration: compute_activation uses strategy
# ---------------------------------------------------------------------------


class TestComputeActivationStrategy:
    """Verify compute_activation() passes strategy through."""

    def test_strategy_affects_activation_score(self):
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="User likes Python programming",
            importance=7,
        )
        # High constant strategy → higher activation
        high = ConstantStrategy(1.0)
        score_high = compute_activation(entry, "anything", noise=False, strategy=high)

        # Low constant strategy → lower activation
        low = ConstantStrategy(0.0)
        score_low = compute_activation(entry, "anything", noise=False, strategy=low)

        assert score_high > score_low

    def test_no_strategy_works(self):
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="User prefers dark mode",
            importance=5,
        )
        # Should not raise
        score = compute_activation(entry, "dark mode", noise=False, strategy=None)
        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# Integration: MemoryManager + RecallEngine use strategy
# ---------------------------------------------------------------------------


class TestRecallWithStrategy:
    """Verify strategy flows through MemoryManager → RecallEngine → recall."""

    @pytest.fixture
    def strategy(self):
        return ConstantStrategy(0.8)

    @pytest.fixture
    def manager_with_strategy(self, strategy):
        return MemoryManager(
            core=CoreMemory(),
            settings=MemorySettings(),
            search_strategy=strategy,
        )

    @pytest.fixture
    def manager_without_strategy(self):
        return MemoryManager(
            core=CoreMemory(),
            settings=MemorySettings(),
        )

    async def test_recall_uses_custom_strategy(self, manager_with_strategy, strategy):
        """Custom strategy is called during recall ranking."""
        await manager_with_strategy.add(
            MemoryEntry(
                type=MemoryType.SEMANTIC,
                content="User likes Python programming",
                importance=7,
            )
        )
        # Query must match content tokens so pre-filter passes candidates to ranking
        await manager_with_strategy.recall("Python programming")
        assert strategy.call_count > 0

    async def test_recall_without_strategy_works(self, manager_without_strategy):
        """No strategy = v0.2.1 behavior (no crash)."""
        await manager_without_strategy.add(
            MemoryEntry(
                type=MemoryType.SEMANTIC,
                content="User likes Python",
                importance=7,
            )
        )
        results = await manager_without_strategy.recall("Python")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Integration: Soul.birth / Soul.awaken with strategy
# ---------------------------------------------------------------------------


class TestSoulWithStrategy:
    """Verify search_strategy flows through Soul lifecycle."""

    async def test_birth_with_strategy(self):
        strategy = ConstantStrategy(0.9)
        soul = await Soul.birth("Aria", search_strategy=strategy)

        await soul.remember("User likes dark mode", type=MemoryType.SEMANTIC)
        await soul.recall("dark mode")
        assert strategy.call_count > 0

    async def test_birth_without_strategy(self):
        """No strategy = default (TokenOverlap equivalent)."""
        soul = await Soul.birth("Aria")
        await soul.remember("User likes dark mode", type=MemoryType.SEMANTIC)
        results = await soul.recall("dark mode")
        assert len(results) >= 1

    async def test_awaken_with_strategy(self, tmp_path):
        """Strategy is used after awaken from .soul file."""
        strategy = ConstantStrategy(0.9)

        # Birth, remember, export
        original = await Soul.birth("Aria")
        await original.remember("User prefers Python", type=MemoryType.SEMANTIC, importance=8)
        soul_path = tmp_path / "aria.soul"
        await original.export(str(soul_path))

        # Awaken with custom strategy
        restored = await Soul.awaken(str(soul_path), search_strategy=strategy)
        await restored.recall("Python")
        assert strategy.call_count > 0

    async def test_strategy_preserved_after_clear(self):
        """Strategy survives memory clear."""
        strategy = ConstantStrategy(0.7)
        soul = await Soul.birth("Aria", search_strategy=strategy)

        await soul.remember("fact about Python", type=MemoryType.SEMANTIC)
        await soul._memory.clear()
        await soul.remember("fact about Python again", type=MemoryType.SEMANTIC)
        await soul.recall("Python")
        assert strategy.call_count > 0
