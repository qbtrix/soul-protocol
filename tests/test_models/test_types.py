# test_types.py — Tests for Pydantic data models in soul_protocol.types.
# Created: 2026-02-22 — Covers Identity defaults, Personality bounds validation,
# SoulConfig JSON roundtrip, MemoryEntry defaults, Mood enum, EvolutionMode enum.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from soul_protocol.types import (
    EvolutionMode,
    Identity,
    MemoryEntry,
    MemoryType,
    Mood,
    Personality,
    SoulConfig,
)


def test_identity_defaults():
    """Identity with only 'name' uses correct defaults."""
    ident = Identity(name="Aria")

    assert ident.name == "Aria"
    assert ident.did == ""
    assert ident.archetype == ""
    assert ident.bonded_to is None
    assert ident.origin_story == ""
    assert ident.prime_directive == ""
    assert ident.core_values == []
    assert ident.born is not None


def test_personality_bounds():
    """Personality traits are validated within 0.0-1.0 range."""
    # Valid at boundaries
    p = Personality(openness=0.0, conscientiousness=1.0)
    assert p.openness == 0.0
    assert p.conscientiousness == 1.0

    # Defaults are all 0.5
    p_default = Personality()
    assert p_default.openness == 0.5
    assert p_default.extraversion == 0.5

    # Value above 1.0 should raise
    with pytest.raises(ValidationError):
        Personality(openness=1.5)

    # Value below 0.0 should raise
    with pytest.raises(ValidationError):
        Personality(neuroticism=-0.1)


def test_soul_config_serialization():
    """SoulConfig model_dump_json -> model_validate_json roundtrip."""
    config = SoulConfig(
        identity=Identity(name="Aria", archetype="Creator"),
    )

    json_str = config.model_dump_json()
    restored = SoulConfig.model_validate_json(json_str)

    assert restored.identity.name == "Aria"
    assert restored.identity.archetype == "Creator"
    assert restored.version == "1.0.0"
    assert restored.state.mood == Mood.NEUTRAL
    assert restored.dna.personality.openness == 0.5


def test_memory_entry_defaults():
    """MemoryEntry uses correct defaults for optional fields."""
    entry = MemoryEntry(type=MemoryType.SEMANTIC, content="User likes coffee")

    assert entry.id == ""
    assert entry.type == MemoryType.SEMANTIC
    assert entry.content == "User likes coffee"
    assert entry.importance == 5
    assert entry.emotion is None
    assert entry.confidence == 1.0
    assert entry.entities == []
    assert entry.created_at is not None
    assert entry.last_accessed is None
    assert entry.access_count == 0


def test_mood_enum_values():
    """Mood enum contains all expected values."""
    expected = {
        "neutral",
        "curious",
        "focused",
        "tired",
        "excited",
        "contemplative",
        "satisfied",
        "concerned",
    }
    actual = {m.value for m in Mood}
    assert actual == expected


def test_evolution_mode_enum():
    """EvolutionMode enum contains disabled, supervised, autonomous."""
    assert EvolutionMode.DISABLED.value == "disabled"
    assert EvolutionMode.SUPERVISED.value == "supervised"
    assert EvolutionMode.AUTONOMOUS.value == "autonomous"
    assert len(EvolutionMode) == 3
