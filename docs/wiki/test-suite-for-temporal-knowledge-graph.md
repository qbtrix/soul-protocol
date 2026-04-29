---
{
  "title": "Test Suite for Temporal Knowledge Graph",
  "summary": "This test suite validates the temporal knowledge graph (`KnowledgeGraph` and `TemporalEdge`) used by Soul Protocol to represent relationships between entities over time. It covers edge creation, time-range activation queries, relationship expiration, duplicate deduplication, point-in-time queries, evolution history, serialization roundtrips, and backward compatibility with older edge formats.",
  "concepts": [
    "KnowledgeGraph",
    "TemporalEdge",
    "temporal relationships",
    "is_active_at",
    "as_of_date",
    "relationship_evolution",
    "get_related",
    "expire_relationship",
    "backward compatibility",
    "point-in-time query"
  ],
  "categories": [
    "testing",
    "knowledge-graph",
    "memory-system",
    "temporal-reasoning",
    "test"
  ],
  "source_docs": [
    "78003e3fb9aec2b0"
  ],
  "backlinks": null,
  "word_count": 519,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul Protocol's knowledge graph stores more than just entity relationships — it stores *when* those relationships were true. A soul might know that "Alice works at Acme" from 2024 to 2025, and then "Alice works at Nova" from 2025 onward. The `KnowledgeGraph` / `TemporalEdge` pair makes these time-bounded relationships queryable with point-in-time semantics.

## TemporalEdge

### Default Timestamps

```python
edge = TemporalEdge("Alice", "Python", "uses")
assert edge.valid_from is not None
assert edge.valid_to is None
```

`valid_from` defaults to the creation timestamp; `valid_to` defaults to `None` (still active). This means every newly created edge is immediately active, which is the expected behavior for relationships discovered in real-time from interactions.

### Temporal Activation Checks

Four boundary cases are tested for `is_active_at(timestamp)`:

- Within range: `True`
- Before start: `False`
- After end: `False`
- No end (open-ended): `True` for any future date

The open-ended case prevents a common bug where code treats `valid_to=None` as "expired at epoch" rather than "still active."

### Serialization

```python
data = edge.to_dict()
restored = TemporalEdge.from_dict(data)
assert restored.valid_from == t0
assert restored.valid_to == t1
```

Datetime fields must survive the dict roundtrip with exact equality — not just approximately equal — because point-in-time queries use strict comparison.

## Graph Operations

### Duplicate Deduplication

```python
graph.add_relationship("Alice", "Python", "uses")
graph.add_relationship("Alice", "Python", "uses")  # duplicate
related = graph.get_related("Alice")
assert len(related) == 1
```

Duplicate active edges are silently ignored. Without this guard, repeated processing of the same interaction event would accumulate phantom relationship duplicates.

### Expire Then Re-Add

Expiring a relationship and then adding a new one for the same triple creates two distinct edges — one historical, one active:

```python
graph.expire_relationship("Alice", "Python", "uses", expire_at=t1)
graph.add_relationship("Alice", "Python", "uses", valid_from=t1)
related = graph.get_related("Alice")          # 1 (only active)
evolution = graph.relationship_evolution("Alice", "Python")  # 2 (all)
```

This separation is intentional: `get_related()` gives the current state; `relationship_evolution()` gives the history.

## Point-in-Time Queries

`as_of_date(timestamp)` returns all edges that were active at that moment:

```python
feb = graph.as_of_date(datetime(2026, 2, 1))
assert feb[0]["target"] == "Python"  # Python relationship active in Feb

apr = graph.as_of_date(datetime(2026, 4, 1))
assert apr[0]["target"] == "Rust"    # Rust relationship active in April
```

This is the core capability that distinguishes the temporal graph from a plain adjacency list.

## Relationship Evolution

`relationship_evolution(source, target)` returns all edges between two nodes sorted by `valid_from`. This allows reconstructing the history of how a relationship changed over time:

```python
assert evolution[0]["relation"] == "friends"
assert evolution[1]["relation"] == "colleagues"
assert evolution[2]["relation"] == "partners"
```

## Backward Compatibility

`test_backward_compat_old_format` feeds the graph an old-format edge dict without `valid_from` or `valid_to` fields:

```python
old_data = {"source": "Alice", "target": "Bob", "relation": "knows"}
restored = KnowledgeGraph.from_dict({"edges": [old_data]})
related = restored.get_related("Alice")
assert len(related) == 1
```

This is a deliberate defensive pattern: souls serialized before the temporal fields were added must still load correctly.

## Known Gaps

- There is no test for `expire_relationship()` with an explicit `expire_at` timestamp — all expiration tests use the default (now).
- Cross-entity queries ("find all relationships active in February for all entities") are not tested.
- The graph does not appear to test what happens when `valid_from > valid_to` — an inverted time range.