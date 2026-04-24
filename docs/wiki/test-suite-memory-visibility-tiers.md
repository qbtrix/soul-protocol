---
{
  "title": "Test Suite: Memory Visibility Tiers",
  "summary": "Tests for the three-tier memory visibility system (PUBLIC, BONDED, PRIVATE) that controls which memories are accessible to external requesters based on bond strength, preventing private memories from leaking while maintaining full system access for the soul itself.",
  "concepts": [
    "MemoryVisibility",
    "PUBLIC",
    "BONDED",
    "PRIVATE",
    "filter_by_visibility",
    "bond_score",
    "DEFAULT_BOND_THRESHOLD",
    "access control",
    "memory privacy",
    "requester_id",
    "backward compatibility"
  ],
  "categories": [
    "privacy",
    "memory",
    "testing",
    "access-control",
    "test"
  ],
  "source_docs": [
    "2cac8ff7a17832a9"
  ],
  "backlinks": null,
  "word_count": 445,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Memory Visibility Tiers

`test_memory_visibility.py` validates the memory visibility access control system introduced in issue #97 (`feat/memory-visibility-templates`). The suite ensures that a soul's memories are selectively disclosed based on the requester's bond strength — a core privacy primitive for multi-platform soul deployment.

### Why Visibility Tiers?

A soul deployed on a public platform may receive queries from strangers, acquaintances, and deeply bonded users. Without visibility controls, all requesters would see all memories — including sensitive personal context that should only be shared with trusted parties. The three tiers map to natural relationship boundaries:

| Tier | Access | Use Case |
|------|--------|----------|
| `PUBLIC` | Always visible | Greetings, persona description, public facts |
| `BONDED` | Visible above bond threshold | Personal preferences, relationship history |
| `PRIVATE` | Soul/system only | Raw emotional state, private confessions |

### MemoryVisibility Enum

```python
assert MemoryVisibility.PUBLIC == "public"
assert MemoryVisibility.BONDED == "bonded"
assert MemoryVisibility.PRIVATE == "private"
```

`TestMemoryVisibilityEnum` verifies the three values, their string representations, and that string coercion works for deserialization from JSON.

### Backward Compatibility

`TestMemoryEntryVisibility` confirms that `MemoryEntry` objects created without a `visibility` field (old data) default to `BONDED`. This preserves existing behavior — memories from before the visibility feature was added remain accessible to bonded users without a migration step.

### filter_by_visibility

`TestFilterByVisibility` exercises the core access control function:

```python
filter_by_visibility(entries, requester_id=None)           # system — sees everything
filter_by_visibility(entries, requester_id="x", bond=0.9)  # bonded user — sees PUBLIC + BONDED
filter_by_visibility(entries, requester_id="x", bond=0.2)  # stranger — sees PUBLIC only
```

Key invariants tested:
- `requester_id=None` (system context) sees all tiers including PRIVATE
- PUBLIC memories are always visible regardless of bond score
- PRIVATE memories are never visible to external requesters (any non-None `requester_id`)
- BONDED memories require `bond_score >= DEFAULT_BOND_THRESHOLD` (default 0.5)
- Exact threshold is inclusive (bond == 0.5 grants access)
- Zero bond threshold exposes PUBLIC + BONDED to everyone (edge case for open platforms)
- Empty entry list returns empty without error

### RecallEngine Integration

`TestSoulRecallVisibility` tests visibility filtering through the full `RecallEngine.recall()` path:

```python
await recall_engine.recall(query, requester_id="external", bond_score=0.3)
# → only PUBLIC entries returned
```

This confirms that the `requester_id` and `bond_score` parameters flow correctly from the API surface down to `filter_by_visibility`.

### Spec-Level Validation

`TestSpecMemoryVisibility` verifies that the spec-layer `MemoryEntry` (in `soul_protocol.spec.memory`) also carries the visibility field with correct enum values, keeping the spec and runtime models in sync.

### Known Gaps

There is no test for visibility changes on an existing entry (migrating a BONDED memory to PRIVATE post-creation). The `remember()` API defaults to `BONDED` if no visibility is specified, but there is no enforcement that memories cannot be downgraded from PRIVATE after the fact.
