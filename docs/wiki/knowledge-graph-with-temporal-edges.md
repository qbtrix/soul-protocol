---
{
  "title": "Knowledge Graph with Temporal Edges",
  "summary": "Implements `KnowledgeGraph` and `TemporalEdge` — a lightweight entity-relationship store with time-bounded validity, multi-hop traversal, shortest-path search, and progressive context loading for recall augmentation.",
  "concepts": [
    "knowledge graph",
    "TemporalEdge",
    "entity relationships",
    "graph traversal",
    "BFS",
    "progressive context",
    "valid_from valid_to",
    "shortest path",
    "GDPR entity deletion",
    "recall augmentation"
  ],
  "categories": [
    "memory",
    "knowledge-graph",
    "soul-protocol-core"
  ],
  "source_docs": [
    "dcf75c72be87d447"
  ],
  "backlinks": null,
  "word_count": 321,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Flat memory stores (episodic, semantic) cannot capture relationships between entities — that "Alice reports to Bob" or that "User worked at Acme from 2022 to 2024". The `KnowledgeGraph` stores these as directed, time-bounded edges, enabling graph-augmented recall where related entities surface alongside directly matched memories.

## TemporalEdge

```python
class TemporalEdge:
    source: str
    target: str
    relation: str
    valid_from: datetime
    valid_to: datetime | None  # None = currently active
    metadata: dict | None
```

`valid_to=None` means the relationship is still active. When an edge is superseded (e.g., user changes employer), the old edge's `valid_to` is set and a new edge is created. This preserves relationship history without deleting facts.

## Deduplication Guard

`add_relationship()` checks for an existing active edge with the same `(source, target, relation)` tuple before inserting. This prevents duplicate edges from accumulating when the same relationship is observed repeatedly.

## Traversal Methods

- **`traverse(start, max_depth)`** — BFS from a start entity, returns all reachable entities within depth
- **`shortest_path(source, target)`** — BFS to find the minimum hop path between two entities
- **`get_neighborhood(entity, depth)`** — returns all edges within N hops
- **`subgraph(entities)`** — extracts the induced subgraph for a given entity set

## Progressive Context Loading

`progressive_context(entity, depth)` returns a list of dicts structured for incremental recall augmentation:

```python
[
    {"depth": 0, "entity": "Alice", "edges": [...]},
    {"depth": 1, "entity": "Bob", "edges": [...]},
]
```

The `format_context()` method (renamed from the duplicate `progressive_context()` string version) formats this as human-readable text for LLM injection. The naming conflict (two methods with the same name) was caught and fixed in `fix/graph-progressive-context-conflict`.

## GDPR Compliance

`remove_entity()` deletes the entity from `_entities` and removes all edges where the entity appears as source or target.

## Known Gaps

- The graph is stored entirely in-memory as Python lists/dicts — no index structure, so edge lookups are O(n) scans.
- No cycle detection in traversal — graphs with self-referential relationships could cause unexpected behavior in `shortest_path()`.