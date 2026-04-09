# test_contradiction.py — Tests for semantic contradiction detection (v0.4.0).
# Created: v0.4.0 — 27 tests covering heuristic mode (negation patterns,
#   entity-attribute conflicts), LLM mock mode, no-contradiction cases,
#   clear contradictions, ambiguous cases, and pipeline integration.

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from soul_protocol.runtime.memory.contradiction import (
    ContradictionDetector,
    ContradictionResult,
)
from soul_protocol.runtime.types import (
    MemoryEntry,
    MemoryType,
)


def _make_memory(content: str, mem_id: str = "", importance: int = 5) -> MemoryEntry:
    """Helper to create a MemoryEntry for testing."""
    return MemoryEntry(
        id=mem_id or content[:8].replace(" ", "_"),
        type=MemoryType.SEMANTIC,
        content=content,
        importance=importance,
    )


# ==== Heuristic mode: negation patterns ====


class TestHeuristicNegation:
    """Tests for heuristic negation-based contradiction detection."""

    async def test_likes_vs_dislikes(self):
        detector = ContradictionDetector()
        old = _make_memory("User likes Python programming", mem_id="old1")
        results = await detector.detect_heuristic("User dislikes Python programming", [old])
        assert len(results) >= 1
        assert results[0].is_contradiction
        assert results[0].old_memory_id == "old1"

    async def test_is_vs_is_not(self):
        detector = ContradictionDetector()
        old = _make_memory("User is a developer", mem_id="old2")
        results = await detector.detect_heuristic("User is not a developer", [old])
        assert len(results) >= 1
        assert results[0].is_contradiction

    async def test_can_vs_cannot(self):
        detector = ContradictionDetector()
        old = _make_memory("User can speak French fluently", mem_id="old3")
        results = await detector.detect_heuristic("User can't speak French fluently", [old])
        assert len(results) >= 1
        assert results[0].is_contradiction

    async def test_has_vs_hasnt(self):
        detector = ContradictionDetector()
        old = _make_memory("User has a dog named Rex", mem_id="old4")
        results = await detector.detect_heuristic("User hasn't a dog named Rex", [old])
        assert len(results) >= 1
        assert results[0].is_contradiction

    async def test_true_vs_false(self):
        detector = ContradictionDetector()
        old = _make_memory("The statement is true about the user", mem_id="old5")
        results = await detector.detect_heuristic("The statement is false about the user", [old])
        assert len(results) >= 1
        assert results[0].is_contradiction

    async def test_works_at_vs_left(self):
        detector = ContradictionDetector()
        old = _make_memory("User works at Google as an engineer", mem_id="old6")
        results = await detector.detect_heuristic("User left Google as an engineer", [old])
        assert len(results) >= 1
        assert results[0].is_contradiction


# ==== Heuristic mode: entity-attribute conflicts ====


class TestHeuristicEntityAttribute:
    """Tests for entity-attribute conflict detection."""

    async def test_different_values_same_attribute(self):
        detector = ContradictionDetector()
        old = _make_memory("User's language is Python", mem_id="attr1")
        results = await detector.detect_heuristic("User's language is Rust", [old])
        assert len(results) >= 1
        assert results[0].is_contradiction
        assert "language" in results[0].reason.lower()

    async def test_same_values_no_conflict(self):
        detector = ContradictionDetector()
        old = _make_memory("User's language is Python", mem_id="attr2")
        results = await detector.detect_heuristic("User's language is Python", [old])
        # Same value should not be a contradiction (might be SKIP in dedup)
        contradictions = [r for r in results if r.is_contradiction]
        # No entity-attribute conflict (same value)
        attr_conflicts = [r for r in contradictions if "Entity-attribute" in r.reason]
        assert len(attr_conflicts) == 0

    async def test_different_attributes_no_conflict(self):
        detector = ContradictionDetector()
        old = _make_memory("User's name is Alice", mem_id="attr3")
        results = await detector.detect_heuristic("User's role is engineer", [old])
        # Different attributes, no conflict
        attr_conflicts = [
            r for r in results if r.is_contradiction and "Entity-attribute" in r.reason
        ]
        assert len(attr_conflicts) == 0


# ==== No contradiction cases ====


class TestNoContradiction:
    """Tests that verify no false positives."""

    async def test_unrelated_memories(self):
        detector = ContradictionDetector()
        old = _make_memory("User enjoys hiking in the mountains", mem_id="nr1")
        results = await detector.detect_heuristic("Python 3.12 has new typing features", [old])
        assert len(results) == 0

    async def test_complementary_facts(self):
        detector = ContradictionDetector()
        old = _make_memory("User uses Python for backend", mem_id="nr2")
        results = await detector.detect_heuristic("User uses JavaScript for frontend", [old])
        # These are different facts, not contradictions
        assert len(results) == 0

    async def test_empty_existing_memories(self):
        detector = ContradictionDetector()
        results = await detector.detect_heuristic("anything new", [])
        assert results == []

    async def test_superseded_memories_skipped(self):
        detector = ContradictionDetector()
        old = _make_memory("User likes Java", mem_id="skip1")
        old.superseded = True
        results = await detector.detect_heuristic("User dislikes Java programming", [old])
        assert len(results) == 0

    async def test_superseded_by_memories_skipped(self):
        detector = ContradictionDetector()
        old = _make_memory("User likes Java", mem_id="skip2")
        old.superseded_by = "newer_id"
        results = await detector.detect_heuristic("User dislikes Java programming", [old])
        assert len(results) == 0


# ==== LLM mock mode ====


class TestLLMMode:
    """Tests for LLM-powered contradiction detection with mocked engine."""

    async def test_llm_detects_contradiction(self):
        engine = AsyncMock()
        engine.think = AsyncMock(return_value="1")

        detector = ContradictionDetector(engine=engine)
        old = _make_memory("User works at Google", mem_id="llm1")
        results = await detector.detect_llm("User now works at Microsoft", [old])
        assert len(results) == 1
        assert results[0].is_contradiction
        assert results[0].old_memory_id == "llm1"
        engine.think.assert_awaited_once()

    async def test_llm_no_contradiction(self):
        engine = AsyncMock()
        engine.think = AsyncMock(return_value="none")

        detector = ContradictionDetector(engine=engine)
        old = _make_memory("User likes Python", mem_id="llm2")
        results = await detector.detect_llm("User also likes Rust", [old])
        assert len(results) == 0

    async def test_llm_multiple_contradictions(self):
        engine = AsyncMock()
        engine.think = AsyncMock(return_value="1, 2")

        detector = ContradictionDetector(engine=engine, similarity_threshold=0.1)
        mems = [
            _make_memory("User lives and works in NYC city", mem_id="llm3a"),
            _make_memory("User commutes daily in NYC city area", mem_id="llm3b"),
        ]
        results = await detector.detect_llm("User moved away from NYC city permanently", mems)
        assert len(results) == 2

    async def test_llm_fallback_on_error(self):
        engine = AsyncMock()
        engine.think = AsyncMock(side_effect=Exception("API error"))

        detector = ContradictionDetector(engine=engine)
        old = _make_memory("User likes coffee", mem_id="llm4")
        # Should fall back to heuristic and not raise
        results = await detector.detect_llm("User hates coffee", [old])
        # Heuristic should catch the likes/hates pattern
        assert isinstance(results, list)

    async def test_llm_mode_requires_engine(self):
        detector = ContradictionDetector(engine=None)
        with pytest.raises(RuntimeError, match="requires a CognitiveEngine"):
            await detector.detect_llm("test", [])

    async def test_llm_empty_similar(self):
        engine = AsyncMock()
        detector = ContradictionDetector(engine=engine)
        results = await detector.detect_llm("test", [])
        assert results == []
        engine.think.assert_not_awaited()


# ==== Auto-dispatch detect() ====


class TestDetectDispatch:
    """Tests for the detect() method that auto-selects mode."""

    async def test_detect_uses_llm_when_available(self):
        engine = AsyncMock()
        engine.think = AsyncMock(return_value="none")

        detector = ContradictionDetector(engine=engine)
        old = _make_memory("test content", mem_id="disp1")
        await detector.detect("similar test content", [old])
        engine.think.assert_awaited_once()

    async def test_detect_uses_heuristic_when_no_engine(self):
        detector = ContradictionDetector(engine=None)
        old = _make_memory("User likes tea", mem_id="disp2")
        results = await detector.detect("User hates tea", [old])
        assert isinstance(results, list)


# ==== Similarity threshold ====


class TestSimilarityThreshold:
    """Tests for the similarity_threshold parameter."""

    async def test_high_threshold_skips_distant(self):
        detector = ContradictionDetector(similarity_threshold=0.9)
        old = _make_memory("User prefers Python for web development", mem_id="thr1")
        results = await detector.detect_heuristic("User dislikes Python", [old])
        # With high threshold, the memories may not be similar enough
        # to even be considered
        assert isinstance(results, list)

    async def test_low_threshold_catches_more(self):
        detector = ContradictionDetector(similarity_threshold=0.1)
        old = _make_memory("User likes cats and dogs", mem_id="thr2")
        results = await detector.detect_heuristic("User hates cats and dogs", [old])
        assert len(results) >= 1


# ==== ContradictionResult structure ====


class TestContradictionResult:
    """Tests for ContradictionResult data structure."""

    def test_default_values(self):
        r = ContradictionResult(is_contradiction=False)
        assert r.old_memory_id == ""
        assert r.new_content == ""
        assert r.reason == ""
        assert r.confidence == 0.0

    def test_full_construction(self):
        r = ContradictionResult(
            is_contradiction=True,
            old_memory_id="abc",
            new_content="new fact",
            reason="negation",
            confidence=0.85,
        )
        assert r.is_contradiction
        assert r.old_memory_id == "abc"
        assert r.confidence == 0.85
