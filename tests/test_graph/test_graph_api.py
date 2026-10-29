# test_graph/test_graph_api.py — Tests for GraphView (the public read API).
# Created: 2026-04-29 (#190) — Round-trips for nodes(), edges(), neighbors(),
# path(), subgraph(), to_mermaid(). Validates the GraphView is the canonical
# read surface used by Soul.graph, the CLI, and the MCP tool.

from __future__ import annotations

import pytest

from soul_protocol import GraphView, Subgraph
from soul_protocol.runtime.memory.graph import KnowledgeGraph


@pytest.fixture
def small_graph() -> KnowledgeGraph:
    """A 4-node graph with mixed types and a path A -> B -> C -> D."""
    g = KnowledgeGraph()
    g.add_entity("A", "person")
    g.add_entity("B", "person")
    g.add_entity("C", "org")
    g.add_entity("D", "tool")
    g.add_relationship("A", "B", "mentions", weight=0.8)
    g.add_relationship("B", "C", "owned_by", weight=0.9)
    g.add_relationship("C", "D", "depends_on")
    return g


@pytest.fixture
def view(small_graph: KnowledgeGraph) -> GraphView:
    return GraphView(small_graph)


# ============ nodes() ============


class TestNodes:
    def test_returns_all_nodes(self, view: GraphView) -> None:
        nodes = view.nodes()
        assert len(nodes) == 4
        assert {n.id for n in nodes} == {"A", "B", "C", "D"}

    def test_filter_by_type(self, view: GraphView) -> None:
        nodes = view.nodes(type="person")
        assert {n.id for n in nodes} == {"A", "B"}

    def test_filter_by_name_match(self, view: GraphView) -> None:
        nodes = view.nodes(name_match="a")
        assert {n.id for n in nodes} == {"A"}

    def test_limit(self, view: GraphView) -> None:
        nodes = view.nodes(limit=2)
        assert len(nodes) == 2

    def test_node_has_default_name(self, view: GraphView) -> None:
        nodes = view.nodes()
        for node in nodes:
            assert node.name == node.id


# ============ edges() ============


class TestEdges:
    def test_returns_all_active_edges(self, view: GraphView) -> None:
        edges = view.edges()
        assert len(edges) == 3

    def test_filter_by_source(self, view: GraphView) -> None:
        edges = view.edges(source="A")
        assert len(edges) == 1
        assert edges[0].target == "B"

    def test_filter_by_target(self, view: GraphView) -> None:
        edges = view.edges(target="C")
        assert len(edges) == 1
        assert edges[0].source == "B"

    def test_filter_by_relation(self, view: GraphView) -> None:
        edges = view.edges(relation="depends_on")
        assert len(edges) == 1
        assert edges[0].source == "C"

    def test_combined_filter(self, view: GraphView) -> None:
        edges = view.edges(source="B", relation="owned_by")
        assert len(edges) == 1
        assert edges[0].target == "C"

    def test_weight_round_trips(self, view: GraphView) -> None:
        edges = view.edges(source="A")
        assert edges[0].weight == 0.8

    def test_no_filter_returns_active_only(self, small_graph: KnowledgeGraph) -> None:
        # Expire one edge — it shouldn't show up in list_edges
        small_graph.expire_relationship("A", "B", "mentions")
        v = GraphView(small_graph)
        edges = v.edges()
        assert len(edges) == 2


# ============ neighbors() ============


class TestNeighbors:
    def test_depth_zero_returns_just_source(self, view: GraphView) -> None:
        neighbors = view.neighbors("A", depth=0)
        assert len(neighbors) == 1
        assert neighbors[0].id == "A"

    def test_depth_one(self, view: GraphView) -> None:
        neighbors = view.neighbors("A", depth=1)
        ids = {n.id for n in neighbors}
        # A and B (1 hop)
        assert ids == {"A", "B"}

    def test_depth_two(self, view: GraphView) -> None:
        neighbors = view.neighbors("A", depth=2)
        ids = {n.id for n in neighbors}
        assert ids == {"A", "B", "C"}

    def test_depth_three(self, view: GraphView) -> None:
        neighbors = view.neighbors("A", depth=3)
        ids = {n.id for n in neighbors}
        assert ids == {"A", "B", "C", "D"}

    def test_neighbors_carry_depth(self, view: GraphView) -> None:
        neighbors = view.neighbors("A", depth=2)
        depths = {n.id: n.depth for n in neighbors}
        assert depths["A"] == 0
        assert depths["B"] == 1
        assert depths["C"] == 2

    def test_unknown_source_returns_empty(self, view: GraphView) -> None:
        assert view.neighbors("nonexistent") == []

    def test_type_filter(self, view: GraphView) -> None:
        neighbors = view.neighbors("A", depth=3, types=["person", "tool"])
        # Only person and tool nodes (B and D), plus the source A itself
        ids = {n.id for n in neighbors}
        assert "A" in ids  # Source is always included
        assert "B" in ids
        assert "D" in ids
        assert "C" not in ids  # org type is filtered out


# ============ path() ============


class TestPath:
    def test_finds_direct_edge(self, view: GraphView) -> None:
        path = view.path("A", "B")
        assert path is not None
        assert len(path) == 1
        assert path[0].source == "A"
        assert path[0].target == "B"

    def test_finds_multi_hop(self, view: GraphView) -> None:
        path = view.path("A", "D")
        assert path is not None
        assert len(path) == 3
        # Endpoints check (graph is undirected for path-finding via
        # _active_neighbors, so the chain may use either direction)
        assert {edge.source for edge in path} | {edge.target for edge in path} == {
            "A",
            "B",
            "C",
            "D",
        }

    def test_zero_length_path_for_same_endpoint(self, view: GraphView) -> None:
        path = view.path("A", "A")
        assert path == []

    def test_no_path_returns_none(self, view: GraphView) -> None:
        # Add an isolated node
        view._graph.add_entity("Z", "person")
        path = view.path("A", "Z")
        assert path is None

    def test_unknown_endpoint_returns_none(self, view: GraphView) -> None:
        assert view.path("A", "nonexistent") is None
        assert view.path("nonexistent", "A") is None

    def test_max_depth_truncates(self, view: GraphView) -> None:
        # max_depth=1 means we can only go one hop
        path = view.path("A", "D", max_depth=1)
        assert path is None  # D is 3 hops away


# ============ subgraph() ============


class TestSubgraph:
    def test_subgraph_keeps_only_requested_nodes(self, view: GraphView) -> None:
        sub = view.subgraph(["A", "B"])
        assert isinstance(sub, Subgraph)
        assert {n.id for n in sub.nodes} == {"A", "B"}

    def test_subgraph_keeps_only_internal_edges(self, view: GraphView) -> None:
        sub = view.subgraph(["A", "B"])
        # Only A-B edge should appear, not B-C
        assert len(sub.edges) == 1
        assert sub.edges[0].target == "B"

    def test_subgraph_skips_unknown_ids(self, view: GraphView) -> None:
        sub = view.subgraph(["A", "B", "ghost"])
        assert {n.id for n in sub.nodes} == {"A", "B"}

    def test_subgraph_input_order_preserved(self, view: GraphView) -> None:
        sub = view.subgraph(["B", "A"])
        # Order matches input
        assert [n.id for n in sub.nodes] == ["B", "A"]


# ============ to_mermaid() ============


class TestToMermaid:
    def test_renders_graph_lr_block(self, view: GraphView) -> None:
        out = view.to_mermaid()
        assert out.startswith("graph LR")

    def test_includes_all_nodes(self, view: GraphView) -> None:
        out = view.to_mermaid()
        for node in ("A", "B", "C", "D"):
            assert node in out

    def test_includes_all_edges(self, view: GraphView) -> None:
        out = view.to_mermaid()
        assert "mentions" in out
        assert "owned_by" in out
        assert "depends_on" in out

    def test_subgraph_to_mermaid(self, view: GraphView) -> None:
        sub = view.subgraph(["A", "B"])
        out = sub.to_mermaid()
        assert out.startswith("graph LR")
        assert "mentions" in out
        # Edges to nodes outside the subgraph are dropped
        assert "owned_by" not in out

    def test_special_chars_in_name_are_sanitized(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("Hello World", "person")
        g.add_entity("foo:bar", "tool")
        g.add_relationship("Hello World", "foo:bar", "uses")
        v = GraphView(g)
        out = v.to_mermaid()
        # Sanitized IDs use underscores; labels keep originals
        assert "Hello_World" in out
        assert '"Hello World :: person"' in out


# ============ stats() ============


class TestStats:
    def test_node_and_edge_counts(self, view: GraphView) -> None:
        s = view.stats()
        assert s["node_count"] == 4
        assert s["edge_count"] == 3

    def test_type_histogram(self, view: GraphView) -> None:
        s = view.stats()
        assert s["types"] == {"person": 2, "org": 1, "tool": 1}

    def test_relation_histogram(self, view: GraphView) -> None:
        s = view.stats()
        assert s["relations"] == {"mentions": 1, "owned_by": 1, "depends_on": 1}
