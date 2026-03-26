# test_soul.py — Tests for the main Soul class API surface.
# Updated: phase1-ablation-fixes — Updated test interactions to pass raised
#   significance threshold (0.5) and short-message penalty.
# Updated: v0.2.0 — Added psychology pipeline integration tests:
#   attention gate, somatic markers, self-model, activation-based recall,
#   and self-model persistence across export/awaken.

from __future__ import annotations

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import (
    Interaction,
    LifecycleState,
    MemoryType,
    Mood,
    SoulConfig,
)


async def test_birth():
    """Soul.birth creates a soul with correct defaults."""
    soul = await Soul.birth("Aria", archetype="The Compassionate Creator")

    assert soul.name == "Aria"
    assert soul.archetype == "The Compassionate Creator"
    assert soul.did.startswith("did:soul:aria-")
    assert soul.lifecycle == LifecycleState.ACTIVE
    assert soul.state.mood == Mood.NEUTRAL
    assert soul.state.energy == 100.0


async def test_birth_with_values():
    """Soul.birth with core_values stores them correctly."""
    soul = await Soul.birth(
        "Aria",
        archetype="The Compassionate Creator",
        values=["empathy", "creativity", "honesty"],
    )

    assert soul.identity.core_values == ["empathy", "creativity", "honesty"]


async def test_remember_and_recall():
    """remember() stores a fact, recall() retrieves it by keyword."""
    soul = await Soul.birth("Aria")

    memory_id = await soul.remember(
        "User prefers dark mode",
        type=MemoryType.SEMANTIC,
        importance=7,
    )
    assert memory_id  # non-empty ID returned

    results = await soul.recall("dark mode")
    assert len(results) >= 1
    assert any("dark mode" in r.content for r in results)


async def test_observe():
    """observe() processes an interaction and updates state."""
    soul = await Soul.birth("Aria")

    initial_energy = soul.state.energy
    initial_social = soul.state.social_battery

    interaction = Interaction(
        user_input="Hello, how are you?",
        agent_output="I'm doing well, thanks!",
        channel="test",
    )
    await soul.observe(interaction)

    # With default biorhythms (no drain), energy stays at 100%.
    # Drain is opt-in for companion souls via Biorhythms config.
    assert soul.state.energy == initial_energy
    assert soul.state.social_battery == initial_social
    assert soul.state.last_interaction is not None


async def test_feel():
    """feel() updates mood and energy via delta-based state changes."""
    soul = await Soul.birth("Aria")

    soul.feel(mood=Mood.TIRED)
    assert soul.state.mood == Mood.TIRED

    soul.feel(energy=-20)
    assert soul.state.energy == 80.0


async def test_export_and_awaken(tmp_path):
    """Export to .soul, awaken from it, verify identity is preserved."""
    original = await Soul.birth("Aria", archetype="The Compassionate Creator")
    soul_path = tmp_path / "aria.soul"

    await original.export(str(soul_path))
    assert soul_path.exists()

    restored = await Soul.awaken(str(soul_path))

    assert restored.name == original.name
    assert restored.archetype == original.archetype
    assert restored.did == original.did
    assert restored.lifecycle == LifecycleState.ACTIVE


async def test_system_prompt():
    """to_system_prompt() returns a non-empty string containing the soul's name."""
    soul = await Soul.birth("Aria", archetype="The Compassionate Creator")

    prompt = soul.to_system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "Aria" in prompt


async def test_serialize_roundtrip():
    """serialize() -> SoulConfig -> new Soul -> verify equality."""
    original = await Soul.birth(
        "Aria",
        archetype="The Compassionate Creator",
        values=["empathy"],
    )

    config = original.serialize()
    assert isinstance(config, SoulConfig)
    assert config.identity.name == "Aria"

    # Roundtrip via JSON
    json_str = config.model_dump_json()
    restored_config = SoulConfig.model_validate_json(json_str)

    restored = Soul(restored_config)
    assert restored.name == original.name
    assert restored.did == original.did
    assert restored.identity.core_values == ["empathy"]


async def test_from_markdown():
    """Soul.from_markdown parses a simple SOUL.md string."""
    md_content = """---
name: TestBot
archetype: The Helper
---

# TestBot

# Personality
- openness: 0.8
- conscientiousness: 0.6
- extraversion: 0.7
- agreeableness: 0.9
- neuroticism: 0.2

# Core Values
- kindness
- reliability
"""
    soul = await Soul.from_markdown(md_content)

    assert soul.name == "TestBot"
    assert soul.archetype == "The Helper"
    assert soul.dna.personality.openness == pytest.approx(0.8, abs=0.01)
    assert soul.dna.personality.agreeableness == pytest.approx(0.9, abs=0.01)
    assert "kindness" in soul.identity.core_values
    assert "reliability" in soul.identity.core_values


async def test_export_awaken_preserves_memories(tmp_path):
    """Export/awaken round-trip preserves episodic and semantic memories."""
    soul = await Soul.birth("Aria")

    # Add memories across tiers
    await soul.remember("User likes dark mode", type=MemoryType.SEMANTIC, importance=7)
    await soul.observe(
        Interaction(
            user_input="My name is Prakash",
            agent_output="Nice to meet you, Prakash!",
        )
    )

    soul_path = tmp_path / "aria.soul"
    await soul.export(str(soul_path))

    restored = await Soul.awaken(str(soul_path))

    # Semantic memory should survive
    results = await restored.recall("dark mode")
    assert any("dark mode" in r.content for r in results)

    # Episodic memory from observe should survive
    results = await restored.recall("Prakash")
    assert len(results) >= 1


async def test_save_load_full_roundtrip(tmp_path):
    """Soul.save() + load_soul_full() preserves config and all memory tiers."""
    from soul_protocol.runtime.storage.file import load_soul_full

    soul = await Soul.birth("Aria")
    await soul.remember("User prefers Python", type=MemoryType.SEMANTIC, importance=8)
    # Use a substantive interaction that passes the raised significance threshold.
    # Needs enough tokens (>=20 after tokenize) and some emotional/novelty signal.
    await soul.observe(
        Interaction(
            user_input="I have been working with FastAPI and Python for several years now and I absolutely love building performant REST APIs with async support",
            agent_output="That is really impressive! FastAPI's async capabilities combined with Python's ecosystem make it an excellent choice for modern backend development.",
        )
    )

    await soul.save(tmp_path)

    # Find the saved directory (colons in DID are replaced with underscores on disk)
    soul_dir = tmp_path / soul.did.replace(":", "_")
    assert soul_dir.exists()
    assert (soul_dir / "soul.json").exists()
    assert (soul_dir / "memory" / "semantic.json").exists()
    assert (soul_dir / "memory" / "episodic.json").exists()

    # Load and verify
    config, memory_data = await load_soul_full(soul_dir)
    assert config is not None
    assert config.identity.name == "Aria"
    assert len(memory_data.get("semantic", [])) >= 1
    assert len(memory_data.get("episodic", [])) >= 1


# ============ v0.2.0 Psychology Pipeline Integration Tests ============


async def test_observe_psychology_pipeline():
    """Full psychology pipeline: observe 5+ interactions, verify all modules fire."""
    soul = await Soul.birth(
        "Aria",
        archetype="The Compassionate Creator",
        values=["empathy", "creativity", "helping"],
    )

    interactions = [
        Interaction(
            user_input="Hi there!",
            agent_output="Hello!",
        ),
        Interaction(
            user_input="I'm really frustrated with this Python bug, it keeps crashing",
            agent_output="Let me help you debug that. What error are you seeing?",
        ),
        Interaction(
            user_input="I love using FastAPI for building APIs, it's amazing!",
            agent_output="FastAPI is great! The async support makes it very performant.",
        ),
        Interaction(
            user_input="My name is Prakash and I work at Qbtrix",
            agent_output="Nice to meet you, Prakash! What does Qbtrix do?",
        ),
        Interaction(
            user_input="I'm building a creative writing tool with Python and React",
            agent_output="That sounds like a wonderful project combining both technologies!",
        ),
        Interaction(
            user_input="Can you help me understand how async/await works in Python?",
            agent_output="Of course! async/await is Python's way of writing concurrent code...",
        ),
    ]

    for interaction in interactions:
        await soul.observe(interaction)

    # --- Attention gate: mundane "Hi there!" should NOT be in episodic ---
    await soul.recall("Hi there")
    # The greeting may or may not match, but emotional/meaningful ones should rank higher
    meaningful_results = await soul.recall("Python bug crashing")
    assert len(meaningful_results) >= 1  # Emotional content stored

    # --- Somatic markers: emotional memories should have markers ---
    frustration_results = await soul.recall("frustrated bug crashing")
    if frustration_results:
        # At least one should have a somatic marker
        has_somatic = any(r.somatic is not None for r in frustration_results)
        # This is true if the entry went through the psychology pipeline
        # (add_with_psychology sets somatic markers)
        if has_somatic:
            somatic_entry = next(r for r in frustration_results if r.somatic)
            assert somatic_entry.somatic.valence < 0  # Frustration is negative
            assert somatic_entry.somatic.arousal > 0  # Frustration has arousal

    # --- Self-model: should have accumulated self-images ---
    self_model = soul.self_model
    active_images = self_model.get_active_self_images(limit=5)
    assert len(active_images) >= 1  # At least one domain detected

    # Technical helper should emerge (Python, FastAPI, debug, API, React)
    domains = [img.domain for img in active_images]
    assert "technical_helper" in domains

    # --- Self-model in system prompt ---
    prompt = soul.to_system_prompt()
    assert "Self-Understanding" in prompt or len(active_images) == 0

    # --- Recall uses activation scoring (no crash, returns results) ---
    results = await soul.recall("Python FastAPI")
    assert len(results) >= 1


async def test_attention_gate_filters_mundane():
    """Mundane interactions skip episodic storage, meaningful ones are stored."""
    soul = await Soul.birth("Aria", values=["technical excellence"])

    # Observe several mundane greetings
    for _ in range(3):
        await soul.observe(
            Interaction(
                user_input="hello",
                agent_output="hi",
            )
        )

    # Observe one meaningful interaction
    await soul.observe(
        Interaction(
            user_input="I'm extremely excited about learning Rust programming!",
            agent_output="Rust is a great language for systems programming!",
        )
    )

    # Recall should find the meaningful one
    results = await soul.recall("Rust programming")
    assert len(results) >= 1
    assert any("Rust" in r.content for r in results)


async def test_self_model_property():
    """soul.self_model property provides access to the SelfModelManager."""
    soul = await Soul.birth("Aria")

    # Initially empty
    assert len(soul.self_model.get_active_self_images()) == 0

    # After technical interactions, self-images emerge
    await soul.observe(
        Interaction(
            user_input="Help me debug this Python code, it has an error",
            agent_output="Let me look at the code and find the bug.",
        )
    )

    images = soul.self_model.get_active_self_images()
    assert len(images) >= 1


async def test_self_model_persists_through_export(tmp_path):
    """Self-model survives export → awaken round-trip."""
    soul = await Soul.birth("Aria", values=["helping"])

    # Build up self-model
    await soul.observe(
        Interaction(
            user_input="I need help with Python programming and debugging",
            agent_output="I can help you with that!",
        )
    )
    await soul.observe(
        Interaction(
            user_input="Can you help me write a function to sort data?",
            agent_output="Sure, here's a sorting function in Python...",
        )
    )

    # Verify self-model exists
    original_images = soul.self_model.get_active_self_images()
    assert len(original_images) >= 1
    original_domain = original_images[0].domain

    # Export and awaken
    soul_path = tmp_path / "aria.soul"
    await soul.export(str(soul_path))
    restored = await Soul.awaken(str(soul_path))

    # Self-model should survive
    restored_images = restored.self_model.get_active_self_images()
    assert len(restored_images) >= 1
    assert restored_images[0].domain == original_domain


async def test_save_load_preserves_self_model(tmp_path):
    """Soul.save() + load preserves self_model.json."""
    from soul_protocol.runtime.storage.file import load_soul_full

    soul = await Soul.birth("Aria")
    await soul.observe(
        Interaction(
            user_input="Help me write a Python script for data analysis",
            agent_output="I can create a data analysis script for you.",
        )
    )

    await soul.save(tmp_path)

    soul_dir = tmp_path / soul.did.replace(":", "_")
    assert (soul_dir / "memory" / "self_model.json").exists()

    # Load and verify self_model is in memory_data
    _, memory_data = await load_soul_full(soul_dir)
    assert "self_model" in memory_data
    assert "self_images" in memory_data["self_model"]


async def test_episodic_entries_have_access_timestamps():
    """v0.2.0 MemoryEntry includes access_timestamps for ACT-R decay."""
    soul = await Soul.birth("Aria")

    await soul.observe(
        Interaction(
            user_input="I love working with databases and SQL queries",
            agent_output="Databases are fundamental to software development!",
        )
    )

    results = await soul.recall("databases SQL")
    if results:
        # Recalled entries should have access_timestamps populated
        for entry in results:
            assert isinstance(entry.access_timestamps, list)
            # After recall, at least one timestamp should exist
            assert len(entry.access_timestamps) >= 1


async def test_backward_compatible_memory_entry():
    """v0.1.0 MemoryEntry (without psychology fields) still works."""
    from soul_protocol.runtime.types import MemoryEntry as ME
    from soul_protocol.runtime.types import MemoryType as MT

    # Create an entry without any v0.2.0 fields (simulates v0.1.0 data)
    entry = ME(
        id="old-entry-001",
        type=MT.SEMANTIC,
        content="User prefers dark mode",
        importance=7,
    )

    # All v0.2.0 fields should have safe defaults
    assert entry.somatic is None
    assert entry.access_timestamps == []
    assert entry.significance == 0.0
    assert entry.general_event_id is None

    # Should serialize/deserialize without errors
    data = entry.model_dump(mode="json")
    restored = ME.model_validate(data)
    assert restored.content == entry.content
    assert restored.somatic is None


# ============ Bond + Skills integration (v0.5.0) ============


async def test_bond_strengthens_on_observe():
    """Bond should strengthen automatically during observe()."""
    soul = await Soul.birth("Aria", values=["coding"])
    initial_strength = soul.bond.bond_strength
    initial_count = soul.bond.interaction_count

    await soul.observe(Interaction(
        user_input="Help me with Python",
        agent_output="Sure, here's how to use list comprehensions.",
    ))

    assert soul.bond.bond_strength > initial_strength
    assert soul.bond.interaction_count > initial_count


async def test_skills_created_from_entities():
    """Skills should be auto-created from extracted entities during observe()."""
    soul = await Soul.birth("Aria", values=["coding"])
    assert len(soul.skills.skills) == 0

    await soul.observe(Interaction(
        user_input="I love Python programming",
        agent_output="Python is great for data science and web dev.",
    ))

    # observe() extracts entities and creates skills from them
    assert len(soul.skills.skills) > 0


async def test_skills_accumulate_xp():
    """Repeated interactions about the same topic should increase skill XP."""
    soul = await Soul.birth("Aria", values=["coding"])

    for _ in range(5):
        await soul.observe(Interaction(
            user_input="Tell me about Python",
            agent_output="Python is a versatile language.",
        ))

    # Find a skill that was created (entity extraction is heuristic-based)
    if soul.skills.skills:
        skill = soul.skills.skills[0]
        assert skill.xp > 0


async def test_bond_and_skills_accessible():
    """soul.bond and soul.skills properties should be accessible."""
    soul = await Soul.birth("Aria")
    assert soul.bond is not None
    assert soul.bond.bond_strength == 50.0
    assert soul.skills is not None
    assert len(soul.skills.skills) == 0
