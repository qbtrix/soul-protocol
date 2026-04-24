---
{
  "title": "Test Suite for Knowledge Graph Traversal",
  "summary": "Tests for the `KnowledgeGraph` traversal API, covering BFS traversal, shortest-path finding, neighbourhood extraction, subgraph extraction, and progressive context rendering at three detail levels. Validates edge expiry, cycle handling, and node deduplication across a range of graph topologies.",
  "concepts": [
    "KnowledgeGraph",
    "BFS traversal",
    "shortest path",
    "neighbourhood",
    "subgraph",
    "progressive context",
    "edge expiry",
    "cycle handling",
    "node deduplication",
    "entity",
    "depth",
    "max_nodes",
    "active_neighbors",
    "graph topology",
    "context rendering"
  ],
  "categories": [
    "testing",
    "knowledge-graph",
    "traversal",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "f56b02b0a630bd09"
  ],
  "backlinks": null,
  "word_count": 452,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul Protocol's knowledge graph stores relationships between named entities (people, places, concepts). `test_graph_traversal.py` validates every traversal primitive that turns raw graph data into structured context for an AI agent.

## Test Graph Fixtures

Four fixtures provide controlled topologies:

| Fixture | Shape | Purpose |
|---|---|---|
| `graph` | Empty | Base case and edge-expiry tests |
| `linear_graph` | A→B→C→D | BFS ordering, depth control, shortest path |
| `star_graph` | Hub→5 spokes | Fan-out, node cap |
| `rich_graph` | Multiple paths, typed nodes | Metadata, alternative routes, cycles |

## BFS Traversal (`TestTraverse`)

`traverse()` performs breadth-first search from a start entity, returning nodes up to a configurable depth.

- **Depth control** — `test_linear_depth_0` returns only the start node; depth 3 reaches all nodes in a four-node chain.
- **Node cap** — `test_max_nodes_limit` verifies the traversal respects `max_nodes` to prevent runaway expansion on dense graphs.
- **BFS order** — `test_bfs_order` asserts nodes are returned in level order, not random order.
- **Cycle safety** — `test_handles_cycles` confirms traversal terminates on cyclic graphs. Without this guard a cycle would cause infinite recursion.
- **No revisit** — `test_does_not_revisit_nodes` ensures nodes seen via one path are not returned again via another.

## Shortest Path (`TestShortestPath`)

- Same-node path returns a single-element list.
- Direct and multi-hop paths return the correct node sequence.
- `test_reverse_direction` checks that directionality is respected.
- `test_no_path`, `test_missing_source`, `test_missing_target`, `test_both_missing` all return `None` or an empty result rather than raising, so callers can handle the missing-path case cleanly.
- `test_shortest_among_alternatives` verifies the algorithm picks the fewest-hop route when multiple paths exist.
- Expired edges are ignored: `test_ignores_expired_edges` confirms that edge TTL is checked during pathfinding.

## Neighbourhood (`TestActiveNeighbors`)

`active_neighbors()` returns nodes connected to an entity by non-expired edges:

- Unknown entities return empty results.
- Outgoing and incoming neighbours are returned based on direction.
- Expired edges are excluded.
- Multiple edges between the same pair produce only one neighbour entry (`test_no_duplicates`), preventing inflated context.

## Subgraph Extraction (`TestSubgraph`)

Returns the induced subgraph over a given entity list — only edges where both endpoints are in the list. Expired edges are excluded. Missing entities are filtered rather than raising.

## Progressive Context (`TestProgressiveContext`)

Three verbosity levels for injecting graph context into prompts:

- **L0** — entity name only.
- **L1** — name + direct relationships.
- **L2** — full neighbourhood with metadata, relationship section, and neighbour types. Neighbours are capped at 10 in L2 output to keep prompts tractable.

`test_level_2_multiline` checks that multi-line metadata renders correctly, preventing prompt injection via newlines in entity metadata.

## Known Gaps

- No tests for weighted shortest path (current implementation appears unweighted).
- No performance tests for large graphs (thousands of nodes).