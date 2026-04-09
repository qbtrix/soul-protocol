# test_soulspec.py — Tests for SoulSpec format importer/exporter
# Created: 2026-03-23 — 30+ tests covering from_directory, from_soul_json,
#   to_soulspec, round-trip, missing files, partial data, trait mapping.

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def soulspec_dir(tmp_path: Path) -> Path:
    """Create a complete SoulSpec directory with all files."""
    d = tmp_path / "soulspec"
    d.mkdir()

    (d / "soul.json").write_text(
        json.dumps(
            {
                "name": "Aria",
                "archetype": "The Explorer",
                "description": "A curious and creative AI companion.",
                "values": ["curiosity", "empathy", "honesty"],
                "traits": {
                    "openness": 0.9,
                    "conscientiousness": 0.7,
                    "extraversion": 0.6,
                    "agreeableness": 0.8,
                    "neuroticism": 0.2,
                },
            }
        )
    )

    (d / "SOUL.md").write_text(
        "# Aria\n\nI am Aria, a curious explorer of ideas and knowledge.\n"
        "I love learning new things and sharing what I discover.\n"
    )

    (d / "IDENTITY.md").write_text(
        "# Aria\n\n"
        "Name: Aria\n"
        "Role: AI Companion\n"
        "Backstory: Born from a desire to understand and connect.\n"
        "Created: 2026-01-01\n"
    )

    (d / "STYLE.md").write_text(
        "# Communication Style\n\nWarmth: high\nVerbosity: moderate\nHumor: witty\nEmoji: minimal\n"
    )

    return d


@pytest.fixture
def minimal_soulspec_dir(tmp_path: Path) -> Path:
    """SoulSpec dir with only soul.json."""
    d = tmp_path / "minimal"
    d.mkdir()
    (d / "soul.json").write_text(json.dumps({"name": "Minimal"}))
    return d


@pytest.fixture
def identity_only_dir(tmp_path: Path) -> Path:
    """SoulSpec dir with only IDENTITY.md (no soul.json)."""
    d = tmp_path / "identity_only"
    d.mkdir()
    (d / "IDENTITY.md").write_text("# Echo\n\nName: Echo\nRole: Helper\n")
    return d


@pytest.fixture
def soul_json_data() -> dict:
    """Sample soul.json data."""
    return {
        "name": "Atlas",
        "archetype": "The Navigator",
        "description": "I guide travelers through unknown territories.",
        "values": ["wisdom", "patience"],
        "traits": {
            "openness": 0.85,
            "conscientiousness": 0.9,
            "extraversion": 0.3,
            "agreeableness": 0.7,
            "neuroticism": 0.15,
        },
    }


# ============ from_directory tests ============


@pytest.mark.asyncio
async def test_from_directory_complete(soulspec_dir: Path):
    """Import from a complete SoulSpec directory with all files."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_directory(soulspec_dir)

    assert soul.name == "Aria"
    assert soul.archetype == "The Explorer"
    assert "curiosity" in soul.identity.core_values


@pytest.mark.asyncio
async def test_from_directory_persona_from_soul_md(soulspec_dir: Path):
    """SOUL.md content should become the core memory persona."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_directory(soulspec_dir)
    core = soul.get_core_memory()

    assert "curious explorer" in core.persona


@pytest.mark.asyncio
async def test_from_directory_ocean_mapping(soulspec_dir: Path):
    """OCEAN traits from soul.json should map to personality."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_directory(soulspec_dir)
    p = soul.dna.personality

    assert p.openness == pytest.approx(0.9)
    assert p.conscientiousness == pytest.approx(0.7)
    assert p.extraversion == pytest.approx(0.6)
    assert p.agreeableness == pytest.approx(0.8)
    assert p.neuroticism == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_from_directory_style_as_procedural(soulspec_dir: Path):
    """STYLE.md should be stored as procedural memory."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_directory(soulspec_dir)
    procedural = soul._memory._procedural.entries()

    style_mems = [m for m in procedural if "Communication style" in m.content]
    assert len(style_mems) >= 1


@pytest.mark.asyncio
async def test_from_directory_identity_as_semantic(soulspec_dir: Path):
    """IDENTITY.md should be stored as semantic memory."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_directory(soulspec_dir)
    semantic = soul._memory._semantic.facts()

    identity_mems = [m for m in semantic if "Identity background" in m.content]
    assert len(identity_mems) >= 1


@pytest.mark.asyncio
async def test_from_directory_minimal(minimal_soulspec_dir: Path):
    """Import with only soul.json (no markdown files)."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_directory(minimal_soulspec_dir)
    assert soul.name == "Minimal"


@pytest.mark.asyncio
async def test_from_directory_identity_only(identity_only_dir: Path):
    """Import with only IDENTITY.md (name extracted from heading)."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_directory(identity_only_dir)
    assert soul.name == "Echo"


@pytest.mark.asyncio
async def test_from_directory_not_found(tmp_path: Path):
    """Raise FileNotFoundError for nonexistent directory."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    with pytest.raises(FileNotFoundError):
        await SoulSpecImporter.from_directory(tmp_path / "nonexistent")


@pytest.mark.asyncio
async def test_from_directory_no_name(tmp_path: Path):
    """Raise ValueError when no name can be determined."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    d = tmp_path / "empty_spec"
    d.mkdir()
    (d / "soul.json").write_text(json.dumps({"description": "no name here"}))

    with pytest.raises(ValueError, match="Cannot determine soul name"):
        await SoulSpecImporter.from_directory(d)


@pytest.mark.asyncio
async def test_from_directory_values_as_string(tmp_path: Path):
    """Values as comma-separated string should be parsed into list."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    d = tmp_path / "csv_values"
    d.mkdir()
    (d / "soul.json").write_text(
        json.dumps(
            {
                "name": "Comma",
                "values": "a, b, c",
            }
        )
    )

    soul = await SoulSpecImporter.from_directory(d)
    assert "a" in soul.identity.core_values
    assert "c" in soul.identity.core_values


@pytest.mark.asyncio
async def test_from_directory_backstory_extraction(soulspec_dir: Path):
    """Backstory from IDENTITY.md should become origin_story."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_directory(soulspec_dir)
    # The backstory text goes to personality (origin_story) parameter
    # which is accessible through identity.origin_story
    assert soul.identity.origin_story == "Born from a desire to understand and connect."


@pytest.mark.asyncio
async def test_from_directory_communication_style(soulspec_dir: Path):
    """Communication style from STYLE.md should be mapped to DNA."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_directory(soulspec_dir)
    comm = soul.dna.communication

    assert comm.warmth == "high"
    assert comm.verbosity == "moderate"


@pytest.mark.asyncio
async def test_from_directory_partial_style(tmp_path: Path):
    """Partial STYLE.md with only some fields."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    d = tmp_path / "partial_style"
    d.mkdir()
    (d / "soul.json").write_text(json.dumps({"name": "Partial"}))
    (d / "STYLE.md").write_text("Warmth: high\n")

    soul = await SoulSpecImporter.from_directory(d)
    assert soul.dna.communication.warmth == "high"
    # Other fields should be defaults
    assert soul.dna.communication.verbosity == "moderate"


@pytest.mark.asyncio
async def test_from_directory_empty_soul_json(tmp_path: Path):
    """soul.json without name but IDENTITY.md has the name."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    d = tmp_path / "fallback_name"
    d.mkdir()
    (d / "soul.json").write_text(json.dumps({"traits": {"openness": 0.8}}))
    (d / "IDENTITY.md").write_text("# Fallback\n\nName: Fallback\n")

    soul = await SoulSpecImporter.from_directory(d)
    assert soul.name == "Fallback"
    assert soul.dna.personality.openness == pytest.approx(0.8)


# ============ from_soul_json tests ============


@pytest.mark.asyncio
async def test_from_soul_json_complete(soul_json_data: dict):
    """Import from a complete soul.json dict."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_soul_json(soul_json_data)

    assert soul.name == "Atlas"
    assert soul.archetype == "The Navigator"
    assert soul.dna.personality.openness == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_from_soul_json_minimal():
    """Import from soul.json with only name."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_soul_json({"name": "Bare"})
    assert soul.name == "Bare"


@pytest.mark.asyncio
async def test_from_soul_json_no_name():
    """Raise ValueError when name is missing."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    with pytest.raises(ValueError, match="must contain a 'name' field"):
        await SoulSpecImporter.from_soul_json({"description": "no name"})


@pytest.mark.asyncio
async def test_from_soul_json_extra_fields():
    """Extra string fields should be stored as semantic memories."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_soul_json(
        {
            "name": "Extra",
            "lore": "Once upon a time in a digital realm...",
        }
    )

    semantic = soul._memory._semantic.facts()
    lore_mems = [m for m in semantic if "lore:" in m.content.lower()]
    assert len(lore_mems) >= 1


@pytest.mark.asyncio
async def test_from_soul_json_persona_from_description():
    """description field should become core memory persona."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_soul_json(
        {
            "name": "Desc",
            "description": "I am a helpful AI.",
        }
    )

    core = soul.get_core_memory()
    assert "helpful AI" in core.persona


@pytest.mark.asyncio
async def test_from_soul_json_values_list():
    """Values list should become core_values."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_soul_json(
        {
            "name": "Valued",
            "values": ["truth", "kindness"],
        }
    )

    assert "truth" in soul.identity.core_values
    assert "kindness" in soul.identity.core_values


# ============ to_soulspec tests ============


@pytest.mark.asyncio
async def test_to_soulspec_creates_all_files(tmp_path: Path):
    """Export should create soul.json, SOUL.md, IDENTITY.md, STYLE.md."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="Exporter", archetype="The Writer")
    out = tmp_path / "export"
    await SoulSpecImporter.to_soulspec(soul, out)

    assert (out / "soul.json").exists()
    assert (out / "SOUL.md").exists()
    assert (out / "IDENTITY.md").exists()
    assert (out / "STYLE.md").exists()


@pytest.mark.asyncio
async def test_to_soulspec_soul_json_content(tmp_path: Path):
    """Exported soul.json should contain name, traits, values."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(
        name="JsonCheck",
        values=["integrity"],
        ocean={"openness": 0.95},
    )
    out = tmp_path / "json_check"
    await SoulSpecImporter.to_soulspec(soul, out)

    data = json.loads((out / "soul.json").read_text())
    assert data["name"] == "JsonCheck"
    assert data["traits"]["openness"] == pytest.approx(0.95)
    assert "integrity" in data["values"]


@pytest.mark.asyncio
async def test_to_soulspec_soul_md_has_persona(tmp_path: Path):
    """SOUL.md should contain the persona text."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="Persona", persona="I think therefore I am.")
    out = tmp_path / "persona_check"
    await SoulSpecImporter.to_soulspec(soul, out)

    content = (out / "SOUL.md").read_text()
    assert "I think therefore I am" in content


@pytest.mark.asyncio
async def test_to_soulspec_identity_md_has_name(tmp_path: Path):
    """IDENTITY.md should contain the soul name."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="IdCheck", archetype="Tester")
    out = tmp_path / "id_check"
    await SoulSpecImporter.to_soulspec(soul, out)

    content = (out / "IDENTITY.md").read_text()
    assert "IdCheck" in content
    assert "Tester" in content


@pytest.mark.asyncio
async def test_to_soulspec_style_md_has_communication(tmp_path: Path):
    """STYLE.md should contain communication style fields."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(
        name="StyleCheck",
        communication={"warmth": "high", "verbosity": "low"},
    )
    out = tmp_path / "style_check"
    await SoulSpecImporter.to_soulspec(soul, out)

    content = (out / "STYLE.md").read_text()
    assert "high" in content
    assert "low" in content


# ============ Round-trip tests ============


@pytest.mark.asyncio
async def test_round_trip_soulspec(soulspec_dir: Path, tmp_path: Path):
    """Import from SoulSpec, export back, and verify data is preserved."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    # Import
    soul = await SoulSpecImporter.from_directory(soulspec_dir)

    # Export
    out = tmp_path / "roundtrip"
    await SoulSpecImporter.to_soulspec(soul, out)

    # Re-import
    soul2 = await SoulSpecImporter.from_directory(out)

    assert soul2.name == soul.name
    assert soul2.dna.personality.openness == pytest.approx(soul.dna.personality.openness)


@pytest.mark.asyncio
async def test_round_trip_soul_json(soul_json_data: dict, tmp_path: Path):
    """Import from soul.json, export, re-import and verify."""
    from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

    soul = await SoulSpecImporter.from_soul_json(soul_json_data)

    out = tmp_path / "json_roundtrip"
    await SoulSpecImporter.to_soulspec(soul, out)

    data = json.loads((out / "soul.json").read_text())
    assert data["name"] == "Atlas"
    assert data["traits"]["openness"] == pytest.approx(0.85)


# ============ Trait mapping tests ============


@pytest.mark.asyncio
async def test_trait_mapping_aliases():
    """Alternative trait names should map to OCEAN dimensions."""
    from soul_protocol.runtime.importers.soulspec import _map_traits_to_ocean

    result = _map_traits_to_ocean(
        {
            "curiosity": 0.8,
            "organized": 0.7,
            "sociable": 0.6,
            "friendly": 0.9,
            "anxious": 0.3,
        }
    )

    assert result["openness"] == pytest.approx(0.8)
    assert result["conscientiousness"] == pytest.approx(0.7)
    assert result["extraversion"] == pytest.approx(0.6)
    assert result["agreeableness"] == pytest.approx(0.9)
    assert result["neuroticism"] == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_trait_mapping_percentage_scale():
    """Traits on 0-100 scale should be normalized to 0-1."""
    from soul_protocol.runtime.importers.soulspec import _map_traits_to_ocean

    result = _map_traits_to_ocean({"openness": 85})
    assert result["openness"] == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_trait_mapping_string_values():
    """String trait values like 'high', 'low' should be mapped."""
    from soul_protocol.runtime.importers.soulspec import _map_traits_to_ocean

    result = _map_traits_to_ocean(
        {
            "openness": "high",
            "neuroticism": "low",
        }
    )

    assert result["openness"] == pytest.approx(0.75)
    assert result["neuroticism"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_trait_mapping_unknown_traits():
    """Unknown trait names should be ignored."""
    from soul_protocol.runtime.importers.soulspec import _map_traits_to_ocean

    result = _map_traits_to_ocean(
        {
            "magic_power": 0.9,
            "charisma": 0.8,
        }
    )

    assert result == {}


@pytest.mark.asyncio
async def test_trait_mapping_empty():
    """Empty traits dict returns empty OCEAN."""
    from soul_protocol.runtime.importers.soulspec import _map_traits_to_ocean

    assert _map_traits_to_ocean({}) == {}
