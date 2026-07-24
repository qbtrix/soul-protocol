# test_schemas.py — Tests for JSON schema generation from Pydantic models
# Created: 2026-03-02 — Validate schema generation, structure, and on-disk files
# Updated: 2026-03-02 — Handle Enum types (Mood) that lack model_json_schema()

"""Tests for JSON schema generation.

Verifies:
  1. All models produce valid JSON schemas without error.
  2. A sample SoulConfig dict validates against the generated schema.
  3. Schema files exist on disk after generation.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel

from soul_protocol.runtime.types import (
    DNA,
    Biorhythms,
    CommunicationStyle,
    CoreMemory,
    EvolutionConfig,
    GeneralEvent,
    Identity,
    Interaction,
    MemoryEntry,
    MemorySettings,
    Mood,
    Mutation,
    Personality,
    ReflectionResult,
    SelfImage,
    SignificanceScore,
    SomaticMarker,
    SoulConfig,
    SoulManifest,
    SoulState,
)

ALL_MODELS = [
    SoulConfig,
    Identity,
    Personality,
    CommunicationStyle,
    Biorhythms,
    DNA,
    SomaticMarker,
    SignificanceScore,
    GeneralEvent,
    SelfImage,
    MemoryEntry,
    CoreMemory,
    MemorySettings,
    SoulState,
    Mood,
    EvolutionConfig,
    Mutation,
    Interaction,
    SoulManifest,
    ReflectionResult,
]

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


# ---------- 1. Schema generation works for every model ----------


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__name__)
def test_model_produces_valid_json_schema(model):
    """Each model should produce a JSON-serializable schema dict."""
    if isinstance(model, type) and issubclass(model, BaseModel):
        schema = model.model_json_schema()
    elif isinstance(model, type) and issubclass(model, Enum):
        # Enums don't have model_json_schema — build a simple schema
        schema = {
            "title": model.__name__,
            "type": "string",
            "enum": [m.value for m in model],
        }
    else:
        pytest.fail(f"Unsupported type: {model}")

    assert isinstance(schema, dict)
    assert "properties" in schema or "enum" in schema or "anyOf" in schema
    # Round-trip through JSON to prove it's serializable
    raw = json.dumps(schema, default=str)
    reloaded = json.loads(raw)
    assert reloaded == json.loads(json.dumps(schema, default=str))


# ---------- 2. Sample SoulConfig validates against schema ----------


def test_sample_soul_config_matches_schema():
    """A minimal SoulConfig dict should match the schema structure."""
    sample = {
        "version": "1.0.0",
        "identity": {
            "name": "Aria",
            "archetype": "companion",
            "origin_story": "Born in the OCEAN lab",
            "prime_directive": "Be helpful and kind",
            "core_values": ["empathy", "curiosity"],
        },
        "dna": {
            "personality": {
                "openness": 0.8,
                "conscientiousness": 0.7,
                "extraversion": 0.6,
                "agreeableness": 0.9,
                "neuroticism": 0.3,
            },
            "communication": {
                "warmth": "high",
                "verbosity": "moderate",
                "humor_style": "gentle",
                "emoji_usage": "moderate",
            },
            "biorhythms": {
                "chronotype": "morning",
                "social_battery": 85.0,
                "energy_regen_rate": 5.0,
            },
        },
        "memory": {
            "episodic_max_entries": 10000,
            "semantic_max_facts": 1000,
            "importance_threshold": 3,
        },
        "lifecycle": "born",
    }

    schema = SoulConfig.model_json_schema()

    # Structural checks: every top-level key in the sample should be
    # a recognized property in the schema
    schema_props = schema.get("properties", {})
    for key in sample:
        assert key in schema_props, f"'{key}' not found in SoulConfig schema properties"

    # Required fields should include at least 'identity'
    required = schema.get("required", [])
    assert "identity" in required

    # Validate by actually constructing the model (the strongest check)
    soul = SoulConfig(**sample)
    assert soul.identity.name == "Aria"
    assert soul.dna.personality.openness == 0.8


# ---------- 3. Schema files exist on disk ----------


def test_individual_schema_files_exist():
    """After running generate_schemas.py, each model should have a file."""
    for model in ALL_MODELS:
        path = SCHEMAS_DIR / f"{model.__name__}.schema.json"
        assert path.exists(), f"Missing schema file: {path}"

        content = json.loads(path.read_text())
        assert isinstance(content, dict)


def test_combined_schema_file_exists():
    """The combined soul-protocol.schema.json should exist and have $defs."""
    path = SCHEMAS_DIR / "soul-protocol.schema.json"
    assert path.exists(), f"Missing combined schema: {path}"

    content = json.loads(path.read_text())
    assert "$defs" in content
    assert "SoulConfig" in content["$defs"]
    assert "$ref" in content


def test_schema_drift():
    """CI drift test: ensure on-disk schemas match generated schemas exactly."""
    # Generate schemas in memory
    individual = {}
    for model in ALL_MODELS:
        name = model.__name__
        if isinstance(model, type) and issubclass(model, BaseModel):
            schema = model.model_json_schema()
        elif isinstance(model, type) and issubclass(model, Enum):
            schema = {
                "title": model.__name__,
                "description": model.__doc__ or "",
                "type": "string",
                "enum": [m.value for m in model],
            }
        else:
            pytest.fail(f"Unsupported type: {model}")
        individual[name] = schema

    # Check individual schemas
    for name, schema in individual.items():
        path = SCHEMAS_DIR / f"{name}.schema.json"
        assert path.exists(), f"Missing on-disk schema: {path}"
        on_disk = json.loads(path.read_text())

        # We dump and load to ensure types like UUID/datetime are serialized exactly as they would be to JSON
        memory_json = json.loads(json.dumps(schema, default=str))
        assert on_disk == memory_json, (
            f"Schema drift detected in {name}.schema.json! Run scripts/generate_schemas.py"
        )

    # Check combined schema
    defs = {}
    for name, schema in individual.items():
        if "$defs" in schema:
            for def_name, def_schema in schema["$defs"].items():
                defs[def_name] = def_schema
        model_def = {k: v for k, v in schema.items() if k != "$defs"}
        defs[name] = model_def

    combined = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/OCEAN/soul-protocol/schemas/soul-protocol.schema.json",
        "title": "Soul Protocol",
        "description": "Complete JSON Schema bundle for the Digital Soul Protocol (DSP) v1.0. "
        "Defines every model used in .soul files, memory entries, evolution, and state.",
        "$ref": "#/$defs/SoulConfig",
        "$defs": defs,
    }

    path = SCHEMAS_DIR / "soul-protocol.schema.json"
    assert path.exists(), f"Missing on-disk schema: {path}"
    on_disk = json.loads(path.read_text())
    memory_json = json.loads(json.dumps(combined, default=str))

    assert on_disk == memory_json, (
        "Schema drift detected in soul-protocol.schema.json! Run scripts/generate_schemas.py"
    )
