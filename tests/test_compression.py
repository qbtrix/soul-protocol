# test_compression.py — Tests for the memory compression pipeline.
# Created: 2026-03-06 — Covers summarization, deduplication, importance-based
#   pruning, and export splitting.

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from soul_protocol.memory.compression import MemoryCompressor
from soul_protocol.types import MemoryEntry, MemoryType


@pytest.fixture
def compressor() -> MemoryCompressor:
    return MemoryCompressor()


def _mem(
    content: str,
    importance: int = 5,
    type: MemoryType = MemoryType.SEMANTIC,
    age_days: int = 0,
) -> MemoryEntry:
    """Helper to create test memory entries."""
    return MemoryEntry(
        type=type,
        content=content,
        importance=importance,
        created_at=datetime.now() - timedelta(days=age_days),
    )


class TestSummarize:
    def test_empty_input(self, compressor: MemoryCompressor):
        assert compressor.summarize_memories([]) == ""

    def test_single_memory(self, compressor: MemoryCompressor):
        result = compressor.summarize_memories([_mem("User likes Python")])
        assert "User likes Python" in result

    def test_deduplicates_in_summary(self, compressor: MemoryCompressor):
        # These share 5/6 tokens = 0.83 overlap, above the 0.7 threshold
        memories = [
            _mem("User likes Python for web development work", importance=8),
            _mem("User likes Python for web application work", importance=5),
        ]
        result = compressor.summarize_memories(memories)
        # The near-duplicate should be removed; only the higher-importance one kept
        assert "web development" in result
        assert "application" not in result

    def test_respects_max_tokens(self, compressor: MemoryCompressor):
        memories = [_mem(f"Fact number {i} about the user") for i in range(100)]
        result = compressor.summarize_memories(memories, max_tokens=20)
        # Should be truncated — far fewer words than 100 entries
        word_count = len(result.split())
        assert word_count <= 25  # small buffer for headers

    def test_groups_by_type(self, compressor: MemoryCompressor):
        memories = [
            _mem("User prefers dark mode", type=MemoryType.SEMANTIC),
            _mem("User asked about Python", type=MemoryType.EPISODIC),
        ]
        result = compressor.summarize_memories(memories, max_tokens=200)
        assert "[semantic]" in result
        assert "[episodic]" in result

    def test_higher_importance_first(self, compressor: MemoryCompressor):
        memories = [
            _mem("Low priority fact", importance=2),
            _mem("Critical fact about identity", importance=9),
        ]
        result = compressor.summarize_memories(memories, max_tokens=50)
        # Critical fact should appear (it's sorted first)
        assert "Critical fact" in result


class TestDeduplicate:
    def test_empty_input(self, compressor: MemoryCompressor):
        assert compressor.deduplicate([]) == []

    def test_no_duplicates(self, compressor: MemoryCompressor):
        memories = [
            _mem("User likes Python"),
            _mem("User works at Acme"),
        ]
        result = compressor.deduplicate(memories)
        assert len(result) == 2

    def test_removes_near_duplicates(self, compressor: MemoryCompressor):
        memories = [
            _mem("User likes Python programming", importance=8),
            _mem("User likes Python programming language", importance=5),
        ]
        result = compressor.deduplicate(memories, similarity_threshold=0.6)
        assert len(result) == 1
        # Higher importance one is kept
        assert result[0].importance == 8

    def test_keeps_distinct_memories(self, compressor: MemoryCompressor):
        memories = [
            _mem("User likes Python"),
            _mem("User works at Google"),
            _mem("User lives in Tokyo"),
        ]
        result = compressor.deduplicate(memories)
        assert len(result) == 3

    def test_custom_threshold(self, compressor: MemoryCompressor):
        memories = [
            _mem("The quick brown fox"),
            _mem("The quick brown dog"),
        ]
        # High threshold: these are different enough to keep both
        result = compressor.deduplicate(memories, similarity_threshold=0.9)
        assert len(result) == 2

        # Low threshold: these overlap enough to merge
        result = compressor.deduplicate(memories, similarity_threshold=0.5)
        assert len(result) == 1


class TestPruneByImportance:
    def test_keeps_high_importance(self, compressor: MemoryCompressor):
        memories = [
            _mem("Important fact", importance=8),
            _mem("Low fact", importance=2),
        ]
        keep, pruned = compressor.prune_by_importance(memories, min_importance=3)
        assert len(keep) == 1
        assert keep[0].content == "Important fact"
        assert len(pruned) == 1

    def test_prunes_old_medium_importance(self, compressor: MemoryCompressor):
        memories = [
            _mem("Old medium fact", importance=5, age_days=400),
            _mem("Recent medium fact", importance=5, age_days=10),
        ]
        keep, pruned = compressor.prune_by_importance(
            memories, min_importance=3, max_age_days=365
        )
        assert len(keep) == 1
        assert keep[0].content == "Recent medium fact"

    def test_keeps_old_high_importance(self, compressor: MemoryCompressor):
        """Old memories with importance >= 7 are always kept."""
        memories = [
            _mem("User's name is Prakash", importance=9, age_days=500),
        ]
        keep, pruned = compressor.prune_by_importance(
            memories, min_importance=3, max_age_days=365
        )
        assert len(keep) == 1
        assert len(pruned) == 0

    def test_empty_input(self, compressor: MemoryCompressor):
        keep, pruned = compressor.prune_by_importance([])
        assert keep == []
        assert pruned == []


class TestCompressForExport:
    def test_all_inline_when_under_limit(self, compressor: MemoryCompressor):
        memories = [_mem(f"Fact {i}") for i in range(5)]
        inline, external = compressor.compress_for_export(memories, max_inline=10)
        assert len(inline) == 5
        assert len(external) == 0

    def test_splits_at_limit(self, compressor: MemoryCompressor):
        memories = [_mem(f"Fact {i}", importance=i + 1) for i in range(10)]
        inline, external = compressor.compress_for_export(memories, max_inline=3)
        assert len(inline) == 3
        assert len(external) == 7
        # Inline should have the highest importance
        assert all(m.importance >= 8 for m in inline)

    def test_empty_input(self, compressor: MemoryCompressor):
        inline, external = compressor.compress_for_export([])
        assert inline == []
        assert external == []
