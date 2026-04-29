---
{
  "title": "Schema Generator: JSON Schema Export for All Soul Protocol Pydantic Models",
  "summary": "A utility script that introspects every Pydantic model in `soul_protocol.runtime.types` and writes individual JSON Schema files plus a combined bundle to the `schemas/` directory, enabling cross-language clients (TypeScript, Rust, Go) to validate soul data structures without depending on the Python package.",
  "concepts": [
    "JSON Schema",
    "Pydantic",
    "schema generation",
    "cross-language",
    "SoulConfig",
    "SoulManifest",
    "Enum handling",
    "combined schema",
    "$defs",
    "$ref",
    "soul_protocol.runtime.types",
    "TypeScript client"
  ],
  "categories": [
    "scripts",
    "tooling",
    "schema",
    "soul-protocol"
  ],
  "source_docs": [
    "9e9cbed6229767a8"
  ],
  "backlinks": null,
  "word_count": 379,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Soul Protocol is a portable protocol, not a Python-only library. Clients written in TypeScript (PocketPaw frontend), Rust (potential native clients), or Go (server integrations) need to validate `.soul` file contents and API payloads without importing Python. JSON Schema is the lingua franca for cross-language schema validation.

`generate_schemas.py` automates schema extraction from the source of truth — the Pydantic models — eliminating the risk of schemas drifting out of sync with the implementation.

## Model Coverage

```python
MODELS = [
    SoulConfig, Identity, Personality, CommunicationStyle, Biorhythms, DNA,
    SomaticMarker, SignificanceScore, GeneralEvent, SelfImage,
    MemoryEntry, CoreMemory, MemorySettings,
    SoulState, Mood,
    EvolutionConfig, Mutation,
    Interaction, SoulManifest, ReflectionResult,
]
```

Models are listed in logical grouping order (top-level → identity → DNA → psychology → memory → state → evolution → lifecycle), which determines the order of `$defs` in the combined schema. This order matters for human readability but not for validation.

## Enum Handling

`Mood` is a plain `Enum` rather than a Pydantic `BaseModel`, so it lacks `model_json_schema()`. The `_enum_schema(enum_cls)` helper constructs a valid JSON Schema manually:

```python
def _enum_schema(enum_cls: type[Enum]) -> dict:
    return {
        "title": enum_cls.__name__,
        "description": enum_cls.__doc__ or "",
        "type": "string",
        "enum": [e.value for e in enum_cls],
    }
```

Without this special case, `Mood` would be silently skipped or raise `AttributeError`. The update note in the source header documents that this was added after the initial version.

## Output Files

| File | Content |
|---|---|
| `schemas/SoulConfig.schema.json` | Individual schema per model |
| `schemas/soul-protocol.schema.json` | Combined bundle with `$defs` |

The combined bundle uses `$defs` with `$ref` cross-references so that a client validating a `SoulManifest` automatically pulls in `DNA`, `CoreMemory`, etc. This is more robust than duplicating nested schema inline.

## Usage

```bash
python scripts/generate_schemas.py
# → schemas/ directory populated
```

The script returns exit code 0 on success, non-zero on failure, making it safe to add to CI as a "schemas are current" check.

## Known Gaps

- There is no check that the generated schemas are actually up to date with the current models. A CI step that runs `generate_schemas.py` and then runs `git diff --exit-code schemas/` would catch schema drift before it reaches consumers.
- The combined schema does not enforce an explicit `$schema` version declaration, which can cause validation tool compatibility issues with strict JSON Schema validators.
