# generate_schemas.py — Generate JSON Schema files from all Pydantic models
# Created: 2026-03-02 — Initial version for cross-language schema support
# Updated: 2026-03-02 — Handle Enum types (Mood) that lack model_json_schema()
#
# Imports every Pydantic model from soul_protocol.types, calls
# .model_json_schema() on each, and writes individual + combined schemas
# to the schemas/ directory.

"""Generate JSON Schema files from Soul Protocol Pydantic models.

Usage:
    python scripts/generate_schemas.py

Outputs:
    schemas/<ModelName>.schema.json  — one per model
    schemas/soul-protocol.schema.json — combined bundle with $defs
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from soul_protocol.types import (
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

# All models to generate schemas for, in logical grouping order
MODELS = [
    # Top-level
    SoulConfig,
    # Identity
    Identity,
    # DNA / Personality
    Personality,
    CommunicationStyle,
    Biorhythms,
    DNA,
    # Psychology
    SomaticMarker,
    SignificanceScore,
    GeneralEvent,
    SelfImage,
    # Memory
    MemoryEntry,
    CoreMemory,
    MemorySettings,
    # State
    SoulState,
    Mood,
    # Evolution
    EvolutionConfig,
    Mutation,
    # Lifecycle
    Interaction,
    SoulManifest,
    ReflectionResult,
]

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


def _enum_schema(enum_cls: type[Enum]) -> dict:
    """Build a JSON Schema for a plain Enum (not a BaseModel)."""
    return {
        "title": enum_cls.__name__,
        "description": enum_cls.__doc__ or "",
        "type": "string",
        "enum": [member.value for member in enum_cls],
    }


def generate_individual_schemas() -> dict[str, dict]:
    """Generate one schema file per model. Returns {name: schema} mapping."""
    schemas = {}
    for model in MODELS:
        name = model.__name__

        if isinstance(model, type) and issubclass(model, BaseModel):
            schema = model.model_json_schema()
        elif isinstance(model, type) and issubclass(model, Enum):
            schema = _enum_schema(model)
        else:
            raise TypeError(f"Unsupported type: {model}")

        schemas[name] = schema

        out_path = SCHEMAS_DIR / f"{name}.schema.json"
        out_path.write_text(json.dumps(schema, indent=2, default=str) + "\n")
        print(f"  wrote {out_path.relative_to(SCHEMAS_DIR.parent)}")

    return schemas


def generate_combined_schema(individual: dict[str, dict]) -> dict:
    """Bundle all schemas into a single file with $defs.

    The combined schema uses SoulConfig as the root and places all
    other model schemas under $defs for cross-referencing.
    """
    defs = {}
    for name, schema in individual.items():
        # Pull nested $defs up to the top level
        if "$defs" in schema:
            for def_name, def_schema in schema["$defs"].items():
                defs[def_name] = def_schema

        # Add the model itself as a def (strip $defs from the copy)
        model_def = {k: v for k, v in schema.items() if k != "$defs"}
        defs[name] = model_def

    # Root schema references SoulConfig
    combined = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/OCEAN/soul-protocol/schemas/soul-protocol.schema.json",
        "title": "Soul Protocol",
        "description": "Complete JSON Schema bundle for the Digital Soul Protocol (DSP) v1.0. "
        "Defines every model used in .soul files, memory entries, evolution, and state.",
        "$ref": "#/$defs/SoulConfig",
        "$defs": defs,
    }

    out_path = SCHEMAS_DIR / "soul-protocol.schema.json"
    out_path.write_text(json.dumps(combined, indent=2, default=str) + "\n")
    print(f"  wrote {out_path.relative_to(SCHEMAS_DIR.parent)}")

    return combined


def main() -> int:
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating individual schemas...")
    individual = generate_individual_schemas()

    print(f"\nGenerated {len(individual)} individual schemas.")

    print("\nGenerating combined schema...")
    generate_combined_schema(individual)

    print(f"\nDone. All schemas written to {SCHEMAS_DIR.relative_to(SCHEMAS_DIR.parent)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
