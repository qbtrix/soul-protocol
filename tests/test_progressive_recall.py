# tests/test_progressive_recall.py — Tests for progressive disclosure in recall
# Created: 2026-03-29 — Verifies progressive=True returns primary + overflow entries

import pytest

from soul_protocol.runtime.memory.episodic import EpisodicStore
from soul_protocol.runtime.memory.procedural import ProceduralStore
from soul_protocol.runtime.memory.recall import RecallEngine
from soul_protocol.runtime.memory.semantic import SemanticStore
from soul_protocol.runtime.types import MemoryEntry, MemoryType


def _make_entry(content: str, importance: int = 5, abstract: str | None = None) -> MemoryEntry:
    entry = MemoryEntry(
        type=MemoryType.SEMANTIC,
        content=content,
        importance=importance,
    )
    if abstract:
        entry.abstract = abstract
    return entry


@pytest.fixture
def recall_engine():
    episodic = EpisodicStore()
    semantic = SemanticStore()
    procedural = ProceduralStore()
    return RecallEngine(
        episodic=episodic,
        semantic=semantic,
        procedural=procedural,
    )


@pytest.fixture
async def populated_engine(recall_engine):
    """Engine with 5 semantic entries of varying importance."""
    for i in range(5):
        entry = _make_entry(
            content=f"Topic alpha fact number {i}",
            importance=8 - i,
            abstract=f"Alpha fact {i}" if i < 4 else None,  # Last entry has no abstract
        )
        await recall_engine._semantic.add(entry)
    return recall_engine


@pytest.mark.asyncio
async def test_progressive_false_returns_limit(populated_engine):
    """Default progressive=False returns exactly limit entries."""
    results = await populated_engine.recall("alpha", limit=3, progressive=False)
    assert len(results) <= 3


@pytest.mark.asyncio
async def test_progressive_true_returns_more_than_limit(populated_engine):
    """progressive=True returns primary + overflow (up to limit*2)."""
    results = await populated_engine.recall("alpha", limit=2, progressive=True)
    assert len(results) > 2
    assert len(results) <= 4


@pytest.mark.asyncio
async def test_overflow_uses_abstract(populated_engine):
    """Overflow entries should have content replaced with abstract."""
    results = await populated_engine.recall("alpha", limit=2, progressive=True)
    overflow = results[2:]
    summarized = [r for r in overflow if r.is_summarized]
    assert len(summarized) > 0
    for entry in summarized:
        assert entry.content == entry.abstract


@pytest.mark.asyncio
async def test_overflow_no_abstract_keeps_content(populated_engine):
    """Overflow entries without abstract keep original content."""
    results = await populated_engine.recall("alpha", limit=1, progressive=True)
    # Find entries that are NOT summarized in overflow
    overflow = results[1:]
    for entry in overflow:
        if not entry.is_summarized:
            assert entry.abstract is None or entry.abstract == ""


@pytest.mark.asyncio
async def test_is_summarized_marker(populated_engine):
    """Primary entries should NOT be marked as summarized."""
    results = await populated_engine.recall("alpha", limit=2, progressive=True)
    primary = results[:2]
    for entry in primary:
        assert entry.is_summarized is False
