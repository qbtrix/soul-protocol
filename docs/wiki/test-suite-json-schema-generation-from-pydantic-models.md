---
{
  "title": "Test Suite: JSON Schema Generation from Pydantic Models",
  "summary": "Verifies that every Soul Protocol Pydantic model can produce a valid, JSON-serializable schema, that a sample `SoulConfig` dict validates against the generated schema, and that the `generate_schemas.py` script produces the expected on-disk files. This acts as a contract test for external consumers who depend on the published JSON schemas.",
  "concepts": [
    "JSON schema",
    "Pydantic model_json_schema",
    "SoulConfig",
    "schema generation",
    "Enum schema",
    "round-trip serialization",
    "generate_schemas.py",
    "soul-protocol.schema.json",
    "$defs",
    "ALL_MODELS",
    "parametrize"
  ],
  "categories": [
    "testing",
    "schema validation",
    "API contract",
    "serialization",
    "test"
  ],
  "source_docs": [
    "b4bc14ab5ec7e883"
  ],
  "backlinks": null,
  "word_count": 453,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul Protocol publishes machine-readable JSON schemas so third parties (integrations, validators, IDEs) can validate soul files without importing the Python package. If any model's schema generation breaks — for example because a new field type is not JSON-serializable — that breakage would only be discovered when a consumer tries to use the published schema. These tests catch those regressions at development time.

## Model Coverage

The test parametrizes over `ALL_MODELS`:

```python
ALL_MODELS = [
    SoulConfig, Identity, Personality, CommunicationStyle, Biorhythms, DNA,
    SomaticMarker, SignificanceScore, GeneralEvent, SelfImage, MemoryEntry,
    CoreMemory, MemorySettings, SoulState, Mood, EvolutionConfig, Mutation,
    Interaction, SoulManifest, ReflectionResult,
]
```

Every model in this list is tested individually, which means the parametrize output in the test runner names each failure by model class name, making it easy to identify which model broke.

## Enum Handling

The `Mood` enum is a Pydantic `Enum` subclass, not a `BaseModel`. It does not have `model_json_schema()`. The test handles this with a branch:

```python
if isinstance(model, type) and issubclass(model, BaseModel):
    schema = model.model_json_schema()
elif isinstance(model, type) and issubclass(model, Enum):
    schema = {"title": model.__name__, "type": "string", "enum": [m.value for m in model]}
```

This was added in the `Updated: 2026-03-02 — Handle Enum types` commit. Without it, `Mood` would cause a `pytest.fail()` and mask any real schema issues in the other models.

## Sample SoulConfig Validation

`test_sample_soul_config_matches_schema` constructs a minimal `SoulConfig` dict and verifies it validates against the generated schema. This catches mismatches between the schema output and what the model actually accepts — for example, if a required field is omitted from the sample, the test fails and documents the minimum viable config structure.

## On-Disk File Checks

Two tests verify that running `generate_schemas.py` produces:
1. **Per-model files**: One JSON file per model in `schemas/`.
2. **Combined schema**: A single `soul-protocol.schema.json` with a top-level `$defs` block that references all model schemas.

These tests prevent the schema files from going stale after model changes. They are not pure unit tests — they depend on the `schemas/` directory existing, meaning they require the code generation script to have been run.

## Round-Trip JSON Serialization

Every schema dict is serialized to JSON and deserialized back to verify round-trip stability:

```python
raw = json.dumps(schema, default=str)
reloaded = json.loads(raw)
assert reloaded == json.loads(json.dumps(schema, default=str))
```

The `default=str` fallback catches types like `datetime` or custom classes that Pydantic might embed in a schema. Without it, `json.dumps` would raise `TypeError` on non-serializable schema values.

## Known Gaps

`SCHEMAS_DIR` is derived from the test file's path at import time (`Path(__file__).resolve().parent.parent / "schemas"`). If the test file is moved, the path breaks. There is no test verifying that the per-model schema file names follow a specific naming convention (e.g., snake_case vs. PascalCase), so inconsistent naming would not be caught.