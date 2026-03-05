# test_extraction.py — Tests for heuristic fact and entity extraction.
# Created: 2026-02-22 — Covers extract_facts (name, preference, tech tool),
#   extract_entities (proper nouns, known tech), deduplication, and the
#   full observe() pipeline in Soul.

from __future__ import annotations

import pytest

from soul_protocol.memory.manager import MemoryManager
from soul_protocol.soul import Soul
from soul_protocol.types import (
    CoreMemory,
    Interaction,
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


# ---- extract_facts tests ----


def test_extract_name(manager: MemoryManager):
    """Detects 'my name is X' and creates a semantic fact."""
    interaction = Interaction(
        user_input="Hi, my name is Prakash",
        agent_output="Nice to meet you, Prakash!",
    )
    facts = manager.extract_facts(interaction)
    assert len(facts) >= 1
    name_facts = [f for f in facts if "name" in f.content.lower()]
    assert len(name_facts) >= 1
    assert "Prakash" in name_facts[0].content
    assert name_facts[0].type == MemoryType.SEMANTIC
    assert name_facts[0].importance == 9


def test_extract_preference(manager: MemoryManager):
    """Detects preference patterns like 'I prefer X' and 'I hate X'."""
    interaction = Interaction(
        user_input="I prefer dark mode and I hate bright themes",
        agent_output="Got it, I'll remember that.",
    )
    facts = manager.extract_facts(interaction)
    contents = [f.content for f in facts]

    # Should find a preference fact
    prefer_facts = [c for c in contents if "prefers" in c.lower()]
    assert len(prefer_facts) >= 1
    assert any("dark mode" in c.lower() for c in prefer_facts)

    # Should find a dislike fact
    dislike_facts = [c for c in contents if "dislikes" in c.lower()]
    assert len(dislike_facts) >= 1
    assert any("bright themes" in c.lower() for c in dislike_facts)


def test_extract_technical_tool(manager: MemoryManager):
    """Detects 'I use X' and 'I work with X' patterns."""
    interaction = Interaction(
        user_input="I use Python and I work with Docker every day",
        agent_output="Great choices!",
    )
    facts = manager.extract_facts(interaction)
    contents = [f.content for f in facts]

    uses_facts = [c for c in contents if "uses" in c.lower()]
    assert len(uses_facts) >= 1
    # At least one should mention Python or Docker
    combined = " ".join(uses_facts).lower()
    assert "python" in combined or "docker" in combined


def test_extract_identity_facts(manager: MemoryManager):
    """Detects identity patterns: 'I work at X', 'I live in X', 'I am from X'."""
    interaction = Interaction(
        user_input="I work at Acme Corp and I'm from Austin",
        agent_output="Noted!",
    )
    facts = manager.extract_facts(interaction)
    contents = [f.content for f in facts]

    work_facts = [c for c in contents if "works at" in c.lower()]
    assert len(work_facts) >= 1
    assert any("acme" in c.lower() for c in work_facts)

    from_facts = [c for c in contents if "from" in c.lower()]
    assert len(from_facts) >= 1
    assert any("austin" in c.lower() for c in from_facts)


def test_extract_building_pattern(manager: MemoryManager):
    """Detects 'I'm building X' pattern."""
    interaction = Interaction(
        user_input="I'm building a chat application",
        agent_output="That sounds exciting!",
    )
    facts = manager.extract_facts(interaction)
    contents = [f.content for f in facts]

    build_facts = [c for c in contents if "building" in c.lower()]
    assert len(build_facts) >= 1
    assert any("chat application" in c.lower() for c in build_facts)


def test_extract_favorite_pattern(manager: MemoryManager):
    """Detects 'my favorite X is Y' pattern."""
    interaction = Interaction(
        user_input="my favorite language is Rust",
        agent_output="Rust is a great language!",
    )
    facts = manager.extract_facts(interaction)
    contents = [f.content for f in facts]

    fav_facts = [c for c in contents if "favorite" in c.lower()]
    assert len(fav_facts) >= 1
    assert any("rust" in c.lower() for c in fav_facts)


def test_no_facts_from_empty_input(manager: MemoryManager):
    """No facts extracted when input has no matching patterns."""
    interaction = Interaction(
        user_input="What is the weather today?",
        agent_output="It's sunny with a high of 75F.",
    )
    facts = manager.extract_facts(interaction)
    assert facts == []


def test_strips_trailing_punctuation(manager: MemoryManager):
    """Captured groups should have trailing punctuation stripped."""
    interaction = Interaction(
        user_input="My name is Alice.",
        agent_output="Hello!",
    )
    facts = manager.extract_facts(interaction)
    name_facts = [f for f in facts if "name" in f.content.lower()]
    assert len(name_facts) >= 1
    # The content should NOT end with a period
    assert not name_facts[0].content.endswith(".")


# ---- extract_entities tests ----


def test_extract_entities_from_text(manager: MemoryManager):
    """Extracts known tech terms and proper nouns from interaction text."""
    interaction = Interaction(
        user_input="I use Python and React for my projects",
        agent_output="Those are popular choices!",
    )
    entities = manager.extract_entities(interaction)
    names_lower = {e["name"].lower() for e in entities}

    assert "python" in names_lower
    assert "react" in names_lower


def test_extract_entities_proper_nouns(manager: MemoryManager):
    """Capitalised words not at sentence start are detected as entities."""
    interaction = Interaction(
        user_input="I met with Sarah about the project",
        agent_output="That sounds productive.",
    )
    entities = manager.extract_entities(interaction)
    names_lower = {e["name"].lower() for e in entities}

    assert "sarah" in names_lower
    sarah_ent = next(e for e in entities if e["name"].lower() == "sarah")
    assert sarah_ent["type"] == "person"


def test_extract_entities_with_relation(manager: MemoryManager):
    """Entity has a relation inferred from context (e.g., 'I use Python')."""
    interaction = Interaction(
        user_input="I use Python daily",
        agent_output="Python is versatile.",
    )
    entities = manager.extract_entities(interaction)
    python_ents = [e for e in entities if e["name"].lower() == "python"]
    assert len(python_ents) == 1
    assert python_ents[0]["relation"] == "uses"
    assert python_ents[0]["type"] == "technology"


def test_extract_entities_building_relation(manager: MemoryManager):
    """'I'm building X' sets relation to 'builds' and type to 'project'."""
    interaction = Interaction(
        user_input="I'm building PocketPaw",
        agent_output="Cool project!",
    )
    entities = manager.extract_entities(interaction)
    pp = [e for e in entities if e["name"].lower() == "pocketpaw"]
    assert len(pp) == 1
    assert pp[0]["relation"] == "builds"
    assert pp[0]["type"] == "project"


def test_extract_entities_no_stop_words(manager: MemoryManager):
    """Common words and pronouns should not appear as entities."""
    interaction = Interaction(
        user_input="The weather is nice today",
        agent_output="I agree, it is lovely!",
    )
    entities = manager.extract_entities(interaction)
    names_lower = {e["name"].lower() for e in entities}

    assert "the" not in names_lower
    assert "is" not in names_lower
    assert "it" not in names_lower
    assert "i" not in names_lower


# ---- deduplication tests ----


async def test_no_duplicate_facts(manager: MemoryManager):
    """Adding the same fact twice via extract_facts skips the duplicate."""
    interaction = Interaction(
        user_input="I prefer dark mode",
        agent_output="Noted!",
    )

    # First extraction — should produce facts
    facts_1 = manager.extract_facts(interaction)
    assert len(facts_1) >= 1

    # Store them
    for fact in facts_1:
        await manager.add(fact)

    # Second extraction of the same interaction — duplicates should be skipped
    facts_2 = manager.extract_facts(interaction)
    # All facts from the second run should have been filtered as duplicates
    assert len(facts_2) == 0


async def test_similar_but_not_identical_facts(manager: MemoryManager):
    """Sufficiently different facts should NOT be deduped."""
    # Store a fact about dark mode
    interaction1 = Interaction(
        user_input="I prefer dark mode",
        agent_output="Sure!",
    )
    facts_1 = manager.extract_facts(interaction1)
    for fact in facts_1:
        await manager.add(fact)

    # A different preference should still be extracted
    interaction2 = Interaction(
        user_input="I prefer large fonts",
        agent_output="Got it!",
    )
    facts_2 = manager.extract_facts(interaction2)
    assert len(facts_2) >= 1
    assert any("large fonts" in f.content.lower() for f in facts_2)


# ---- Full pipeline: Soul.observe() ----


async def test_extract_from_observe():
    """Full pipeline: create soul, observe interaction, recall the extracted fact."""
    soul = await Soul.birth("TestSoul")

    interaction = Interaction(
        user_input="My name is Prakash and I use Python",
        agent_output="Nice to meet you, Prakash!",
    )
    await soul.observe(interaction)

    # Recall should find the extracted name fact
    results = await soul.recall("Prakash", types=[MemoryType.SEMANTIC])
    assert len(results) >= 1
    assert any("prakash" in r.content.lower() for r in results)

    # Recall should also find the Python usage fact
    results_python = await soul.recall("Python", types=[MemoryType.SEMANTIC])
    assert len(results_python) >= 1
    assert any("python" in r.content.lower() for r in results_python)


async def test_observe_updates_knowledge_graph():
    """observe() adds extracted entities to the knowledge graph."""
    soul = await Soul.birth("GraphSoul")

    interaction = Interaction(
        user_input="I use Docker and I'm building PocketPaw",
        agent_output="Great stack!",
    )
    await soul.observe(interaction)

    # Access the internal graph to verify entities were added
    graph = soul._memory._graph
    entity_names = [e.lower() for e in graph.entities()]

    assert "docker" in entity_names
    assert "pocketpaw" in entity_names
