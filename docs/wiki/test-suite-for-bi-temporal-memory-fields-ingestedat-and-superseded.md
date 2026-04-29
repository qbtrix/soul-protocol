---
{
  "title": "Test Suite for Bi-Temporal Memory Fields (ingested_at and superseded)",
  "summary": "Validates bi-temporal tracking on MemoryEntry — the `ingested_at` timestamp (when a fact entered this soul's memory vs. when it was created) and the `superseded` flag (marking outdated facts replaced by newer information). Tests cover defaults, explicit values, manager behavior, serialization round-trips, and backward compatibility with soul files that predate these fields.",
  "concepts": [
    "ingested_at",
    "superseded",
    "bi-temporal",
    "MemoryEntry",
    "MemoryManager",
    "created_at",
    "soul migration",
    "backward compatibility",
    "serialization",
    "spec layer",
    "valid time",
    "transaction time"
  ],
  "categories": [
    "testing",
    "memory",
    "bi-temporal",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "798df9ba244940de"
  ],
  "backlinks": null,
  "word_count": 485,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_bitemporal.py` verifies the bi-temporal data model applied to soul memory. "Bi-temporal" means each memory entry carries two independent time axes:

1. **`created_at`** — when the underlying fact or event occurred (valid time)
2. **`ingested_at`** — when this soul processed and stored the fact (transaction time)

This distinction matters for soul migration: when a fact from an old soul is imported into a new one, its `created_at` is preserved (the event hasn't changed) but `ingested_at` reflects the import time (when this soul learned of it). Without this field, there would be no way to distinguish original memories from imported ones.

## ingested_at Field (TestIngestedAtField)

### Defaults and Explicit Values
- `test_default_is_none` — a newly constructed `MemoryEntry` has `ingested_at = None` until it is stored
- `test_explicit_value_preserved` — if `ingested_at` is set explicitly, the value is not overwritten
- `test_created_at_independent_of_ingested_at` — the two timestamps are independent; setting one does not affect the other

### Manager Behavior
```python
async def test_add_sets_ingested_at(manager):
    # MemoryManager.add() must set ingested_at to now() if it is None
    # This is the canonical "stamp on ingest" behavior

async def test_add_preserves_explicit_ingested_at(manager):
    # If ingested_at is already set (e.g., during migration), manager must not overwrite it
```

The preservation test is the critical migration correctness check. If the manager always overwrote `ingested_at`, imported memories would lose their historical ingestion timestamps, making it impossible to reconstruct the soul's learning timeline after a migration.

`test_ingested_at_set_for_procedural` verifies that procedural memories (skills and how-tos) also receive `ingested_at` — the field applies to all memory types, not just semantic facts.

### Serialization and Backward Compatibility
- `test_serialization_roundtrip` — `ingested_at` survives a JSON serialize/deserialize cycle without precision loss
- `test_backward_compat_no_ingested_at` — a soul file that was saved before this field existed (no `ingested_at` key in JSON) must deserialize cleanly with `ingested_at = None`. This prevents a `ValidationError` crash when loading older `.soul` archives.

## superseded Field (TestSupersededField)

The `superseded` flag marks facts that have been replaced by a newer, more accurate version (e.g., "works at Acme Corp" is superseded when "works at BetaCo" is added). Superseded memories are hidden from normal recall but retained for audit purposes.

- `test_default_is_false` — memories are active by default
- `test_set_to_true` — the flag can be set to True
- `test_backward_compat_no_superseded` — old soul files without the `superseded` key must deserialize to `False` (not raise an error)

## Spec Layer (TestSpecMemoryEntry)

The spec layer (`soul_protocol.spec.memory`) is the serialization schema that defines the `.soul` file format. These tests verify that `ingested_at` and `superseded` also exist in the spec layer with matching defaults and that spec-layer round-trips preserve both fields. This is important because the spec layer and runtime layer must stay in sync — divergence would cause silent data loss on save/load.

## Known Gaps

No TODOs flagged. There are no tests for the case where `ingested_at` is set to a timezone-naive datetime — potential issues with UTC vs. local time comparisons are not covered.