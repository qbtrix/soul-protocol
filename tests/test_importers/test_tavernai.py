# test_tavernai.py — Tests for TavernAI Character Card V2 importer/exporter
# Created: 2026-03-23 — 25+ tests covering from_json, from_png, to_character_card,
#   round-trip, minimal card, full card, invalid data, PNG embedding/extraction.

from __future__ import annotations

from pathlib import Path

import pytest


def _make_card_v2(
    name: str = "Aria",
    description: str = "A curious companion.",
    personality: str = "Friendly and thoughtful.",
    scenario: str = "",
    first_mes: str = "",
    mes_example: str = "",
    tags: list[str] | None = None,
    creator: str = "",
    creator_notes: str = "",
    character_version: str = "1.0",
    extensions: dict | None = None,
) -> dict:
    """Helper to build a valid Character Card V2 dict."""
    return {
        "spec": "chara_card_v2",
        "data": {
            "name": name,
            "description": description,
            "personality": personality,
            "scenario": scenario,
            "first_mes": first_mes,
            "mes_example": mes_example,
            "tags": tags or [],
            "creator": creator,
            "creator_notes": creator_notes,
            "character_version": character_version,
            "extensions": extensions or {},
        },
    }


@pytest.fixture
def full_card() -> dict:
    """A fully populated Character Card V2."""
    return _make_card_v2(
        name="Luna",
        description="A mysterious oracle who sees futures.",
        personality="Enigmatic, wise, occasionally playful.",
        scenario="You meet Luna at a crossroads under a crescent moon.",
        first_mes="*Luna tilts her head* I've been expecting you.",
        mes_example="<START>\n{{user}}: What do you see?\n{{char}}: Possibility.",
        tags=["oracle", "mystical", "wise"],
        creator="MoonForge",
        creator_notes="Designed for philosophical conversations.",
        character_version="2.1",
        extensions={"depth_prompt": "Think deeply before responding."},
    )


@pytest.fixture
def minimal_card() -> dict:
    """The minimum valid Character Card V2."""
    return _make_card_v2(name="Bare", description="", personality="")


# ============ from_json tests ============


@pytest.mark.asyncio
async def test_from_json_full(full_card: dict):
    """Import a fully populated Character Card V2."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)

    assert soul.name == "Luna"


@pytest.mark.asyncio
async def test_from_json_persona_mapping(full_card: dict):
    """Description + personality should become core memory persona."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)
    core = soul.get_core_memory()

    assert "mysterious oracle" in core.persona
    assert "Enigmatic" in core.persona


@pytest.mark.asyncio
async def test_from_json_first_mes_as_procedural(full_card: dict):
    """first_mes should be stored as procedural memory."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)
    procedural = soul._memory._procedural.entries()

    greeting_mems = [m for m in procedural if "Default greeting" in m.content]
    assert len(greeting_mems) >= 1
    assert "expecting you" in greeting_mems[0].content


@pytest.mark.asyncio
async def test_from_json_scenario_as_semantic(full_card: dict):
    """Scenario should be stored as semantic memory."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)
    semantic = soul._memory._semantic.facts()

    scenario_mems = [m for m in semantic if "scenario" in m.content.lower()]
    assert len(scenario_mems) >= 1


@pytest.mark.asyncio
async def test_from_json_mes_example_as_procedural(full_card: dict):
    """mes_example should be stored as procedural memory."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)
    procedural = soul._memory._procedural.entries()

    example_mems = [m for m in procedural if "Example conversations" in m.content]
    assert len(example_mems) >= 1


@pytest.mark.asyncio
async def test_from_json_tags_as_values(full_card: dict):
    """Tags should become core_values."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)

    assert "oracle" in soul.identity.core_values
    assert "mystical" in soul.identity.core_values


@pytest.mark.asyncio
async def test_from_json_creator_as_semantic(full_card: dict):
    """Creator should be stored as semantic memory."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)
    semantic = soul._memory._semantic.facts()

    creator_mems = [m for m in semantic if "MoonForge" in m.content]
    assert len(creator_mems) >= 1


@pytest.mark.asyncio
async def test_from_json_extensions_stored(full_card: dict):
    """Extensions should be stored as semantic memory."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)
    semantic = soul._memory._semantic.facts()

    ext_mems = [m for m in semantic if "extensions" in m.content.lower()]
    assert len(ext_mems) >= 1


@pytest.mark.asyncio
async def test_from_json_minimal(minimal_card: dict):
    """Import a minimal Character Card V2 with just a name."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(minimal_card)
    assert soul.name == "Bare"


@pytest.mark.asyncio
async def test_from_json_missing_spec():
    """Raise ValueError for missing spec field."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    with pytest.raises(ValueError, match="Not a Character Card V2"):
        await TavernAIImporter.from_json({"data": {"name": "Bad"}})


@pytest.mark.asyncio
async def test_from_json_wrong_spec():
    """Raise ValueError for wrong spec value."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    with pytest.raises(ValueError, match="Not a Character Card V2"):
        await TavernAIImporter.from_json(
            {
                "spec": "chara_card_v1",
                "data": {"name": "Old"},
            }
        )


@pytest.mark.asyncio
async def test_from_json_missing_data():
    """Raise ValueError when 'data' object is missing."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    with pytest.raises(ValueError, match="missing 'data' object"):
        await TavernAIImporter.from_json({"spec": "chara_card_v2"})


@pytest.mark.asyncio
async def test_from_json_missing_name():
    """Raise ValueError when name is missing from data."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    with pytest.raises(ValueError, match="missing 'name' field"):
        await TavernAIImporter.from_json(
            {
                "spec": "chara_card_v2",
                "data": {"description": "No name"},
            }
        )


@pytest.mark.asyncio
async def test_from_json_description_only():
    """Card with description but no personality should still work."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    card = _make_card_v2(name="DescOnly", description="I describe things.", personality="")
    soul = await TavernAIImporter.from_json(card)

    core = soul.get_core_memory()
    assert "describe things" in core.persona


@pytest.mark.asyncio
async def test_from_json_personality_only():
    """Card with personality but no description should still work."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    card = _make_card_v2(name="PersOnly", description="", personality="Bold and brave.")
    soul = await TavernAIImporter.from_json(card)

    core = soul.get_core_memory()
    assert "Bold and brave" in core.persona


# ============ to_character_card tests ============


@pytest.mark.asyncio
async def test_to_character_card_structure():
    """Exported card should have correct V2 structure."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="Exporter", persona="I export things.")
    card = await TavernAIImporter.to_character_card(soul)

    assert card["spec"] == "chara_card_v2"
    assert "data" in card
    assert card["data"]["name"] == "Exporter"


@pytest.mark.asyncio
async def test_to_character_card_persona_as_description():
    """Core memory persona should become the description field."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="DescExport", persona="I am the description.")
    card = await TavernAIImporter.to_character_card(soul)

    assert "I am the description" in card["data"]["description"]


@pytest.mark.asyncio
async def test_to_character_card_values_as_tags():
    """Core values should become tags."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="Tagged", values=["brave", "kind"])
    card = await TavernAIImporter.to_character_card(soul)

    assert "brave" in card["data"]["tags"]
    assert "kind" in card["data"]["tags"]


@pytest.mark.asyncio
async def test_to_character_card_archetype_as_notes():
    """Archetype should become creator_notes."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="ArchExport", archetype="The Sage")
    card = await TavernAIImporter.to_character_card(soul)

    assert card["data"]["creator_notes"] == "The Sage"


# ============ Round-trip tests ============


@pytest.mark.asyncio
async def test_round_trip_json(full_card: dict):
    """Import from JSON, export back, verify key fields preserved."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)
    card = await TavernAIImporter.to_character_card(soul)

    assert card["data"]["name"] == "Luna"
    assert card["spec"] == "chara_card_v2"
    # Persona should contain the original description
    assert "mysterious oracle" in card["data"]["description"]


@pytest.mark.asyncio
async def test_round_trip_preserves_first_mes(full_card: dict):
    """Round-trip should preserve first_mes content."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)
    card = await TavernAIImporter.to_character_card(soul)

    assert "expecting you" in card["data"]["first_mes"]


@pytest.mark.asyncio
async def test_round_trip_preserves_scenario(full_card: dict):
    """Round-trip should preserve scenario content."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    soul = await TavernAIImporter.from_json(full_card)
    card = await TavernAIImporter.to_character_card(soul)

    assert "crossroads" in card["data"]["scenario"]


# ============ PNG tests ============


@pytest.mark.asyncio
async def test_from_png_extraction(tmp_path: Path):
    """Extract Character Card from a PNG file with embedded tEXt chunk."""
    from soul_protocol.runtime.importers.tavernai import (
        TavernAIImporter,
        _build_png_with_chara,
        _minimal_png,
    )

    card = _make_card_v2(name="PNGTest", description="Embedded in an image.")
    png_bytes = _build_png_with_chara(_minimal_png(), card)

    png_path = tmp_path / "test.png"
    png_path.write_bytes(png_bytes)

    soul = await TavernAIImporter.from_png(png_path)
    assert soul.name == "PNGTest"


@pytest.mark.asyncio
async def test_from_png_not_found(tmp_path: Path):
    """Raise FileNotFoundError for nonexistent PNG."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    with pytest.raises(FileNotFoundError):
        await TavernAIImporter.from_png(tmp_path / "nonexistent.png")


@pytest.mark.asyncio
async def test_from_png_invalid_file(tmp_path: Path):
    """Raise ValueError for non-PNG file."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter

    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png file")

    with pytest.raises(ValueError, match="Not a valid PNG"):
        await TavernAIImporter.from_png(bad)


@pytest.mark.asyncio
async def test_from_png_no_chara_chunk(tmp_path: Path):
    """Raise ValueError for PNG without character data."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter, _minimal_png

    # Minimal PNG without any tEXt chunk
    png_path = tmp_path / "empty.png"
    png_path.write_bytes(_minimal_png())

    with pytest.raises(ValueError, match="No 'chara'"):
        await TavernAIImporter.from_png(png_path)


@pytest.mark.asyncio
async def test_to_png_creates_valid_file(tmp_path: Path):
    """Export to PNG should create a valid PNG with embedded card."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter, _extract_json_from_png
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="PNGExport", persona="Testing PNG export.")
    png_path = tmp_path / "output.png"
    await TavernAIImporter.to_png(soul, png_path)

    assert png_path.exists()
    # Verify PNG signature
    data = png_path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

    # Verify embedded card
    card = _extract_json_from_png(data)
    assert card["data"]["name"] == "PNGExport"


@pytest.mark.asyncio
async def test_round_trip_png(tmp_path: Path):
    """Round-trip: Soul -> PNG -> Soul should preserve name and persona."""
    from soul_protocol.runtime.importers.tavernai import TavernAIImporter
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth(name="RoundPNG", persona="I survive round trips.")
    png_path = tmp_path / "round.png"
    await TavernAIImporter.to_png(soul, png_path)

    soul2 = await TavernAIImporter.from_png(png_path)
    assert soul2.name == "RoundPNG"
    assert "round trips" in soul2.get_core_memory().persona
