# test_soul_templates.py — Tests for soul templates and batch spawning (#96).
# Created: feat/memory-visibility-templates — Validates SoulTemplate model,
#   SoulFactory.from_template(), batch_spawn() with variance, name patterns,
#   overrides, and skill registration.

from __future__ import annotations

import pytest

from soul_protocol.runtime.templates import SoulFactory
from soul_protocol.spec.template import SoulTemplate

# ---------------------------------------------------------------------------
# SoulTemplate model
# ---------------------------------------------------------------------------


class TestSoulTemplate:
    def test_minimal_template(self):
        t = SoulTemplate(name="test")
        assert t.name == "test"
        assert t.archetype == "assistant"
        assert t.personality == {}
        assert t.core_memories == []
        assert t.skills == []
        assert t.metadata == {}
        assert t.personality_variance == 0.1
        assert t.name_prefix == ""

    def test_full_template(self):
        t = SoulTemplate(
            name="Explorer",
            archetype="curious researcher",
            personality={"openness": 0.9, "neuroticism": 0.2},
            core_memories=["I love learning"],
            skills=["research", "analysis"],
            metadata={"version": "1.0"},
            personality_variance=0.2,
            name_prefix="Exp-",
        )
        assert t.name == "Explorer"
        assert t.personality["openness"] == 0.9
        assert len(t.core_memories) == 1
        assert len(t.skills) == 2
        assert t.personality_variance == 0.2
        assert t.name_prefix == "Exp-"

    def test_variance_bounds(self):
        """personality_variance must be 0.0 to 0.5."""
        t = SoulTemplate(name="t", personality_variance=0.0)
        assert t.personality_variance == 0.0
        t = SoulTemplate(name="t", personality_variance=0.5)
        assert t.personality_variance == 0.5

    def test_variance_too_high(self):
        with pytest.raises(Exception):  # Pydantic validation error
            SoulTemplate(name="t", personality_variance=0.6)

    def test_variance_negative(self):
        with pytest.raises(Exception):
            SoulTemplate(name="t", personality_variance=-0.1)

    def test_serialization_roundtrip(self):
        t = SoulTemplate(
            name="Test",
            personality={"openness": 0.8},
            core_memories=["memory1"],
        )
        data = t.model_dump()
        restored = SoulTemplate.model_validate(data)
        assert restored.name == "Test"
        assert restored.personality["openness"] == 0.8
        assert restored.core_memories == ["memory1"]

    def test_json_roundtrip(self):
        t = SoulTemplate(name="Json", skills=["coding"])
        json_str = t.model_dump_json()
        restored = SoulTemplate.model_validate_json(json_str)
        assert restored.name == "Json"
        assert restored.skills == ["coding"]


# ---------------------------------------------------------------------------
# SoulFactory.from_template()
# ---------------------------------------------------------------------------


class TestSoulFactoryFromTemplate:
    @pytest.mark.asyncio
    async def test_basic_creation(self):
        t = SoulTemplate(name="TestBot", archetype="helper")
        soul = await SoulFactory.from_template(t)
        assert soul.name == "TestBot"
        assert soul.archetype == "helper"

    @pytest.mark.asyncio
    async def test_name_override(self):
        t = SoulTemplate(name="Template")
        soul = await SoulFactory.from_template(t, name="CustomName")
        assert soul.name == "CustomName"

    @pytest.mark.asyncio
    async def test_personality_applied(self):
        t = SoulTemplate(
            name="Curious",
            personality={"openness": 0.9, "neuroticism": 0.1},
        )
        soul = await SoulFactory.from_template(t)
        assert soul.dna.personality.openness == 0.9
        assert soul.dna.personality.neuroticism == 0.1

    @pytest.mark.asyncio
    async def test_core_memories_stored(self):
        t = SoulTemplate(
            name="MemBot",
            core_memories=["I am a helper", "I value honesty"],
        )
        soul = await SoulFactory.from_template(t)
        results = await soul.recall("helper honesty")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_skills_registered(self):
        t = SoulTemplate(
            name="SkillBot",
            skills=["coding", "analysis"],
        )
        soul = await SoulFactory.from_template(t)
        assert soul.skills.get("coding") is not None
        assert soul.skills.get("analysis") is not None

    @pytest.mark.asyncio
    async def test_unique_did(self):
        t = SoulTemplate(name="UniqueTest")
        soul1 = await SoulFactory.from_template(t)
        soul2 = await SoulFactory.from_template(t)
        assert soul1.did != soul2.did

    @pytest.mark.asyncio
    async def test_overrides(self):
        """Keyword overrides take precedence over template values."""
        t = SoulTemplate(name="Base", archetype="helper")
        soul = await SoulFactory.from_template(t, archetype="researcher")
        assert soul.archetype == "researcher"

    @pytest.mark.asyncio
    async def test_empty_personality(self):
        """Empty personality dict uses defaults (0.5 for all traits)."""
        t = SoulTemplate(name="Default")
        soul = await SoulFactory.from_template(t)
        assert soul.dna.personality.openness == 0.5


# ---------------------------------------------------------------------------
# SoulFactory.batch_spawn()
# ---------------------------------------------------------------------------


class TestSoulFactoryBatchSpawn:
    @pytest.mark.asyncio
    async def test_correct_count(self):
        t = SoulTemplate(name="Worker")
        souls = await SoulFactory.batch_spawn(t, count=5, rng_seed=42)
        assert len(souls) == 5

    @pytest.mark.asyncio
    async def test_unique_names(self):
        t = SoulTemplate(name="Agent", name_prefix="A-")
        souls = await SoulFactory.batch_spawn(t, count=3, rng_seed=42)
        names = [s.name for s in souls]
        assert names == ["A-001", "A-002", "A-003"]

    @pytest.mark.asyncio
    async def test_name_pattern_default(self):
        t = SoulTemplate(name="Bot")
        souls = await SoulFactory.batch_spawn(t, count=2, rng_seed=42)
        # Default prefix is template.name when name_prefix is empty
        assert souls[0].name == "Bot001"
        assert souls[1].name == "Bot002"

    @pytest.mark.asyncio
    async def test_unique_dids(self):
        t = SoulTemplate(name="Clone")
        souls = await SoulFactory.batch_spawn(t, count=5, rng_seed=42)
        dids = [s.did for s in souls]
        assert len(set(dids)) == 5

    @pytest.mark.asyncio
    async def test_personality_variance(self):
        t = SoulTemplate(
            name="Varied",
            personality={"openness": 0.5},
            personality_variance=0.3,
        )
        souls = await SoulFactory.batch_spawn(t, count=10, rng_seed=42)
        openness_values = [s.dna.personality.openness for s in souls]
        # With variance=0.3, values should differ but stay in [0.2, 0.8] range
        assert not all(v == 0.5 for v in openness_values)
        assert all(0.0 <= v <= 1.0 for v in openness_values)

    @pytest.mark.asyncio
    async def test_zero_variance_exact_clones(self):
        t = SoulTemplate(
            name="Clone",
            personality={"openness": 0.7, "neuroticism": 0.3},
            personality_variance=0.0,
        )
        souls = await SoulFactory.batch_spawn(t, count=3, rng_seed=42)
        for soul in souls:
            assert soul.dna.personality.openness == 0.7
            assert soul.dna.personality.neuroticism == 0.3

    @pytest.mark.asyncio
    async def test_reproducible_with_seed(self):
        t = SoulTemplate(
            name="Seeded",
            personality={"openness": 0.5},
            personality_variance=0.2,
        )
        batch1 = await SoulFactory.batch_spawn(t, count=5, rng_seed=123)
        batch2 = await SoulFactory.batch_spawn(t, count=5, rng_seed=123)
        for s1, s2 in zip(batch1, batch2):
            assert s1.dna.personality.openness == s2.dna.personality.openness

    @pytest.mark.asyncio
    async def test_core_memories_in_batch(self):
        t = SoulTemplate(
            name="MemWorker",
            core_memories=["I serve the collective"],
        )
        souls = await SoulFactory.batch_spawn(t, count=3, rng_seed=42)
        for soul in souls:
            results = await soul.recall("collective")
            assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_skills_in_batch(self):
        t = SoulTemplate(
            name="SkillWorker",
            skills=["navigation"],
        )
        souls = await SoulFactory.batch_spawn(t, count=2, rng_seed=42)
        for soul in souls:
            assert soul.skills.get("navigation") is not None

    @pytest.mark.asyncio
    async def test_batch_zero_count(self):
        t = SoulTemplate(name="Empty")
        souls = await SoulFactory.batch_spawn(t, count=0, rng_seed=42)
        assert souls == []

    @pytest.mark.asyncio
    async def test_custom_name_pattern(self):
        t = SoulTemplate(name="Bot", name_prefix="X-")
        souls = await SoulFactory.batch_spawn(
            t, count=2, name_pattern="{name}-v{index}", rng_seed=42
        )
        assert souls[0].name == "Bot-v1"
        assert souls[1].name == "Bot-v2"

    @pytest.mark.asyncio
    async def test_variance_clamped_to_bounds(self):
        """Personality values should stay in [0.0, 1.0] even with high base + variance."""
        t = SoulTemplate(
            name="Edge",
            personality={"openness": 0.95},
            personality_variance=0.5,
        )
        souls = await SoulFactory.batch_spawn(t, count=20, rng_seed=42)
        for soul in souls:
            assert 0.0 <= soul.dna.personality.openness <= 1.0


# ---------------------------------------------------------------------------
# SoulFactory instance methods
# ---------------------------------------------------------------------------


class TestSoulFactoryRegistry:
    def test_register_and_list(self):
        factory = SoulFactory()
        t1 = SoulTemplate(name="Alpha")
        t2 = SoulTemplate(name="Beta")
        factory.register(t1)
        factory.register(t2)
        assert set(factory.list_templates()) == {"Alpha", "Beta"}

    def test_list_empty(self):
        factory = SoulFactory()
        assert factory.list_templates() == []


# ---------------------------------------------------------------------------
# Public API exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_soul_template_from_spec(self):
        from soul_protocol.spec import SoulTemplate as SpecTemplate

        t = SpecTemplate(name="test")
        assert t.name == "test"

    def test_soul_factory_from_package(self):
        from soul_protocol import SoulFactory as PkgFactory

        assert PkgFactory is not None

    def test_soul_template_from_package(self):
        from soul_protocol import SoulTemplate as PkgTemplate

        t = PkgTemplate(name="pkg")
        assert t.name == "pkg"

    def test_memory_visibility_from_package(self):
        from soul_protocol import MemoryVisibility as PkgVis

        assert PkgVis.PUBLIC == "public"
