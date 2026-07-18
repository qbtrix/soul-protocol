# memory/graph_view.py — Public, ergonomic facade over KnowledgeGraph.
# Created: 2026-04-29 (#108, #190) — Wraps the existing KnowledgeGraph with
# a clean, typed surface used by Soul.graph, the ``soul graph`` CLI, and the
# ``soul_graph_query`` MCP tool. Keeps the storage class internal-only — all
# external consumers should reach for GraphView instead so future storage
# backends (on-disk index, networkx adapter) remain swappable.

from __future__ import annotations

from typing import TYPE_CHECKING

from soul_protocol.runtime.memory.graph_types import (
    GraphEdge,
    GraphNode,
    Subgraph,
    _render_mermaid,
)

if TYPE_CHECKING:
    from soul_protocol.runtime.memory.graph import KnowledgeGraph


class GraphView:
    """Read-mostly view of a soul's knowledge graph.

    Construct via ``soul.graph`` — GraphView is a thin adapter over the
    underlying :class:`KnowledgeGraph`. Mutations should go through
    :meth:`Soul.observe` (which runs the extractor pipeline) so trust chain
    entries get appended; direct edits are possible via the storage class
    but bypass auditing.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def nodes(
        self,
        *,
        type: str | None = None,  # noqa: A002 - public param name
        name_match: str | None = None,
        limit: int | None = None,
    ) -> list[GraphNode]:
        """Return nodes, optionally filtered by type / name substring / limit."""
        return self._graph.list_nodes(type=type, name_match=name_match, limit=limit)

    def edges(
        self,
        *,
        source: str | None = None,
        target: str | None = None,
        relation: str | None = None,
    ) -> list[GraphEdge]:
        """Return active edges, optionally filtered."""
        return self._graph.list_edges(source=source, target=target, relation=relation)

    def neighbors(
        self,
        node_id: str,
        depth: int = 1,
        types: list[str] | None = None,
    ) -> list[GraphNode]:
        """Return nodes reachable from ``node_id`` within ``depth`` hops.

        The starting node is always included as the first element with
        ``depth=0`` so callers can render it in the same view. ``types``
        filters non-source nodes by entity type.
        """
        return self._graph.neighbors_typed(node_id, depth=depth, types=types)

    def path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 4,
    ) -> list[GraphEdge] | None:
        """Shortest path BFS — list of edges from source to target, or None."""
        return self._graph.find_path_typed(source_id, target_id, max_depth=max_depth)

    def subgraph(self, node_ids: list[str]) -> Subgraph:
        """Extract the subgraph induced by ``node_ids``.

        Returns a :class:`Subgraph` containing only the requested nodes (in
        input order, skipping unknowns) plus every active edge whose source
        and target are both in the set.
        """
        keep = set(node_ids)
        nodes: list[GraphNode] = []
        for node in self._graph.list_nodes():
            if node.id in keep:
                nodes.append(node)
        # Reorder to match input
        order = {nid: i for i, nid in enumerate(node_ids)}
        nodes.sort(key=lambda n: order.get(n.id, len(order)))
        edges: list[GraphEdge] = []
        for edge in self._graph.list_edges():
            if edge.source in keep and edge.target in keep:
                edges.append(edge)
        return Subgraph(nodes=nodes, edges=edges)

    def to_mermaid(self) -> str:
        """Render the full graph as a Mermaid ``graph LR`` block."""
        return _render_mermaid(self.nodes(), self.edges())

    # ============ Walks (used by recall graph_walk) ============

    def reachable(
        self,
        start: str,
        depth: int = 2,
        edge_types: list[str] | None = None,
    ) -> dict[str, int]:
        """Return ``{node_id: hop_distance}`` for nodes reachable from ``start``.

        Used by the recall ``graph_walk`` parameter to gather entity names
        whose memories should be ranked. Edge-type filtering applies during
        traversal so a ``relation`` filter genuinely prunes the BFS frontier
        rather than just filtering the final node list.
        """
        if start not in self._graph._entities:
            return {}
        from collections import deque

        type_set: set[str] | None = set(edge_types) if edge_types else None
        seen: dict[str, int] = {start: 0}
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue
            for edge in self._graph._edges:
                if not edge.is_currently_active():
                    continue
                if edge.source == current:
                    nxt = edge.target
                elif edge.target == current:
                    nxt = edge.source
                else:
                    continue
                if type_set is not None and edge.relation not in type_set:
                    continue
                if nxt in seen:
                    continue
                seen[nxt] = d + 1
                queue.append((nxt, d + 1))
        return seen

    # ============ Stats ============

    def stats(self) -> dict:
        """Quick summary — node and edge counts plus type histograms."""
        nodes = self.nodes()
        edges = self.edges()
        type_hist: dict[str, int] = {}
        for n in nodes:
            type_hist[n.type] = type_hist.get(n.type, 0) + 1
        rel_hist: dict[str, int] = {}
        for e in edges:
            rel_hist[e.relation] = rel_hist.get(e.relation, 0) + 1
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "types": type_hist,
            "relations": rel_hist,
        }
