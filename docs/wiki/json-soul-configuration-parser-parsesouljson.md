---
{
  "title": "JSON Soul Configuration Parser (parse_soul_json)",
  "summary": "A single-function module that parses a JSON string into a validated SoulConfig using Pydantic's model_validate_json, combining deserialization and schema validation in one atomic step.",
  "concepts": [
    "JSON parser",
    "SoulConfig",
    "Pydantic validation",
    "model_validate_json",
    "soul configuration",
    "configuration parsing",
    "parse_soul_json"
  ],
  "categories": [
    "parsers",
    "configuration",
    "JSON"
  ],
  "source_docs": [
    "1acd3e1880bc6066"
  ],
  "backlinks": null,
  "word_count": 475,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`parse_soul_json()` is the entry point for souls defined in JSON format. JSON soul configs are typically generated programmatically — by APIs, build scripts, or SoulFactory templates — rather than written by hand. The function provides a clean, typed conversion from raw JSON string to a fully validated `SoulConfig`.

## Implementation

```python
def parse_soul_json(content: str) -> SoulConfig:
    return SoulConfig.model_validate_json(content)
```

The brevity is intentional and reflects correct use of Pydantic v2's API. `model_validate_json()` performs both JSON parsing and Pydantic model validation in a single pass — it is faster than the two-step alternative (`json.loads()` + `model_validate()`) because Pydantic's Rust-backed JSON parser avoids building an intermediate Python dict.

## Error Contract

The function does not catch exceptions — it surfaces them directly to the caller:

- `pydantic.ValidationError`: The JSON was valid but did not match the `SoulConfig` schema (e.g., a required field was missing, a value was the wrong type).
- `ValueError`: The string was not valid JSON at all.

This clean error propagation allows the caller (typically `Soul.birth_from_config()`) to decide whether to log and re-raise, show a user-facing error message, or fall back to another config format.

## Why a Standalone Module?

Keeping the JSON parser isolated from the YAML and Markdown parsers prevents import coupling. `yaml_parser.py` imports `pyyaml`; `markdown.py` imports both `pyyaml` and the DID generator. A consumer that only uses JSON configs imports only this file and its single `soul_protocol.runtime.types` dependency — no YAML, no regex, no DID library.

## Integration

Called by `Soul.birth_from_config()` after file extension dispatch:

```python
if path.suffix == ".json":
    config = parse_soul_json(path.read_text())
```

Also usable directly in tests or API handlers that receive JSON payloads over HTTP without going through the file system.

## Known Gaps

- No schema version handling. If `SoulConfig` adds a required field in a future version, older JSON files will fail validation with a cryptic Pydantic error rather than a helpful "schema version mismatch" message.
- No support for JSON with comments (JSONC format), which some users prefer for annotating soul config files.

## Comparison: model_validate_json vs. Two-Step Parse

Pydantic v2 provides two routes to build a model from JSON:

```python
# Route 1 — single pass (what we use):
SoulConfig.model_validate_json(content)

# Route 2 — two steps:
import json
data = json.loads(content)
SoulConfig.model_validate(data)
```

Route 1 uses Pydantic's Rust-backed JSON parser which produces the validated model directly without allocating an intermediate Python dict. For large soul configs with long core memory sections, this can be 30–50% faster. The single-pass approach also produces cleaner error messages: the `ValidationError` includes the JSON path to the offending field.

## Testing Pattern

The function is trivially mockable in tests since it is a pure function — no class state, no side effects:

```python
def test_missing_name_raises():
    with pytest.raises(pydantic.ValidationError):
        parse_soul_json('{"archetype": "companion"}')
```

This makes `parse_soul_json` one of the easiest entry points to test comprehensively across all invalid schema variations.
