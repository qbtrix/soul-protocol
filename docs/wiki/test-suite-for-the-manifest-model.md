---
{
  "title": "Test Suite for the Manifest Model",
  "summary": "This test suite validates the `Manifest` Pydantic model, which acts as the metadata header of a `.soul` archive. It covers default field values, explicit field assignment, and the full Pydantic serialization roundtrip to ensure no data is silently dropped during pack/unpack.",
  "concepts": [
    "Manifest",
    "soul archive",
    ".soul file",
    "Pydantic serialization",
    "model_dump",
    "model_validate",
    "format_version",
    "checksum",
    "soul_id",
    "soul portability"
  ],
  "categories": [
    "testing",
    "soul-format",
    "spec",
    "serialization",
    "test"
  ],
  "source_docs": [
    "189d6fd38dd23cb5"
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

The `Manifest` model is the envelope metadata that accompanies every `.soul` archive. It records the format version, the soul's identity references, a checksum for integrity verification, and aggregate stats. These tests exist because a broken manifest can silently corrupt portable soul transfers — a soul can be loaded but the platform receiving it has no way to validate its integrity or origin.

## What Is Being Tested

### Default Field Behavior

The `test_manifest_defaults` test confirms that a zero-argument `Manifest()` is always valid and carries safe empty-string defaults. This defensive pattern prevents `AttributeError` or `None`-comparison failures downstream when code reads `manifest.soul_id` on a freshly constructed object before any values are set.

```python
manifest = Manifest()
assert manifest.format_version == "1.0.0"
assert manifest.soul_id == ""
assert manifest.checksum == ""
assert manifest.stats == {}
assert manifest.created is not None
```

Notably, `created` auto-populates even on an empty manifest, which gives every manifest a traceable birth timestamp without requiring the caller to supply one.

### Explicit Value Storage

`test_manifest_with_values` confirms that caller-supplied values survive construction. This sounds trivial but becomes important when validating that Pydantic validators or field aliases are not silently transforming or discarding data — for example, normalizing `soul_id` to lowercase or stripping whitespace.

### Serialization Roundtrip

`test_manifest_serialization` is the most critical test. It exercises the `model_dump()` / `model_validate()` path that the `.soul` file format depends on for persistence:

```python
raw = manifest.model_dump()
restored = Manifest.model_validate(raw)
assert restored.soul_id == manifest.soul_id
assert restored.stats == manifest.stats
assert restored.created == manifest.created
```

The `created` field is explicitly checked in the roundtrip because datetime serialization is a common failure point — JSON does not natively support datetime objects, and a misconfigured Pydantic model can silently convert a `datetime` to a string and then fail to parse it back to the same type on reload.

## Why This Matters for Soul Portability

The `.soul` file is a portable zip archive intended to migrate AI companion identity across platforms. The manifest is read first during unpack to decide whether the archive is compatible with the current runtime version. If `format_version` is not preserved correctly through a roundtrip, a platform receiving a migrated soul would incorrectly reject valid archives.

The `checksum` field is checked to detect corruption during transport. An empty default is fine at construction time, but the roundtrip test ensures a non-empty checksum written by the pack step is faithfully restored on the unpack side.

## Known Gaps

- The tests do not verify that `format_version` follows semantic versioning rules (e.g., rejects `"1"` or `"v1.0.0"`). Pydantic validators for this field may or may not exist.
- There is no test for what happens when `model_validate` receives a future format version (e.g., `"2.0.0"`). Forward-compatibility behavior is not covered.
- The `stats` field accepts an arbitrary dict — no schema is enforced. Tests only cover the keys `total_memories` and `layers`, leaving other keys untested.