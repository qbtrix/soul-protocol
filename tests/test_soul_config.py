# test_soul_config.py — Tests for flexible soul configuration at birth.
# Created: 2026-02-23 — Tests for Soul.birth() with custom OCEAN, communication,
#   biorhythms, and persona parameters. Tests for Soul.birth_from_config() with
#   YAML and JSON config files. Tests for CLI --config and OCEAN flag options.

from __future__ import annotations

import json

import pytest
import yaml

from soul_protocol.soul import Soul
from soul_protocol.types import LifecycleState, Mood

# ============ Soul.birth() with custom OCEAN ============


async def test_birth_with_full_ocean():
    """Soul.birth with all five OCEAN traits applies them to DNA."""
    soul = await Soul.birth(
        "Aria",
        ocean={
            "openness": 0.8,
            "conscientiousness": 0.9,
            "extraversion": 0.3,
            "agreeableness": 0.7,
            "neuroticism": 0.2,
        },
    )

    p = soul.dna.personality
    assert p.openness == pytest.approx(0.8)
    assert p.conscientiousness == pytest.approx(0.9)
    assert p.extraversion == pytest.approx(0.3)
    assert p.agreeableness == pytest.approx(0.7)
    assert p.neuroticism == pytest.approx(0.2)


async def test_birth_with_partial_ocean():
    """Partial OCEAN dict fills unspecified traits with 0.5 default."""
    soul = await Soul.birth(
        "Aria",
        ocean={"openness": 0.9, "neuroticism": 0.1},
    )

    p = soul.dna.personality
    assert p.openness == pytest.approx(0.9)
    assert p.neuroticism == pytest.approx(0.1)
    # Unspecified traits default to 0.5
    assert p.conscientiousness == pytest.approx(0.5)
    assert p.extraversion == pytest.approx(0.5)
    assert p.agreeableness == pytest.approx(0.5)


async def test_birth_without_ocean_uses_defaults():
    """Without ocean param, all personality traits default to 0.5."""
    soul = await Soul.birth("Aria")

    p = soul.dna.personality
    assert p.openness == pytest.approx(0.5)
    assert p.conscientiousness == pytest.approx(0.5)
    assert p.extraversion == pytest.approx(0.5)
    assert p.agreeableness == pytest.approx(0.5)
    assert p.neuroticism == pytest.approx(0.5)


# ============ Soul.birth() with custom communication style ============


async def test_birth_with_communication_style():
    """Soul.birth with communication dict applies style to DNA."""
    soul = await Soul.birth(
        "Aria",
        communication={
            "warmth": "high",
            "verbosity": "low",
            "humor_style": "dry",
            "emoji_usage": "minimal",
        },
    )

    c = soul.dna.communication
    assert c.warmth == "high"
    assert c.verbosity == "low"
    assert c.humor_style == "dry"
    assert c.emoji_usage == "minimal"


async def test_birth_with_partial_communication():
    """Partial communication dict keeps model defaults for unspecified fields."""
    soul = await Soul.birth(
        "Aria",
        communication={"warmth": "high"},
    )

    c = soul.dna.communication
    assert c.warmth == "high"
    # Unspecified fields keep model defaults
    assert c.verbosity == "moderate"
    assert c.humor_style == "none"
    assert c.emoji_usage == "none"


# ============ Soul.birth() with custom biorhythms ============


async def test_birth_with_biorhythms():
    """Soul.birth with biorhythms dict applies them to DNA."""
    soul = await Soul.birth(
        "Aria",
        biorhythms={
            "chronotype": "night_owl",
            "energy_regen_rate": 3.0,
        },
    )

    b = soul.dna.biorhythms
    assert b.chronotype == "night_owl"
    assert b.energy_regen_rate == pytest.approx(3.0)


# ============ Soul.birth() with persona ============


async def test_birth_with_persona():
    """Soul.birth with persona sets core memory persona text."""
    persona_text = "I am Aria, a precise and efficient coding assistant."
    soul = await Soul.birth("Aria", persona=persona_text)

    core = soul.get_core_memory()
    assert core.persona == persona_text


async def test_birth_persona_overrides_personality():
    """When both persona and personality are provided, persona wins for core memory."""
    soul = await Soul.birth(
        "Aria",
        personality="Origin story text",
        persona="I am Aria, the custom persona.",
    )

    core = soul.get_core_memory()
    assert core.persona == "I am Aria, the custom persona."


async def test_birth_personality_fallback():
    """When only personality is provided (no persona), it becomes core memory."""
    soul = await Soul.birth("Aria", personality="I am Aria from personality param.")

    core = soul.get_core_memory()
    assert core.persona == "I am Aria from personality param."


# ============ Soul.birth() with all custom params together ============


async def test_birth_with_all_custom_params():
    """Full customization: OCEAN + communication + biorhythms + persona + values."""
    soul = await Soul.birth(
        "Zara",
        archetype="The Night Coder",
        values=["precision", "clarity"],
        ocean={"openness": 0.8, "conscientiousness": 0.9, "neuroticism": 0.2},
        communication={"warmth": "high", "verbosity": "low"},
        biorhythms={"chronotype": "night_owl", "energy_regen_rate": 3.0},
        persona="I am Zara, a precise and efficient coding assistant.",
    )

    assert soul.name == "Zara"
    assert soul.archetype == "The Night Coder"
    assert soul.identity.core_values == ["precision", "clarity"]
    assert soul.lifecycle == LifecycleState.ACTIVE

    # OCEAN
    p = soul.dna.personality
    assert p.openness == pytest.approx(0.8)
    assert p.conscientiousness == pytest.approx(0.9)
    assert p.neuroticism == pytest.approx(0.2)
    assert p.extraversion == pytest.approx(0.5)  # default
    assert p.agreeableness == pytest.approx(0.5)  # default

    # Communication
    c = soul.dna.communication
    assert c.warmth == "high"
    assert c.verbosity == "low"

    # Biorhythms
    b = soul.dna.biorhythms
    assert b.chronotype == "night_owl"
    assert b.energy_regen_rate == pytest.approx(3.0)

    # Persona
    core = soul.get_core_memory()
    assert "Zara" in core.persona


# ============ Soul.birth() backward compatibility ============


async def test_birth_backward_compatible():
    """Existing Soul.birth() calls (no new params) still work correctly."""
    soul = await Soul.birth(
        "Aria",
        archetype="The Compassionate Creator",
        values=["empathy", "creativity"],
    )

    assert soul.name == "Aria"
    assert soul.archetype == "The Compassionate Creator"
    assert soul.identity.core_values == ["empathy", "creativity"]
    assert soul.did.startswith("did:soul:aria-")
    assert soul.lifecycle == LifecycleState.ACTIVE
    assert soul.state.mood == Mood.NEUTRAL

    # DNA should be all defaults
    p = soul.dna.personality
    assert p.openness == pytest.approx(0.5)
    assert p.conscientiousness == pytest.approx(0.5)

    c = soul.dna.communication
    assert c.warmth == "moderate"


async def test_birth_with_kwargs_does_not_crash():
    """Extra kwargs don't crash birth (forward compatibility)."""
    soul = await Soul.birth(
        "Aria",
        future_param="some_value",
    )
    assert soul.name == "Aria"


# ============ Soul.birth_from_config() with YAML ============


async def test_birth_from_yaml_config(tmp_path):
    """birth_from_config() reads a YAML file and births a configured soul."""
    config = {
        "name": "Aria",
        "archetype": "The Coding Expert",
        "values": ["precision", "clarity", "speed"],
        "ocean": {
            "openness": 0.8,
            "conscientiousness": 0.9,
            "extraversion": 0.3,
            "agreeableness": 0.7,
            "neuroticism": 0.2,
        },
        "communication": {
            "warmth": "high",
            "verbosity": "low",
            "humor_style": "dry",
            "emoji_usage": "minimal",
        },
        "biorhythms": {
            "chronotype": "night_owl",
            "energy_regen_rate": 3.0,
        },
        "persona": "I am Aria, a precise and efficient coding assistant.",
    }

    yaml_path = tmp_path / "soul-config.yaml"
    yaml_path.write_text(yaml.dump(config, default_flow_style=False))

    soul = await Soul.birth_from_config(yaml_path)

    assert soul.name == "Aria"
    assert soul.archetype == "The Coding Expert"
    assert soul.identity.core_values == ["precision", "clarity", "speed"]

    p = soul.dna.personality
    assert p.openness == pytest.approx(0.8)
    assert p.conscientiousness == pytest.approx(0.9)
    assert p.extraversion == pytest.approx(0.3)
    assert p.neuroticism == pytest.approx(0.2)

    c = soul.dna.communication
    assert c.warmth == "high"
    assert c.verbosity == "low"

    b = soul.dna.biorhythms
    assert b.chronotype == "night_owl"

    core = soul.get_core_memory()
    assert "Aria" in core.persona


async def test_birth_from_yml_extension(tmp_path):
    """birth_from_config() works with .yml extension too."""
    config = {"name": "Bolt", "archetype": "The Quick Helper"}
    yml_path = tmp_path / "soul-config.yml"
    yml_path.write_text(yaml.dump(config))

    soul = await Soul.birth_from_config(yml_path)
    assert soul.name == "Bolt"


# ============ Soul.birth_from_config() with JSON ============


async def test_birth_from_json_config(tmp_path):
    """birth_from_config() reads a JSON file and births a configured soul."""
    config = {
        "name": "Bolt",
        "archetype": "The Fast Thinker",
        "values": ["speed", "accuracy"],
        "ocean": {
            "openness": 0.6,
            "conscientiousness": 0.8,
            "extraversion": 0.7,
            "agreeableness": 0.5,
            "neuroticism": 0.3,
        },
        "persona": "I am Bolt, built for speed and accuracy.",
    }

    json_path = tmp_path / "soul-config.json"
    json_path.write_text(json.dumps(config, indent=2))

    soul = await Soul.birth_from_config(json_path)

    assert soul.name == "Bolt"
    assert soul.archetype == "The Fast Thinker"
    assert soul.identity.core_values == ["speed", "accuracy"]
    assert soul.dna.personality.openness == pytest.approx(0.6)

    core = soul.get_core_memory()
    assert "Bolt" in core.persona


# ============ Soul.birth_from_config() minimal config ============


async def test_birth_from_config_minimal(tmp_path):
    """A config with just 'name' works — everything else defaults."""
    config = {"name": "Spark"}
    yaml_path = tmp_path / "minimal.yaml"
    yaml_path.write_text(yaml.dump(config))

    soul = await Soul.birth_from_config(yaml_path)

    assert soul.name == "Spark"
    assert soul.dna.personality.openness == pytest.approx(0.5)
    assert soul.dna.communication.warmth == "moderate"


# ============ Soul.birth_from_config() error cases ============


async def test_birth_from_config_unsupported_format(tmp_path):
    """Unsupported file format raises ValueError."""
    bad_path = tmp_path / "soul-config.txt"
    bad_path.write_text("name: Aria")

    with pytest.raises(ValueError, match="Unsupported config format"):
        await Soul.birth_from_config(bad_path)


async def test_birth_from_config_file_not_found():
    """Missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        await Soul.birth_from_config("/nonexistent/path/config.yaml")


# ============ Config roundtrip: birth with config -> export -> awaken ============


async def test_config_survives_export_roundtrip(tmp_path):
    """Custom OCEAN/communication/biorhythms survive export -> awaken."""
    original = await Soul.birth(
        "Aria",
        ocean={"openness": 0.9, "neuroticism": 0.1},
        communication={"warmth": "high", "humor_style": "dry"},
        biorhythms={"chronotype": "night_owl"},
        persona="I am Aria, configured from birth.",
    )

    soul_path = tmp_path / "aria.soul"
    await original.export(str(soul_path))

    restored = await Soul.awaken(str(soul_path))

    assert restored.name == original.name
    assert restored.dna.personality.openness == pytest.approx(0.9)
    assert restored.dna.personality.neuroticism == pytest.approx(0.1)
    assert restored.dna.personality.conscientiousness == pytest.approx(0.5)
    assert restored.dna.communication.warmth == "high"
    assert restored.dna.communication.humor_style == "dry"
    assert restored.dna.biorhythms.chronotype == "night_owl"


async def test_config_from_file_survives_roundtrip(tmp_path):
    """birth_from_config -> export -> awaken preserves all settings."""
    config = {
        "name": "Echo",
        "archetype": "The Listener",
        "ocean": {"openness": 0.7, "agreeableness": 0.9},
        "communication": {"warmth": "high", "verbosity": "high"},
        "persona": "I am Echo, I listen and reflect.",
    }
    yaml_path = tmp_path / "echo.yaml"
    yaml_path.write_text(yaml.dump(config, default_flow_style=False))

    original = await Soul.birth_from_config(yaml_path)
    soul_path = tmp_path / "echo.soul"
    await original.export(str(soul_path))

    restored = await Soul.awaken(str(soul_path))

    assert restored.name == "Echo"
    assert restored.dna.personality.openness == pytest.approx(0.7)
    assert restored.dna.personality.agreeableness == pytest.approx(0.9)
    assert restored.dna.communication.warmth == "high"


# ============ CLI --config option ============


def test_cli_birth_with_config_option(tmp_path):
    """CLI birth --config reads YAML and creates a soul file."""
    from click.testing import CliRunner

    from soul_protocol.cli.main import cli

    config = {
        "name": "CliSoul",
        "archetype": "The Helper",
        "ocean": {"openness": 0.7, "conscientiousness": 0.8},
    }
    config_path = tmp_path / "cli-config.yaml"
    config_path.write_text(yaml.dump(config))

    output_path = tmp_path / "clisoul.soul"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["birth", "--config", str(config_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    assert "Birthed" in result.output
    assert "CliSoul" in result.output
    assert output_path.exists()


def test_cli_birth_with_ocean_flags(tmp_path):
    """CLI birth with OCEAN flags creates a soul with custom personality."""
    from click.testing import CliRunner

    from soul_protocol.cli.main import cli

    output_path = tmp_path / "ocean-soul.soul"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "birth",
            "OceanTest",
            "--openness",
            "0.9",
            "--conscientiousness",
            "0.8",
            "--neuroticism",
            "0.1",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    assert "Birthed" in result.output
    assert "OceanTest" in result.output
    assert "O=0.9" in result.output  # OCEAN summary line
    assert output_path.exists()


def test_cli_birth_without_config_backward_compatible(tmp_path):
    """CLI birth without --config still works as before."""
    from click.testing import CliRunner

    from soul_protocol.cli.main import cli

    output_path = tmp_path / "basic.soul"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["birth", "BasicSoul", "--output", str(output_path)],
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    assert "Birthed" in result.output
    assert "BasicSoul" in result.output
    assert output_path.exists()


def test_cli_birth_config_json(tmp_path):
    """CLI birth --config works with JSON files too."""
    from click.testing import CliRunner

    from soul_protocol.cli.main import cli

    config = {
        "name": "JsonSoul",
        "ocean": {"openness": 0.6},
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    output_path = tmp_path / "jsonsoul.soul"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["birth", "--config", str(config_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    assert "JsonSoul" in result.output
    assert output_path.exists()
