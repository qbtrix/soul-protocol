# Soul Protocol JSON Schemas

Machine-readable [JSON Schema](https://json-schema.org/) definitions for every data model in the Digital Soul Protocol (DSP). These schemas are auto-generated from the canonical Pydantic models in `src/soul_protocol/spec/memory.py` and `src/soul_protocol/runtime/types.py`.

## What's here

| File | Description |
|------|-------------|
| `SoulConfig.schema.json` | The main schema for a `.soul` file's config payload |
| `Identity.schema.json` | Soul identity (DID, name, archetype, values) |
| `Personality.schema.json` | Big Five OCEAN trait scores |
| `DNA.schema.json` | Complete personality blueprint (personality + communication + biorhythms) |
| `MemoryEntry.schema.json` | A single memory with somatic markers and significance |
| `SoulState.schema.json` | Current mood, energy, and social battery |
| `EvolutionConfig.schema.json` | Evolution system settings and mutation history |
| `SoulManifest.schema.json` | Metadata for `.soul` archive files |
| `soul-protocol.schema.json` | **Combined bundle** with all models under `$defs` |
| *(and more)* | One file per model — see the full list below |

## Why JSON Schemas?

The Soul Protocol is language-agnostic. While the reference implementation is in Python, souls should be readable and writable from any language. These schemas let you:

- **Validate** `.soul` files and memory exports in JavaScript, Go, Rust, Java, or any language with a JSON Schema validator
- **Generate** type-safe client code using tools like `quicktype`, `json-schema-to-typescript`, or `datamodel-code-generator`
- **Document** the protocol in a way that's both human-readable and machine-parseable

## Validating a .soul file

### Python

```python
import json
from jsonschema import validate

with open("schemas/SoulConfig.schema.json") as f:
    schema = json.load(f)

soul_data = {"version": "1.0.0", "identity": {"name": "Aria"}}
validate(instance=soul_data, schema=schema)
```

### JavaScript / Node.js

```javascript
const Ajv = require("ajv");
const schema = require("./schemas/SoulConfig.schema.json");

const ajv = new Ajv();
const validate = ajv.compile(schema);

const soulData = { version: "1.0.0", identity: { name: "Aria" } };
const valid = validate(soulData);
if (!valid) console.error(validate.errors);
```

### CLI (using `check-jsonschema`)

```bash
pip install check-jsonschema
check-jsonschema --schemafile schemas/SoulConfig.schema.json my_soul.json
```

## Regenerating

Schemas are generated from the Pydantic source of truth. To regenerate after changing the models:

```bash
uv run python scripts/generate_schemas.py
```

## All models

Identity, Personality, CommunicationStyle, Biorhythms, DNA, SomaticMarker, SignificanceScore, GeneralEvent, SelfImage, MemoryEntry, CoreMemory, MemorySettings, SoulState, Mood, EvolutionConfig, Mutation, Interaction, SoulManifest, ReflectionResult, SoulConfig
