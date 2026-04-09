# test_memory.py — Tests for the memory subsystem (MemoryManager facade).
# Created: 2026-02-22 — Covers core memory, episodic/semantic/procedural stores,
# cross-store recall, memory removal, knowledge graph, and clear operations.
# Updated: 2026-03-06 — Updated test_core_memory_edit to expect replace behavior
#   per Bug #15 fix (edit_core now replaces instead of appending).

from __future__ import annotations

import pytest

from soul_protocol.runtime.memory.graph import KnowledgeGraph
from soul_protocol.runtime.memory.manager import MemoryManager
from soul_protocol.runtime.types import (
    CoreMemory,
    Interaction,
    MemoryEntry,
    MemorySettings,
    MemoryType,
)


@pytest.fixture
def manager() -> MemoryManager:
    """Create a fresh MemoryManager with default settings."""
    return MemoryManager(
        core=CoreMemory(),
        settings=MemorySettings(),
    )


async def test_core_memory_set_and_get(manager: MemoryManager):
    """set_core and get_core work for persona and human fields."""
    manager.set_core(persona="I am Aria, a helpful assistant.", human="")
    core = manager.get_core()
    assert core.persona == "I am Aria, a helpful assistant."
    assert core.human == ""

    manager.set_core(persona=None, human="User is a developer.")
    core = manager.get_core()
    # persona unchanged because we passed None
    assert core.persona == "I am Aria, a helpful assistant."
    assert core.human == "User is a developer."


async def test_core_memory_edit(manager: MemoryManager):
    """edit_core replaces core memory fields (Bug #15 fix)."""
    manager.set_core(persona="I am Aria.", human="User is kind.")

    await manager.edit_core(persona="I love helping.")
    core = manager.get_core()
    assert core.persona == "I love helping."
    assert core.human == "User is kind."

    await manager.edit_core(human="Prefers dark mode.")
    core = manager.get_core()
    assert core.persona == "I love helping."
    assert core.human == "Prefers dark mode."


async def test_episodic_add_and_search(manager: MemoryManager):
    """Adding an episodic interaction and searching by keyword."""
    interaction = Interaction(
        user_input="What is the weather?",
        agent_output="It's sunny today!",
        channel="test",
    )
    mem_id = await manager.add_episodic(interaction)
    assert mem_id

    results = await manager.recall("weather")
    assert len(results) >= 1
    assert any("weather" in r.content.lower() for r in results)


async def test_semantic_add_and_search(manager: MemoryManager):
    """Adding a semantic memory and searching for it."""
    entry = MemoryEntry(
        type=MemoryType.SEMANTIC,
        content="User prefers Python over JavaScript",
        importance=8,
    )
    mem_id = await manager.add(entry)
    assert mem_id

    results = await manager.recall("Python", types=[MemoryType.SEMANTIC])
    assert len(results) >= 1
    assert any("Python" in r.content for r in results)


async def test_procedural_add_and_search(manager: MemoryManager):
    """Adding a procedural memory and searching for it."""
    entry = MemoryEntry(
        type=MemoryType.PROCEDURAL,
        content="To deploy, run: git push origin main",
        importance=7,
    )
    mem_id = await manager.add(entry)
    assert mem_id

    results = await manager.recall("deploy", types=[MemoryType.PROCEDURAL])
    assert len(results) >= 1
    assert any("deploy" in r.content.lower() for r in results)


async def test_recall_across_stores(manager: MemoryManager):
    """recall() finds results across episodic and semantic stores."""
    # Add a semantic fact
    await manager.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="User loves coffee",
            importance=6,
        )
    )

    # Add an episodic interaction mentioning coffee
    await manager.add_episodic(
        Interaction(
            user_input="I need coffee",
            agent_output="Let me help you find a cafe!",
        )
    )

    # Recall across all stores
    results = await manager.recall("coffee")
    assert len(results) >= 2
    contents = [r.content.lower() for r in results]
    assert any("coffee" in c for c in contents)


async def test_memory_remove(manager: MemoryManager):
    """remove() deletes a memory by ID."""
    entry = MemoryEntry(
        type=MemoryType.SEMANTIC,
        content="User dislikes spam",
        importance=5,
    )
    mem_id = await manager.add(entry)

    # Confirm it exists
    results = await manager.recall("spam")
    assert len(results) >= 1

    # Remove it
    removed = await manager.remove(mem_id)
    assert removed is True

    # Confirm it's gone
    results_after = await manager.recall("spam")
    assert not any(r.id == mem_id for r in results_after)

    # Removing a non-existent ID returns False
    assert await manager.remove("nonexistent-id") is False


def test_knowledge_graph_add_and_query():
    """KnowledgeGraph supports adding entities/relationships and querying them."""
    graph = KnowledgeGraph()

    graph.add_entity("Alice", "person")
    graph.add_entity("Bob", "person")
    graph.add_relationship("Alice", "Bob", "knows")

    assert "Alice" in graph.entities()
    assert "Bob" in graph.entities()

    related = graph.get_related("Alice")
    assert len(related) == 1
    assert related[0]["target"] == "Bob"
    assert related[0]["relation"] == "knows"
    assert related[0]["direction"] == "outgoing"

    # Bob sees it as incoming
    related_bob = graph.get_related("Bob")
    assert len(related_bob) == 1
    assert related_bob[0]["direction"] == "incoming"

    # Serialization roundtrip
    data = graph.to_dict()
    restored = KnowledgeGraph.from_dict(data)
    assert "Alice" in restored.entities()
    assert len(restored.get_related("Alice")) == 1


async def test_memory_manager_clear(manager: MemoryManager):
    """clear() wipes episodic, semantic, and procedural stores (not core)."""
    manager.set_core(persona="I am Aria.", human="User info.")

    await manager.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="some fact",
            importance=5,
        )
    )
    await manager.add_episodic(Interaction(user_input="hello", agent_output="hi"))

    await manager.clear()

    # Stores should be empty
    results = await manager.recall("fact")
    assert results == []

    results = await manager.recall("hello")
    assert results == []

    # Core memory should be preserved
    core = manager.get_core()
    assert core.persona == "I am Aria."
    assert core.human == "User info."


# ============================================================================
# Significance short-circuit tests (PR #149)
# ============================================================================
#
# observe() runs a 6-step pipeline: sentiment → significance → episodic store →
# fact extraction → entity extraction → self-model update. Steps 5 and 6 are
# the most expensive (they call the LLM). When skip_deep_processing_on_low_significance
# is enabled (default), trivial interactions skip steps 5 and 6 entirely.
#
# These tests mock _cognitive.extract_entities and _cognitive.update_self_model
# so we can assert call counts directly. Significance is also mocked for
# deterministic control over the gate.


class TestSignificanceShortCircuit:
    """observe() should skip steps 5 and 6 for low-significance interactions
    when the flag is enabled, and always run them when the flag is disabled."""

    @staticmethod
    def _trivial_score():
        """A SignificanceScore that scores well below the 0.35 threshold."""
        from soul_protocol.runtime.types import SignificanceScore

        return SignificanceScore(
            novelty=0.0,
            emotional_intensity=0.0,
            goal_relevance=0.0,
            content_richness=0.0,
        )

    @staticmethod
    def _significant_score():
        """A SignificanceScore that scores well above the 0.35 threshold."""
        from soul_protocol.runtime.types import SignificanceScore

        return SignificanceScore(
            novelty=0.9,
            emotional_intensity=0.8,
            goal_relevance=0.9,
            content_richness=0.9,
        )

    @staticmethod
    def _neutral_somatic():
        """A neutral SomaticMarker for sentiment mocking."""
        from soul_protocol.runtime.types import SomaticMarker

        return SomaticMarker(valence=0.0, arousal=0.1, label="neutral")

    @pytest.fixture
    def mocked_manager(self) -> MemoryManager:
        """MemoryManager with every LLM-touching cognitive method replaced
        by an AsyncMock, including a safe-default trivial significance score.

        Individual tests override assess_significance to set a specific
        branch; pre-mocking it here guarantees that a test which forgets to
        set a value never falls through to a live LLM call."""
        from unittest.mock import AsyncMock

        mgr = MemoryManager(core=CoreMemory(), settings=MemorySettings())
        mgr._cognitive.detect_sentiment = AsyncMock(return_value=self._neutral_somatic())
        # Safe default — trivial score. Tests that care about the high path
        # override this explicitly.
        mgr._cognitive.assess_significance = AsyncMock(return_value=self._trivial_score())
        mgr._cognitive.extract_facts = AsyncMock(return_value=[])
        mgr._cognitive.extract_entities = AsyncMock(return_value=[])
        mgr._cognitive.update_self_model = AsyncMock()
        return mgr

    async def test_skips_extraction_on_trivial_interaction(self, mocked_manager):
        """Low-significance interaction should skip steps 5 and 6 when the
        default flag is on."""
        from unittest.mock import AsyncMock

        mgr = mocked_manager
        mgr._cognitive.assess_significance = AsyncMock(return_value=self._trivial_score())
        assert mgr._settings.skip_deep_processing_on_low_significance is True

        result = await mgr.observe(Interaction(user_input="ok", agent_output="sure"))

        mgr._cognitive.extract_entities.assert_not_called()
        mgr._cognitive.update_self_model.assert_not_called()
        assert result["is_significant"] is False

    async def test_runs_extraction_on_significant_interaction(self, mocked_manager):
        """High-significance interaction should run steps 5 and 6 regardless
        of the short-circuit flag."""
        from unittest.mock import AsyncMock

        mgr = mocked_manager
        mgr._cognitive.assess_significance = AsyncMock(return_value=self._significant_score())

        result = await mgr.observe(
            Interaction(
                user_input="I'm switching the data pipeline from Python to Rust because of performance",
                agent_output="What's driving the performance switch? Memory, throughput, or startup time?",
            )
        )

        mgr._cognitive.extract_entities.assert_called_once()
        mgr._cognitive.update_self_model.assert_called_once()
        assert result["is_significant"] is True

    async def test_return_shape_preserved_across_both_paths(self, mocked_manager):
        """observe() return dict should have the same keys whether or not
        the short-circuit fires. Callers destructuring the result should
        not break based on the gate decision."""
        from unittest.mock import AsyncMock

        mgr = mocked_manager

        # Trivial path
        mgr._cognitive.assess_significance = AsyncMock(return_value=self._trivial_score())
        trivial = await mgr.observe(Interaction(user_input="ok", agent_output="sure"))

        # Significant path — reset mocks so call counts don't leak
        mgr._cognitive.extract_entities.reset_mock()
        mgr._cognitive.update_self_model.reset_mock()
        mgr._cognitive.assess_significance = AsyncMock(return_value=self._significant_score())
        significant = await mgr.observe(
            Interaction(
                user_input="Shipping the new auth module today with OAuth2 support",
                agent_output="Which identity provider did you end up choosing for the integration?",
            )
        )

        # Identical key sets in both paths
        assert trivial.keys() == significant.keys()
        required = {
            "somatic",
            "significance",
            "is_significant",
            "episodic_id",
            "facts",
            "entities",
            "contradictions",
        }
        assert required.issubset(trivial.keys())
        # Entities should be an empty list in the trivial path, not missing
        assert trivial["entities"] == []

    async def test_disabled_flag_always_runs_extraction(self, mocked_manager):
        """With skip_deep_processing_on_low_significance=False, steps 5 and 6
        should run even on trivial interactions. This is the escape hatch for
        callers who need guaranteed extraction regardless of score."""
        from unittest.mock import AsyncMock

        mgr = mocked_manager
        mgr._settings.skip_deep_processing_on_low_significance = False
        mgr._cognitive.assess_significance = AsyncMock(return_value=self._trivial_score())

        await mgr.observe(Interaction(user_input="ok", agent_output="sure"))

        mgr._cognitive.extract_entities.assert_called_once()
        mgr._cognitive.update_self_model.assert_called_once()

    async def test_fact_promotion_still_triggers_extraction(self, mocked_manager):
        """When significance is low but fact extraction finds facts (step 4b
        promotion), BOTH entity extraction AND self-model update should run.
        This protects the subtle case where a message is short but carries
        meaningful content — steps 5 and 6 rise and fall together inside the
        same else branch, so both must be asserted."""
        from unittest.mock import AsyncMock

        mgr = mocked_manager
        # (assess_significance is already mocked to trivial by the fixture)
        # Fact extraction finds something — this flips `significant` in step 4b
        mgr._cognitive.extract_facts = AsyncMock(
            return_value=[
                MemoryEntry(
                    type=MemoryType.SEMANTIC,
                    content="User moved to Berlin",
                    importance=7,
                )
            ]
        )

        await mgr.observe(
            Interaction(user_input="Moved to Berlin last week", agent_output="Welcome!")
        )

        # Because facts were found, the significance gate flipped to True and
        # BOTH deep-processing steps should have run even though
        # assess_significance scored low
        mgr._cognitive.extract_entities.assert_called_once()
        mgr._cognitive.update_self_model.assert_called_once()
