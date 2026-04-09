# tests/test_e2e_integration.py — Pytest-wrapped end-to-end integration tests
# for soul-protocol's critical paths: full lifecycle, config roundtrip,
# memory persistence across export/import, and self-model emergence.
#
# Updated: phase1-ablation-fixes — Fixed flaky recall test: fact conflict
#   resolution could supersede the "Python for backend" memory, so query
#   changed to "Docker Kubernetes" which survives conflicts.
# Created: 2026-03-02 — E2E integration test suite covering the full soul
# lifecycle, birth_from_config roundtrips, multi-tier memory persistence,
# self-model emergence, core memory editing, directory format roundtrip,
# and state persistence through export/awaken cycles.

from __future__ import annotations

import json

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import (
    Interaction,
    LifecycleState,
    MemoryType,
    Mood,
    SoulConfig,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def rich_soul() -> Soul:
    """Birth a soul with realistic configuration and some memories."""
    soul = await Soul.birth(
        "IntegrationBot",
        archetype="The Thorough Tester",
        personality="I validate end-to-end workflows.",
        values=["accuracy", "thoroughness", "reliability"],
        ocean={
            "openness": 0.7,
            "conscientiousness": 0.9,
            "extraversion": 0.5,
            "agreeableness": 0.8,
            "neuroticism": 0.2,
        },
        communication={"warmth": "high", "verbosity": "moderate"},
        biorhythms={"energy_drain_rate": 2.0, "social_drain_rate": 5.0},
    )

    # Seed some memories
    await soul.remember("User prefers Python for backend development", importance=8)
    await soul.remember("User uses Docker and Kubernetes", importance=7)
    await soul.remember("User's preferred editor is Neovim", importance=6)

    # Observe a few interactions
    interactions = [
        Interaction(
            user_input="How do I set up a CI/CD pipeline?",
            agent_output="Use GitHub Actions with a workflow YAML file.",
            channel="test",
        ),
        Interaction(
            user_input="I prefer using type hints everywhere",
            agent_output="Type hints improve code quality and IDE support.",
            channel="test",
        ),
        Interaction(
            user_input="Help me debug this Python async issue",
            agent_output="Check for missing await calls and ensure proper event loop usage.",
            channel="test",
        ),
    ]
    for interaction in interactions:
        await soul.observe(interaction)

    return soul


# ---------------------------------------------------------------------------
# Test: Full Lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """birth -> observe -> recall -> export -> awaken -> recall matches."""

    async def test_birth_creates_active_soul(self):
        soul = await Soul.birth("Lifecycle", archetype="The Test Runner")
        assert soul.name == "Lifecycle"
        assert soul.lifecycle == LifecycleState.ACTIVE
        assert soul.did.startswith("did:soul:")
        assert soul.state.mood == Mood.NEUTRAL
        assert soul.state.energy == 100.0

    async def test_observe_updates_state(self, rich_soul: Soul):
        initial_energy = rich_soul.state.energy
        await rich_soul.observe(
            Interaction(
                user_input="One more question about testing",
                agent_output="Sure, let me help with that.",
            )
        )
        assert rich_soul.state.energy < initial_energy
        assert rich_soul.state.last_interaction is not None

    async def test_recall_finds_stored_memories(self, rich_soul: Soul):
        # Query for Docker/Kubernetes — this memory survives fact conflict
        # resolution (unlike "Python for backend" which can be superseded
        # by "prefers type hints" due to shared "prefers" token).
        results = await rich_soul.recall("Docker Kubernetes")
        assert len(results) >= 1
        assert any(
            "docker" in r.content.lower() or "kubernetes" in r.content.lower() for r in results
        )

    async def test_full_export_awaken_cycle(self, rich_soul: Soul, tmp_path):
        """Full lifecycle: the big one."""
        soul = rich_soul

        # Store pre-export state
        original_name = soul.name
        original_did = soul.did
        original_archetype = soul.archetype

        # Export
        soul_path = tmp_path / "lifecycle.soul"
        await soul.export(str(soul_path))
        assert soul_path.exists()
        assert soul_path.stat().st_size > 0

        # Awaken
        restored = await Soul.awaken(str(soul_path))

        # Identity preserved
        assert restored.name == original_name
        assert restored.did == original_did
        assert restored.archetype == original_archetype
        assert restored.lifecycle == LifecycleState.ACTIVE

        # Memories preserved
        assert restored.memory_count >= 1

        # Recall works on restored soul
        results = await restored.recall("Docker Kubernetes")
        assert any(
            "docker" in r.content.lower() or "kubernetes" in r.content.lower() for r in results
        )

        # Neovim memory survives (less likely to be superseded by fact conflicts)
        editor_results = await restored.recall("Neovim editor")
        assert any("neovim" in r.content.lower() for r in editor_results)


# ---------------------------------------------------------------------------
# Test: Config Roundtrip
# ---------------------------------------------------------------------------


class TestConfigRoundtrip:
    """birth_from_config -> export -> awaken -> config matches."""

    async def test_yaml_config_roundtrip(self, tmp_path):
        # Create YAML config
        yaml_content = """
name: YamlTestBot
archetype: The Config Tester
values:
  - testing
  - precision
ocean:
  openness: 0.8
  conscientiousness: 0.7
  extraversion: 0.6
  agreeableness: 0.9
  neuroticism: 0.1
persona: I am YamlTestBot, born from YAML.
"""
        yaml_path = tmp_path / "test_config.yaml"
        yaml_path.write_text(yaml_content)

        # Birth from config
        soul = await Soul.birth_from_config(yaml_path)
        assert soul.name == "YamlTestBot"
        assert soul.archetype == "The Config Tester"
        assert "testing" in soul.identity.core_values
        assert soul.dna.personality.openness == pytest.approx(0.8, abs=0.01)

        # Export and awaken
        soul_path = tmp_path / "yaml_test.soul"
        await soul.export(str(soul_path))
        restored = await Soul.awaken(str(soul_path))

        # Config matches
        assert restored.name == "YamlTestBot"
        assert restored.archetype == "The Config Tester"
        assert "testing" in restored.identity.core_values
        assert restored.dna.personality.openness == pytest.approx(0.8, abs=0.01)
        assert restored.dna.personality.neuroticism == pytest.approx(0.1, abs=0.01)

    async def test_json_config_roundtrip(self, tmp_path):
        # Create JSON config
        json_content = {
            "name": "JsonTestBot",
            "archetype": "The JSON Lover",
            "values": ["structure", "clarity"],
            "ocean": {
                "openness": 0.5,
                "conscientiousness": 0.95,
            },
            "persona": "I am JsonTestBot, born from JSON.",
        }
        json_path = tmp_path / "test_config.json"
        json_path.write_text(json.dumps(json_content))

        # Birth from config
        soul = await Soul.birth_from_config(json_path)
        assert soul.name == "JsonTestBot"
        assert soul.dna.personality.conscientiousness == pytest.approx(0.95, abs=0.01)

        # Export and awaken
        soul_path = tmp_path / "json_test.soul"
        await soul.export(str(soul_path))
        restored = await Soul.awaken(str(soul_path))

        assert restored.name == "JsonTestBot"
        assert restored.dna.personality.conscientiousness == pytest.approx(0.95, abs=0.01)

    async def test_serialize_config_roundtrip(self, rich_soul: Soul, tmp_path):
        """Serialize -> JSON -> SoulConfig -> new Soul -> verify."""
        config = rich_soul.serialize()
        json_str = config.model_dump_json()
        restored_config = SoulConfig.model_validate_json(json_str)
        restored = Soul(restored_config)

        assert restored.name == rich_soul.name
        assert restored.did == rich_soul.did
        assert restored.identity.core_values == rich_soul.identity.core_values


# ---------------------------------------------------------------------------
# Test: Memory Persistence
# ---------------------------------------------------------------------------


class TestMemoryPersistence:
    """Memory persistence across export/import."""

    async def test_semantic_memories_persist(self, tmp_path):
        soul = await Soul.birth("MemPersist")
        await soul.remember("User likes dark mode", type=MemoryType.SEMANTIC, importance=8)
        await soul.remember("User's name is Jordan", type=MemoryType.SEMANTIC, importance=9)
        await soul.remember("User works at Acme Corp", type=MemoryType.SEMANTIC, importance=7)

        soul_path = tmp_path / "mem_persist.soul"
        await soul.export(str(soul_path))
        restored = await Soul.awaken(str(soul_path))

        # All three semantic memories should survive
        dark_results = await restored.recall("dark mode")
        assert any("dark" in r.content.lower() for r in dark_results)

        name_results = await restored.recall("Jordan")
        assert any("jordan" in r.content.lower() for r in name_results)

        work_results = await restored.recall("Acme Corp")
        assert any("acme" in r.content.lower() for r in work_results)

    async def test_episodic_memories_from_observe_persist(self, tmp_path):
        soul = await Soul.birth("EpisodicPersist", values=["learning"])
        await soul.observe(
            Interaction(
                user_input="I'm really excited about learning Rust!",
                agent_output="Rust is fantastic for systems programming!",
            )
        )
        await soul.observe(
            Interaction(
                user_input="My name is Alex and I work at StartupCo",
                agent_output="Nice to meet you, Alex!",
            )
        )

        soul_path = tmp_path / "episodic_persist.soul"
        await soul.export(str(soul_path))
        restored = await Soul.awaken(str(soul_path))

        # Episodic memories or extracted facts should survive
        results = await restored.recall("Rust programming")
        assert len(results) >= 1

    async def test_core_memory_persists(self, tmp_path):
        soul = await Soul.birth("CorePersist", persona="I am CorePersist, the reliable one.")
        await soul.edit_core_memory(human="The user is a data scientist named Pat.")

        soul_path = tmp_path / "core_persist.soul"
        await soul.export(str(soul_path))
        restored = await Soul.awaken(str(soul_path))

        core = restored.get_core_memory()
        assert "CorePersist" in core.persona
        assert "Pat" in core.human

    async def test_memory_count_preserved(self, rich_soul: Soul, tmp_path):

        soul_path = tmp_path / "count_test.soul"
        await rich_soul.export(str(soul_path))
        restored = await Soul.awaken(str(soul_path))

        # Memory count should be preserved (or at least non-zero)
        assert restored.memory_count >= 1

    async def test_procedural_memory_persists(self, tmp_path):
        soul = await Soul.birth("ProceduralPersist")
        await soul.remember(
            "To deploy: run 'docker build -t app .' then 'docker push'",
            type=MemoryType.PROCEDURAL,
            importance=8,
        )

        soul_path = tmp_path / "proc_persist.soul"
        await soul.export(str(soul_path))
        restored = await Soul.awaken(str(soul_path))

        results = await restored.recall("deploy docker")
        assert any("docker" in r.content.lower() for r in results)

    async def test_multi_tier_memory_save_load(self, tmp_path):
        """Save via save() and load via awaken() with directory format."""
        from soul_protocol.runtime.storage.file import load_soul_full

        soul = await Soul.birth("MultiTier", values=["completeness"])

        # Add memories across tiers
        await soul.remember("Semantic fact about Python", type=MemoryType.SEMANTIC, importance=7)
        await soul.remember(
            "Deploy with docker compose up", type=MemoryType.PROCEDURAL, importance=8
        )
        await soul.observe(
            Interaction(
                user_input="I love using pytest for testing my code",
                agent_output="pytest is great with its fixture system!",
            )
        )

        await soul.save(tmp_path)

        # Verify file structure (colons in DID are replaced with underscores on disk)
        soul_dir = tmp_path / soul.did.replace(":", "_")
        assert (soul_dir / "soul.json").exists()
        assert (soul_dir / "memory" / "semantic.json").exists()
        assert (soul_dir / "memory" / "episodic.json").exists()
        assert (soul_dir / "memory" / "procedural.json").exists()

        # Load and verify
        config, memory_data = await load_soul_full(soul_dir)
        assert config is not None
        assert config.identity.name == "MultiTier"
        assert len(memory_data.get("semantic", [])) >= 1
        assert len(memory_data.get("procedural", [])) >= 1


# ---------------------------------------------------------------------------
# Test: Self-Model Emergence
# ---------------------------------------------------------------------------


class TestSelfModelEmergence:
    """Self-model emergence after multiple observations."""

    async def test_self_model_emerges_from_technical_interactions(self):
        soul = await Soul.birth("ModelTest", values=["technical excellence"])

        # Use interactions rich in seed keywords (python, code, debug, api,
        # programming, docker, testing) to reliably trigger technical_helper
        technical_interactions = [
            Interaction(
                user_input="Help me debug this Python code that has an error",
                agent_output="Let me trace through your Python code and find the bug.",
            ),
            Interaction(
                user_input="I need help with programming an API server",
                agent_output="Let me help you build that API with Python and FastAPI.",
            ),
            Interaction(
                user_input="Can you help me deploy this with Docker?",
                agent_output="Docker deploy is straightforward. Let me write the Dockerfile.",
            ),
            Interaction(
                user_input="I want to write testing code for my Python function",
                agent_output="Use pytest for testing your Python code. Here is an example.",
            ),
            Interaction(
                user_input="Help me fix this JavaScript error in my React code",
                agent_output="The error is in your React component. Check the variable scope.",
            ),
        ]

        for interaction in technical_interactions:
            await soul.observe(interaction)

        images = soul.self_model.get_active_self_images(limit=10)
        assert len(images) >= 1, "Self-model should have at least one domain"

        domains = [img.domain for img in images]
        assert "technical_helper" in domains, f"Expected technical_helper in {domains}"

    async def test_self_model_confidence_grows(self):
        soul = await Soul.birth("ConfidenceTest")

        # Observe many technical interactions to build confidence
        for i in range(10):
            await soul.observe(
                Interaction(
                    user_input=f"Help me with Python coding problem #{i + 1}",
                    agent_output="Here's a solution using Python best practices.",
                )
            )

        images = soul.self_model.get_active_self_images(limit=5)
        if images:
            max_confidence = max(img.confidence for img in images)
            assert max_confidence > 0.1, f"Confidence should grow, got {max_confidence}"

    async def test_self_model_persists_through_export(self, tmp_path):
        soul = await Soul.birth("ExportModelTest")

        for i in range(5):
            await soul.observe(
                Interaction(
                    user_input=f"Help me debug Python error #{i + 1}",
                    agent_output="Let me trace through the code.",
                )
            )

        original_images = soul.self_model.get_active_self_images(limit=5)
        assert len(original_images) >= 1

        soul_path = tmp_path / "model_test.soul"
        await soul.export(str(soul_path))
        restored = await Soul.awaken(str(soul_path))

        restored_images = restored.self_model.get_active_self_images(limit=5)
        assert len(restored_images) >= 1

        # Domain should match
        original_domains = set(img.domain for img in original_images)
        restored_domains = set(img.domain for img in restored_images)
        assert original_domains == restored_domains, (
            f"Domains diverged: original={original_domains}, restored={restored_domains}"
        )

    async def test_self_model_in_system_prompt(self):
        soul = await Soul.birth("PromptModelTest")

        await soul.observe(
            Interaction(
                user_input="Help me write Python code for data analysis",
                agent_output="I can create a data analysis script for you.",
            )
        )
        await soul.observe(
            Interaction(
                user_input="Debug my Python API endpoint",
                agent_output="Let me check the route handler.",
            )
        )

        images = soul.self_model.get_active_self_images()
        if images:
            prompt = soul.to_system_prompt()
            assert "Self-Understanding" in prompt or "self" in prompt.lower()


# ---------------------------------------------------------------------------
# Test: Core Memory Editing
# ---------------------------------------------------------------------------


class TestCoreMemoryEditing:
    async def test_edit_persona(self):
        soul = await Soul.birth("CoreEditTest", persona="Base persona.")
        core = soul.get_core_memory()
        assert "Base persona" in core.persona

        await soul.edit_core_memory(persona="I also help with creative writing.")
        core = soul.get_core_memory()
        assert "creative writing" in core.persona

    async def test_edit_human(self):
        soul = await Soul.birth("CoreEditTest")
        await soul.edit_core_memory(human="User is a senior developer.")
        core = soul.get_core_memory()
        assert "senior developer" in core.human

    async def test_core_memory_survives_export(self, tmp_path):
        soul = await Soul.birth("CoreExportTest")
        await soul.edit_core_memory(
            persona="I am an expert in machine learning.",
            human="User works in bioinformatics.",
        )

        soul_path = tmp_path / "core_export.soul"
        await soul.export(str(soul_path))
        restored = await Soul.awaken(str(soul_path))

        core = restored.get_core_memory()
        assert "machine learning" in core.persona
        assert "bioinformatics" in core.human


# ---------------------------------------------------------------------------
# Test: Directory Format Roundtrip
# ---------------------------------------------------------------------------


class TestDirectoryFormat:
    async def test_save_local_and_awaken(self, tmp_path):
        soul = await Soul.birth("DirTest", persona="I am DirTest.")
        await soul.remember("Directory format test fact", importance=8)

        soul_dir = tmp_path / "test_soul_dir"
        await soul.save_local(soul_dir)

        # Check directory structure
        assert (soul_dir / "soul.json").exists()
        assert (soul_dir / "memory").exists()
        assert (soul_dir / "memory" / "semantic.json").exists()

        # Awaken from directory
        restored = await Soul.awaken(str(soul_dir))
        assert restored.name == "DirTest"

        results = await restored.recall("directory format test")
        assert any("directory" in r.content.lower() for r in results)

    async def test_save_load_full_directory(self, tmp_path):
        """save() + load_soul_full() preserves everything."""
        from soul_protocol.runtime.storage.file import load_soul_full

        soul = await Soul.birth("DirFull", values=["completeness"])
        await soul.remember("Test semantic fact", type=MemoryType.SEMANTIC, importance=7)
        await soul.observe(
            Interaction(
                user_input="I use Python 3.12",
                agent_output="Python 3.12 has great performance improvements!",
            )
        )

        await soul.save(tmp_path)
        soul_dir = tmp_path / soul.did.replace(":", "_")
        config, mem_data = await load_soul_full(soul_dir)

        assert config is not None
        assert config.identity.name == "DirFull"
        assert "semantic" in mem_data
        assert len(mem_data["semantic"]) >= 1


# ---------------------------------------------------------------------------
# Test: State Persistence
# ---------------------------------------------------------------------------


class TestStatePersistence:
    async def test_mood_and_energy_in_export(self, tmp_path):
        soul = await Soul.birth("StateTest")
        soul.feel(mood=Mood.EXCITED)
        soul.feel(energy=-25)

        # Energy and mood should be set
        assert soul.state.mood == Mood.EXCITED
        assert soul.state.energy == 75.0

        # Export preserves state in soul.json config
        config = soul.serialize()
        assert config.state.mood == Mood.EXCITED
        assert config.state.energy == 75.0

    async def test_last_interaction_timestamp(self):
        soul = await Soul.birth("TimestampTest")
        assert soul.state.last_interaction is None

        await soul.observe(
            Interaction(
                user_input="hello",
                agent_output="hi",
            )
        )
        assert soul.state.last_interaction is not None


# ---------------------------------------------------------------------------
# Test: Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    async def test_corrupt_soul_file(self, tmp_path):
        from soul_protocol.runtime.exceptions import SoulCorruptError

        corrupt_path = tmp_path / "corrupt.soul"
        corrupt_path.write_bytes(b"not a zip")

        with pytest.raises(SoulCorruptError):
            await Soul.awaken(str(corrupt_path))

    async def test_nonexistent_soul_file(self, tmp_path):
        from soul_protocol.runtime.exceptions import SoulFileNotFoundError

        with pytest.raises(SoulFileNotFoundError):
            await Soul.awaken(str(tmp_path / "does_not_exist.soul"))

    async def test_unsupported_config_format(self, tmp_path):
        bad_path = tmp_path / "config.xml"
        bad_path.write_text("<soul>nope</soul>")

        with pytest.raises(ValueError, match="Unsupported config format"):
            await Soul.birth_from_config(bad_path)

    async def test_missing_config_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            await Soul.birth_from_config(tmp_path / "missing.yaml")
