---
{
  "title": "Test Suite: Graph-Augmented Recall Pipeline",
  "summary": "Validates the integration of KnowledgeGraph with RecallEngine, covering graph traversal via progressive_context at multiple depth levels, graph-wired recall with entity matching, deduplication, and graceful degradation when no graph is provided.",
  "concepts": [
    "KnowledgeGraph",
    "RecallEngine",
    "progressive_context",
    "graph traversal",
    "entity matching",
    "memory deduplication",
    "MemoryManager",
    "graph-augmented recall",
    "depth traversal",
    "token overlap",
    "entity expansion"
  ],
  "categories": [
    "memory",
    "knowledge-graph",
    "testing",
    "recall",
    "test"
  ],
  "source_docs": [
    "33e7c13cc38fbf3f"
  ],
  "backlinks": null,
  "word_count": 462,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Graph-Augmented Recall Pipeline

This test module (`test_graph_recall.py`) verifies that the v0.4.0 graph-augmented recall pipeline behaves correctly end-to-end. The tests ensure that `KnowledgeGraph` traversal and `RecallEngine` cooperate to surface semantically related memories that naive keyword search would miss.

### Why Graph-Augmented Recall Exists

Standard recall relies on token overlap or BM25 scoring — a query for "FastAPI" won't surface memories tagged with "Pydantic" even though Pydantic is a direct dependency. The knowledge graph solves this by expanding a query's entity set to include graph neighbors, enabling contextual memory retrieval without requiring the user to know every connected term.

### TestProgressiveContext: Depth-Level Traversal

The `TestProgressiveContext` class exercises `KnowledgeGraph.progressive_context()` at depths 0, 1, and 2:

- **Level 0** — returns only the queried entity itself (direct facts only)
- **Level 1** — expands to immediate graph neighbors (one hop)
- **Level 2** — expands further (two hops), useful for discovering transitive relationships

The suite also verifies edge cases:
- Unknown entities return an empty context (no KeyError)
- Isolated entities with no relationships return empty at levels 1+
- Entries include a `depth` field for downstream ranking
- No entity is visited twice (cycle prevention via deduplication)

```python
@pytest.fixture
def graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    g.add_entity("Python", "language")
    g.add_entity("FastAPI", "framework")
    g.add_relationship("FastAPI", "Python", "built_with")
    return g
```

### TestGraphRecall: RecallEngine Integration

`TestGraphRecall` wires a `KnowledgeGraph` into `RecallEngine` and confirms:

- **Entity extraction from queries** — "Tell me about FastAPI" resolves `FastAPI` → expands to `Python`, `Pydantic`
- **Graph-connected memory surfacing** — memories about related entities (not just the queried one) are returned
- **Deduplication** — memories returned by both direct search and graph expansion are not duplicated
- **Limit enforcement** — `limit=N` is respected even when graph expansion would return more
- **Type filter compatibility** — `types=[MemoryType.SEMANTIC]` filters work alongside graph expansion
- **Min-importance filtering** — `min_importance` thresholds apply to graph-expanded results
- **Case-insensitive entity matching** — "fastapi" matches the graph node stored as "FastAPI"

### Graceful Degradation

Three tests cover the no-graph scenario:
- `test_recall_without_graph_param` — `RecallEngine` called without a `graph=` argument still returns results
- `test_recall_no_graph_object` — A fixture that builds `RecallEngine` with no graph wired in
- `test_recall_empty_graph` — An empty `KnowledgeGraph()` with no entities or edges

All three cases must return sensible results (no crash, no KeyError) because graph support is additive — existing deployments without a knowledge graph should be unaffected.

### MemoryManager Integration

`test_manager_recall_uses_graph` confirms the high-level `MemoryManager.recall()` façade properly propagates the graph through to the underlying `RecallEngine`, so callers don't need to reach past the manager layer.

### Known Gaps

No explicit TODO or FIXME markers in the source, but the test coverage focuses on a pre-built static graph. Dynamic graph construction (auto-extraction of entities from incoming interactions) is tested elsewhere in the cognitive engine suite.
