---
{
  "title": "Test Suite: Identity Spec — Construction, Auto-ID, Traits, and Serialization",
  "summary": "Validates the core `Identity` primitive from `soul_protocol.spec`, covering minimal construction, deterministic auto-ID generation, uniqueness guarantees, arbitrary traits storage, and Pydantic `model_dump`/`model_validate` round-trip fidelity. Identity is the foundational spec model that all other containers reference.",
  "concepts": [
    "Identity",
    "auto-ID",
    "12-character hex",
    "traits dict",
    "created_at",
    "model_dump",
    "model_validate",
    "serialization round-trip",
    "explicit ID",
    "spec layer",
    "uniqueness"
  ],
  "categories": [
    "testing",
    "spec layer",
    "identity",
    "serialization",
    "test"
  ],
  "source_docs": [
    "7e4cc1855c839b19"
  ],
  "backlinks": null,
  "word_count": 476,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`Identity` is the simplest model in Soul Protocol's spec layer and the foundation for `SoulContainer`, the runtime `Soul`, and any future soul-like entity. Its tests are intentionally small because `Identity` has minimal behavior — but each test pins a specific contract that higher-level code depends on.

## Minimal Construction

```python
def test_identity_basic():
    identity = Identity(name="Aria")
    assert identity.name == "Aria"
    assert identity.traits == {}     # not None
    assert identity.created_at is not None
```

The test asserts `traits == {}` specifically — not `traits is None`. This matters because code that does `identity.traits["role"]` or `identity.traits.get("role")` would crash on `None` but work correctly on an empty dict. `created_at` is set at construction time, enabling age calculations and sorting without requiring callers to supply a timestamp.

## Auto-ID Generation

```python
def test_identity_auto_id():
    identity = Identity(name="Aria")
    assert len(identity.id) == 12
    assert all(c in "0123456789abcdef" for c in identity.id)
```

The 12-character hex format is:
- Short enough to be human-readable in logs and debug output
- Long enough to have 16^12 ≈ 281 trillion possible values, making collisions extremely unlikely
- Hex-only (no hyphens or special characters), making it safe in file paths, URLs, and database keys without escaping

## Uniqueness

```python
def test_identity_auto_id_is_unique():
    a = Identity(name="Aria")
    b = Identity(name="Aria")
    assert a.id != b.id
```

This test catches an implementation that caches the ID generation or seeds a random generator with a name-based hash, which would produce identical IDs for souls with the same name. In a multi-agent fleet, this would cause identity collisions.

## Traits Storage

```python
def test_identity_traits():
    traits = {"role": "assistant", "openness": 0.85, "tags": ["empathic"]}
    identity = Identity(name="Aria", traits=traits)
    assert identity.traits["role"] == "assistant"
    assert identity.traits["openness"] == 0.85
    assert identity.traits["tags"] == ["empathic"]
```

Traits accept heterogeneous value types (string, float, list). The spec does not validate or interpret traits — it stores them as-is. This flexibility is intentional: different deployment contexts add different domain-specific traits (OCEAN scores, role strings, capability tags) without requiring spec changes.

## Serialization Round-Trip

```python
def test_identity_serialization():
    raw = identity.model_dump()
    restored = Identity.model_validate(raw)
    assert restored.id == identity.id
    assert restored.created_at == identity.created_at
```

Both `id` and `created_at` must be preserved exactly through serialization. `id` is a string — no risk of type coercion. `created_at` is a datetime — the test verifies timezone-aware equality, catching implementations that serialize to naive datetime strings and lose timezone information.

## Explicit ID Override

```python
def test_identity_explicit_id():
    identity = Identity(name="Aria", id="abc123def456")
    assert identity.id == "abc123def456"
```

When an ID is provided explicitly, auto-generation must not override it. This enables ID preservation during migration — loading a soul from an older file format that already has a known ID.

## Known Gaps

No TODO or FIXME markers. There is no test for what happens when an explicit ID is provided that does not match the 12-character hex format — it is unclear whether validation rejects it or accepts any string.