---
{
  "title": "Test Suite: Core Pydantic Data Models",
  "summary": "Validates the foundational Pydantic models in soul_protocol.types — Identity defaults, Personality trait bounds, SoulConfig JSON serialization round-trip, MemoryEntry defaults, Mood enum completeness, and EvolutionMode enum values.",
  "concepts": [
    "Identity",
    "Personality",
    "SoulConfig",
    "MemoryEntry",
    "Mood",
    "EvolutionMode",
    "Pydantic",
    "data models",
    "ValidationError",
    "OCEAN traits",
    "soul_protocol.types",
    "JSON round-trip"
  ],
  "categories": [
    "data-models",
    "testing",
    "pydantic",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "8afd9233ca61e687"
  ],
  "backlinks": null,
  "word_count": 449,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Core Pydantic Data Models

`test_types.py` is the canonical contract test for soul-protocol's Pydantic data models. Created 2026-02-22, it verifies the six core types that form the data backbone of every soul: `Identity`, `Personality`, `SoulConfig`, `MemoryEntry`, `Mood`, and `EvolutionMode`.

### Why Contract Tests for Data Models?

Pydantic models have implicit behavioral contracts — default values, validation ranges, and serialization format. Without explicit tests, small model changes (adding a field, changing a default, tightening a validator) can silently break downstream code that depends on specific defaults or JSON structure. These tests serve as a stability guarantee for the public API.

### Identity Defaults

```python
ident = Identity(name="Aria")
assert ident.did == ""
assert ident.archetype == ""
assert ident.bonded_to is None
assert ident.origin_story == ""
assert ident.prime_directive == ""
assert ident.core_values == []
assert ident.born is not None
```

Only `name` is required. All other fields use safe defaults: empty strings (not None) for text fields, an empty list for `core_values`, `None` for `bonded_to`, and a real timestamp for `born`. Explicit testing of these defaults prevents accidental breaking changes when model fields are refactored.

### Personality Bounds Validation

```python
# Valid at boundaries
Personality(openness=0.0, conscientiousness=1.0)  # OK

# Defaults are all 0.5 (neutral)
Personality().openness == 0.5

# Out-of-range raises ValidationError
with pytest.raises(ValidationError):
    Personality(openness=1.5)
```

OCEAN traits are constrained to [0.0, 1.0]. The test verifies both boundary values are valid, the default is 0.5 (neutral midpoint), and values outside the range raise `pydantic.ValidationError`. This prevents nonsensical personality configurations from silently entering the system.

### SoulConfig JSON Round-Trip

```python
json_str = config.model_dump_json()
restored = SoulConfig.model_validate_json(json_str)
# restored must equal config
```

`SoulConfig` wraps `Identity`, `Personality`, and `MemorySettings` into a single document. The round-trip test ensures that all nested models serialize to valid JSON and deserialize back to equal Python objects — critical for `.soul` file persistence.

### MemoryEntry Defaults

`test_memory_entry_defaults` verifies that a `MemoryEntry` created with only `type` and `content` has sensible defaults for `importance` (5), `created_at` (present timestamp), and all optional fields (`None`). This guards against entries with unexpected null fields reaching storage.

### Mood Enum

`test_mood_enum_values` checks that the `Mood` enum contains all expected values. This prevents accidental removal of mood states that downstream code may reference by name.

### EvolutionMode Enum

```python
assert EvolutionMode.DISABLED in EvolutionMode
assert EvolutionMode.SUPERVISED in EvolutionMode
assert EvolutionMode.AUTONOMOUS in EvolutionMode
```

`EvolutionMode` controls whether a soul's personality can change over time. Three modes: `DISABLED` (static), `SUPERVISED` (changes require approval), `AUTONOMOUS` (self-directed). The test ensures all three exist and the enum is stable.

### Known Gaps

No test covers `SoulConfig` with non-default `MemorySettings` or nested validation errors. The `Identity.bonded_to` field (deprecated in favor of `bonds` in multi-bond work) is still tested here as a backwards-compat assertion.
