---
{
  "title": "Test Suite: Context Spec Models -- Pydantic Schemas for Conversation Context",
  "summary": "Tests for the Pydantic models that define Soul Protocol's conversation context data layer, including `CompactionLevel` enum, `ContextMessage`, `ContextNode`, and the result types (`AssembleResult`, `GrepResult`, `ExpandResult`, `DescribeResult`). Validates defaults, serialization round-trips, unique ID generation, and string-enum comparability.",
  "concepts": [
    "CompactionLevel",
    "ContextMessage",
    "ContextNode",
    "AssembleResult",
    "GrepResult",
    "ExpandResult",
    "DescribeResult",
    "Pydantic",
    "StrEnum",
    "serialization round-trip",
    "default_factory",
    "context models",
    "schema contract"
  ],
  "categories": [
    "testing",
    "data models",
    "context management",
    "Pydantic",
    "test"
  ],
  "source_docs": [
    "4e58392a184ac3c6"
  ],
  "backlinks": null,
  "word_count": 414,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_context_models.py` validates the Pydantic data models at the core of Soul Protocol's context management system. These models are the shared language between the context store, the compaction engine, and the CLI. If their defaults, serialization, or validation behavior changes unexpectedly, every layer that touches context data breaks. The tests act as a schema contract.

## CompactionLevel Enum

```python
class TestCompactionLevel:
    def test_values(self):
        assert CompactionLevel.VERBATIM == "verbatim"
        assert CompactionLevel.SUMMARY == "summary"
        assert CompactionLevel.BULLETS == "bullets"
        assert CompactionLevel.TRUNCATED == "truncated"

    def test_is_str_enum(self):
        assert isinstance(CompactionLevel.VERBATIM, str)

    def test_all_levels_exist(self):
        assert len(CompactionLevel) == 4
```

The `StrEnum` inheritance is intentional: it allows `CompactionLevel` values to be used directly in string comparisons and JSON serialization without calling `.value`. The count assertion prevents silent additions of new levels without updating the test.

## ContextMessage

`ContextMessage` represents a single turn in a conversation. Tests verify:

- **Defaults**: `id` is auto-generated UUID, `timestamp` defaults to now, `token_count` defaults to 0
- **Custom fields**: all fields can be overridden
- **Unique IDs**: two messages created without explicit IDs get different UUIDs
- **Serialization round-trip**: `model_dump()` then reconstruct produces an equal object

The unique-ID test catches a class of bug where the default factory is shared across instances (e.g., using a mutable default instead of a `default_factory`).

## ContextNode

`ContextNode` represents a compaction artifact -- a summary, bullet list, or truncated placeholder that replaces a range of original messages. Tests verify:

- **Defaults**: `node_id` auto-generated, `level` defaults to `VERBATIM`, `children` defaults to empty list
- **Summary node construction**: populated `children` list, `seq_start`/`seq_end` range set correctly
- **Serialization round-trip**: Pydantic round-trip preserves all fields including nested structures

## Result Types

Four result types are validated for their defaults and construction:

| Type | Purpose | Key Fields |
|------|---------|------------|
| `AssembleResult` | Output of context assembly | `messages`, `nodes`, `total_tokens` |
| `GrepResult` | Search results from context | `matches`, `pattern` |
| `ExpandResult` | Expansion of a compacted node | `messages`, `node_id` |
| `DescribeResult` | Statistical summary of context | `message_count`, `token_count`, compaction stats |

Each result type defaults to empty/zero values so callers can safely access fields without null checks.

## Why These Tests Matter

Pydantic models are frequently modified during feature development. A field renamed, a default changed, or an enum value added can break serialized data stored in `.soul` files or returned from the context store. These tests are the regression gate that ensures model changes are intentional.

## Known Gaps

No TODOs flagged. Suite was introduced at v0.3.0.