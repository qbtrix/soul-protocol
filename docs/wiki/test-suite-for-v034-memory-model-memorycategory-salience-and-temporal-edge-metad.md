---
{
  "title": "Test Suite for v0.3.4 Memory Model: MemoryCategory, Salience, and Temporal Edge Metadata",
  "summary": "This test suite covers spec-level additions introduced in Soul Protocol v0.3.4: the `MemoryCategory` enum for classifying memory entries, `salience` as an additive activation boost on `MemoryEntry`, and `metadata` on `TemporalEdge` along with its surfacing through `KnowledgeGraph` query methods. The salience tests were rewritten from a multiplicative to an additive boost model to prevent low-importance memories from being penalized disproportionately.",
  "concepts": [
    "MemoryCategory",
    "salience",
    "activation boost",
    "additive boost",
    "TemporalEdge",
    "KnowledgeGraph",
    "MemoryEntry",
    "compute_activation",
    "StrEnum",
    "memory classification"
  ],
  "categories": [
    "testing",
    "memory-model",
    "knowledge-graph",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "7d69420b42647132"
  ],
  "backlinks": null,
  "word_count": 563,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Version 0.3.4 extended the core memory data model with three closely related capabilities: categorical classification of memories, a salience score that adjusts how likely a memory is to surface in recall, and contextual metadata attached to knowledge graph edges. This test file validates all three.

## MemoryCategory Enum

The `MemoryCategory` enum classifies memories into seven semantic types:

```python
assert MemoryCategory.PROFILE == "profile"
assert MemoryCategory.PREFERENCE == "preference"
assert MemoryCategory.ENTITY == "entity"
assert MemoryCategory.EVENT == "event"
assert MemoryCategory.CASE == "case"
assert MemoryCategory.PATTERN == "pattern"
assert MemoryCategory.SKILL == "skill"
```

Being a `StrEnum` means the category value passes through JSON serialization as a plain string, which avoids a class of bugs where enum members do not serialize correctly and require custom encoders.

## Salience as Additive Activation Boost

### Why Salience Exists

Not all memories are equally worth surfacing. A fact the user repeats frequently should rank higher than a one-off mention, even if both have the same importance score. `salience` is a `float` in `[0.0, 1.0]` defaulting to `0.5` (neutral) that shifts the `compute_activation` score additively by up to ±0.25.

### Additive vs. Multiplicative

The critical design decision — documented in the test comments — is that the boost is **additive**, not multiplicative. The earlier multiplicative model amplified penalties: a low-importance memory (negative base activation) multiplied by a low salience score produced a very large negative activation, making the memory nearly unreachable even with a relevant query. The rewrite ensures:

```
boost = (salience - 0.5) * 0.5  # range: -0.25 to +0.25
activation = base + boost
```

Key properties tested:

- `salience=0.5` (neutral) applies zero boost — existing behavior is unchanged.
- `salience=1.0` always scores higher than `salience=0.0` for identical content.
- High salience on a **low-importance** memory (negative base) still **improves** activation rather than amplifying the penalty.
- The total range of salience effect is exactly 0.5 (from −0.25 to +0.25).

```python
# Range test
assert max_score - min_score == pytest.approx(0.5, abs=0.01)
```

Pydantic validation enforces bounds:

```python
with pytest.raises(ValidationError):
    MemoryEntry(type=MemoryType.SEMANTIC, content="x", salience=-0.1)
```

## TemporalEdge Metadata

### Purpose

A `TemporalEdge` in the `KnowledgeGraph` represents a relationship between two named entities over a time range. Metadata provides provenance context (`why` this edge exists) that cannot be expressed through the source/target/relation triple alone:

```python
edge = TemporalEdge(source="A", target="B", relation="knows",
                   metadata={"context": "met at conference", "confidence": 0.9})
```

### Serialization Behavior

Two specific behaviors are tested for `to_dict()` / `from_dict()`:

- Metadata is **included** in the dict when present.
- Metadata is **omitted entirely** (key not present) when `None`, keeping serialized edges lean for storage.

### Query Method Surfacing

Metadata must flow through all three graph query methods — `get_related()`, `as_of_date()`, and `relationship_evolution()` — so callers do not need to perform secondary lookups. The tests confirm metadata appears in results when set and is absent when not set:

```python
results = g.get_related("Alice")
assert results[0]["metadata"] == {"since": "2024"}

# When no metadata:
assert "metadata" not in results[0]
```

## Known Gaps

- There is no test for `category` and `abstract` fields surviving a `.soul` zip roundtrip — the model-level roundtrip is tested but integration with `pack_soul`/`unpack_soul` is not.
- The `overview` field on `MemoryEntry` has no tests beyond basic assignment and JSON roundtrip — no tests validate its role in recall ranking.
- Metadata on `TemporalEdge` is a raw dict with no schema enforcement, which could allow silent type drift between writes and reads.