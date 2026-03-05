# test_memory.py — Tests for the memory subsystem (MemoryManager facade).
# Created: 2026-02-22 — Covers core memory, episodic/semantic/procedural stores,
# cross-store recall, memory removal, knowledge graph, and clear operations.

from __future__ import annotations

import pytest

from soul_protocol.memory.graph import KnowledgeGraph
from soul_protocol.memory.manager import MemoryManager
from soul_protocol.types import (
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
    """edit_core appends text to existing core memory fields."""
    manager.set_core(persona="I am Aria.", human="User is kind.")

    await manager.edit_core(persona="I love helping.")
    core = manager.get_core()
    assert "I am Aria." in core.persona
    assert "I love helping." in core.persona

    await manager.edit_core(human="Prefers dark mode.")
    core = manager.get_core()
    assert "User is kind." in core.human
    assert "Prefers dark mode." in core.human


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
