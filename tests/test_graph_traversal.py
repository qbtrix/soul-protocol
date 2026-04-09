# test_graph_traversal.py — Tests for graph traversal methods and progressive context.
# Created: 2026-03-22 — Covers traverse(), shortest_path(), get_neighborhood(),
#   subgraph(), format_context(), and _active_neighbors() on KnowledgeGraph.

from __future__ import annotations

import pytest

from soul_protocol.runtime.memory.graph import KnowledgeGraph

# ============ Fixtures ============


@pytest.fixture
def graph() -> KnowledgeGraph:
    return KnowledgeGraph()


@pytest.fixture
def linear_graph() -> KnowledgeGraph:
    """A -> B -> C -> D (linear chain)."""
    g = KnowledgeGraph()
    g.add_entity("A", "node")
    g.add_entity("B", "node")
    g.add_entity("C", "node")
    g.add_entity("D", "node")
    g.add_relationship("A", "B", "connects")
    g.add_relationship("B", "C", "connects")
    g.add_relationship("C", "D", "connects")
    return g


@pytest.fixture
def star_graph() -> KnowledgeGraph:
    """Hub connected to 5 spokes."""
    g = KnowledgeGraph()
    g.add_entity("Hub", "center")
    for i in range(5):
        name = f"Spoke{i}"
        g.add_entity(name, "leaf")
        g.add_relationship("Hub", name, "links")
    return g


@pytest.fixture
def rich_graph() -> KnowledgeGraph:
    """A graph with types, metadata, and multiple paths."""
    g = KnowledgeGraph()
    g.add_entity("Alice", "person")
    g.add_entity("Bob", "person")
    g.add_entity("Python", "technology")
    g.add_entity("Rust", "technology")
    g.add_entity("ACME", "company")
    g.add_relationship(
        "Alice", "Python", "uses", metadata={"context": "Primary language", "confidence": 0.9}
    )
    g.add_relationship("Alice", "ACME", "works_at")
    g.add_relationship("Bob", "Python", "uses")
    g.add_relationship("Bob", "Rust", "uses")
    g.add_relationship("Bob", "ACME", "works_at")
    g.add_relationship("ACME", "Python", "uses")
    return g


# ============ _active_neighbors ============


class TestActiveNeighbors:
    def test_no_neighbors_for_unknown_entity(self, graph: KnowledgeGraph):
        assert graph._active_neighbors("nonexistent") == []

    def test_outgoing_neighbors(self, linear_graph: KnowledgeGraph):
        neighbors = linear_graph._active_neighbors("A")
        assert "B" in neighbors

    def test_incoming_neighbors(self, linear_graph: KnowledgeGraph):
        neighbors = linear_graph._active_neighbors("B")
        assert "A" in neighbors
        assert "C" in neighbors

    def test_excludes_expired_edges(self, graph: KnowledgeGraph):
        graph.add_entity("X", "node")
        graph.add_entity("Y", "node")
        graph.add_relationship("X", "Y", "links")
        graph.expire_relationship("X", "Y", "links")
        assert graph._active_neighbors("X") == []

    def test_no_duplicates(self, graph: KnowledgeGraph):
        """Multiple edges between same pair should not duplicate neighbors."""
        graph.add_entity("X", "node")
        graph.add_entity("Y", "node")
        # Expire first, add another with different relation
        graph.add_relationship("X", "Y", "links")
        graph.expire_relationship("X", "Y", "links")
        graph.add_relationship("X", "Y", "knows")
        graph.add_relationship("Y", "X", "knows")
        neighbors = graph._active_neighbors("X")
        assert neighbors.count("Y") == 1


# ============ traverse ============


class TestTraverse:
    def test_empty_graph(self, graph: KnowledgeGraph):
        assert graph.traverse("nonexistent") == []

    def test_single_node(self, graph: KnowledgeGraph):
        graph.add_entity("Alone", "node")
        result = graph.traverse("Alone")
        assert len(result) == 1
        assert result[0]["entity"] == "Alone"
        assert result[0]["depth"] == 0

    def test_linear_depth_0(self, linear_graph: KnowledgeGraph):
        result = linear_graph.traverse("A", max_depth=0)
        assert len(result) == 1
        assert result[0]["entity"] == "A"

    def test_linear_depth_1(self, linear_graph: KnowledgeGraph):
        result = linear_graph.traverse("A", max_depth=1)
        entities = [r["entity"] for r in result]
        assert "A" in entities
        assert "B" in entities
        assert "C" not in entities

    def test_linear_depth_2(self, linear_graph: KnowledgeGraph):
        result = linear_graph.traverse("A", max_depth=2)
        entities = [r["entity"] for r in result]
        assert "A" in entities
        assert "B" in entities
        assert "C" in entities
        assert "D" not in entities

    def test_linear_depth_3_reaches_all(self, linear_graph: KnowledgeGraph):
        result = linear_graph.traverse("A", max_depth=3)
        entities = [r["entity"] for r in result]
        assert set(entities) == {"A", "B", "C", "D"}

    def test_star_from_hub(self, star_graph: KnowledgeGraph):
        result = star_graph.traverse("Hub", max_depth=1)
        assert len(result) == 6  # Hub + 5 spokes

    def test_star_from_spoke(self, star_graph: KnowledgeGraph):
        result = star_graph.traverse("Spoke0", max_depth=1)
        entities = [r["entity"] for r in result]
        assert "Spoke0" in entities
        assert "Hub" in entities

    def test_max_nodes_limit(self, star_graph: KnowledgeGraph):
        result = star_graph.traverse("Hub", max_depth=1, max_nodes=3)
        assert len(result) <= 3

    def test_bfs_order(self, linear_graph: KnowledgeGraph):
        result = linear_graph.traverse("A", max_depth=10)
        depths = [r["depth"] for r in result]
        # BFS: depths should be non-decreasing
        assert depths == sorted(depths)

    def test_includes_entity_type(self, star_graph: KnowledgeGraph):
        result = star_graph.traverse("Hub", max_depth=0)
        assert result[0]["entity_type"] == "center"

    def test_includes_edges(self, star_graph: KnowledgeGraph):
        result = star_graph.traverse("Hub", max_depth=0)
        assert len(result[0]["edges"]) == 5  # 5 outgoing edges from Hub

    def test_does_not_revisit_nodes(self, rich_graph: KnowledgeGraph):
        result = rich_graph.traverse("Alice", max_depth=3)
        entities = [r["entity"] for r in result]
        assert len(entities) == len(set(entities))

    def test_handles_cycles(self, graph: KnowledgeGraph):
        graph.add_entity("X", "node")
        graph.add_entity("Y", "node")
        graph.add_entity("Z", "node")
        graph.add_relationship("X", "Y", "links")
        graph.add_relationship("Y", "Z", "links")
        graph.add_relationship("Z", "X", "links")
        result = graph.traverse("X", max_depth=10)
        assert len(result) == 3  # Should visit each once


# ============ shortest_path ============


class TestShortestPath:
    def test_same_node(self, linear_graph: KnowledgeGraph):
        assert linear_graph.shortest_path("A", "A") == ["A"]

    def test_direct_neighbors(self, linear_graph: KnowledgeGraph):
        path = linear_graph.shortest_path("A", "B")
        assert path == ["A", "B"]

    def test_multi_hop(self, linear_graph: KnowledgeGraph):
        path = linear_graph.shortest_path("A", "D")
        assert path == ["A", "B", "C", "D"]

    def test_reverse_direction(self, linear_graph: KnowledgeGraph):
        # Edges are directed A->B->C->D but traversal is undirected
        path = linear_graph.shortest_path("D", "A")
        assert path == ["D", "C", "B", "A"]

    def test_no_path(self, graph: KnowledgeGraph):
        graph.add_entity("X", "node")
        graph.add_entity("Y", "node")
        # No edges between them
        assert graph.shortest_path("X", "Y") is None

    def test_missing_source(self, graph: KnowledgeGraph):
        graph.add_entity("Y", "node")
        assert graph.shortest_path("nonexistent", "Y") is None

    def test_missing_target(self, graph: KnowledgeGraph):
        graph.add_entity("X", "node")
        assert graph.shortest_path("X", "nonexistent") is None

    def test_both_missing(self, graph: KnowledgeGraph):
        assert graph.shortest_path("X", "Y") is None

    def test_through_common_node(self, rich_graph: KnowledgeGraph):
        # Alice -> Python <- Bob (both connected via Python)
        path = rich_graph.shortest_path("Alice", "Bob")
        assert path is not None
        assert path[0] == "Alice"
        assert path[-1] == "Bob"
        assert len(path) <= 3  # Should find short path

    def test_shortest_among_alternatives(self, rich_graph: KnowledgeGraph):
        # Alice to Bob: via Python (2 hops) or via ACME (2 hops)
        path = rich_graph.shortest_path("Alice", "Bob")
        assert len(path) == 3  # Alice -> X -> Bob

    def test_ignores_expired_edges(self, graph: KnowledgeGraph):
        graph.add_entity("X", "node")
        graph.add_entity("Y", "node")
        graph.add_entity("Z", "node")
        graph.add_relationship("X", "Y", "links")
        graph.add_relationship("Y", "Z", "links")
        graph.expire_relationship("X", "Y", "links")
        assert graph.shortest_path("X", "Z") is None


# ============ get_neighborhood ============


class TestGetNeighborhood:
    def test_missing_entity(self, graph: KnowledgeGraph):
        result = graph.get_neighborhood("nonexistent")
        assert result == {"nodes": [], "edges": []}

    def test_radius_0(self, star_graph: KnowledgeGraph):
        result = star_graph.get_neighborhood("Hub", radius=0)
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["entity"] == "Hub"
        assert result["edges"] == []

    def test_radius_1_star(self, star_graph: KnowledgeGraph):
        result = star_graph.get_neighborhood("Hub", radius=1)
        assert len(result["nodes"]) == 6  # Hub + 5 spokes
        assert len(result["edges"]) == 5

    def test_radius_1_linear(self, linear_graph: KnowledgeGraph):
        result = linear_graph.get_neighborhood("B", radius=1)
        entities = {n["entity"] for n in result["nodes"]}
        assert entities == {"A", "B", "C"}

    def test_radius_2_linear(self, linear_graph: KnowledgeGraph):
        result = linear_graph.get_neighborhood("B", radius=2)
        entities = {n["entity"] for n in result["nodes"]}
        assert entities == {"A", "B", "C", "D"}

    def test_nodes_include_depth(self, linear_graph: KnowledgeGraph):
        result = linear_graph.get_neighborhood("A", radius=2)
        depth_map = {n["entity"]: n["depth"] for n in result["nodes"]}
        assert depth_map["A"] == 0
        assert depth_map["B"] == 1
        assert depth_map["C"] == 2

    def test_edges_only_within_neighborhood(self, rich_graph: KnowledgeGraph):
        # Neighborhood of Alice radius=1 includes Alice, Python, ACME
        result = rich_graph.get_neighborhood("Alice", radius=1)
        node_names = {n["entity"] for n in result["nodes"]}
        for edge in result["edges"]:
            assert edge["source"] in node_names
            assert edge["target"] in node_names

    def test_includes_metadata(self, rich_graph: KnowledgeGraph):
        result = rich_graph.get_neighborhood("Alice", radius=1)
        meta_edges = [e for e in result["edges"] if "metadata" in e]
        assert len(meta_edges) >= 1


# ============ subgraph ============


class TestSubgraph:
    def test_empty_entity_list(self, rich_graph: KnowledgeGraph):
        result = rich_graph.subgraph([])
        assert result == {"nodes": [], "edges": []}

    def test_single_entity(self, rich_graph: KnowledgeGraph):
        result = rich_graph.subgraph(["Alice"])
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["entity"] == "Alice"
        assert result["edges"] == []  # No edges to self

    def test_connected_pair(self, rich_graph: KnowledgeGraph):
        result = rich_graph.subgraph(["Alice", "Python"])
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1
        assert result["edges"][0]["relation"] == "uses"

    def test_full_triangle(self, rich_graph: KnowledgeGraph):
        result = rich_graph.subgraph(["Alice", "ACME", "Python"])
        assert len(result["nodes"]) == 3
        # Alice->Python, Alice->ACME, ACME->Python
        assert len(result["edges"]) == 3

    def test_missing_entity_filtered(self, rich_graph: KnowledgeGraph):
        result = rich_graph.subgraph(["Alice", "nonexistent"])
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["entity"] == "Alice"

    def test_excludes_expired_edges(self, graph: KnowledgeGraph):
        graph.add_entity("X", "node")
        graph.add_entity("Y", "node")
        graph.add_relationship("X", "Y", "links")
        graph.expire_relationship("X", "Y", "links")
        result = graph.subgraph(["X", "Y"])
        assert len(result["edges"]) == 0

    def test_includes_entity_type(self, rich_graph: KnowledgeGraph):
        result = rich_graph.subgraph(["Alice", "Python"])
        types = {n["entity"]: n["entity_type"] for n in result["nodes"]}
        assert types["Alice"] == "person"
        assert types["Python"] == "technology"


# ============ format_context ============


class TestProgressiveContext:
    def test_missing_entity(self, graph: KnowledgeGraph):
        assert graph.format_context("nonexistent") == ""

    def test_level_0(self, rich_graph: KnowledgeGraph):
        ctx = rich_graph.format_context("Alice", level=0)
        assert ctx == "Alice (person)"

    def test_level_0_negative(self, rich_graph: KnowledgeGraph):
        ctx = rich_graph.format_context("Alice", level=-1)
        assert ctx == "Alice (person)"

    def test_level_1_with_relationships(self, rich_graph: KnowledgeGraph):
        ctx = rich_graph.format_context("Alice", level=1)
        assert "Alice (person)" in ctx
        assert "uses" in ctx
        assert "works_at" in ctx

    def test_level_1_no_relationships(self, graph: KnowledgeGraph):
        graph.add_entity("Lonely", "node")
        ctx = graph.format_context("Lonely", level=1)
        assert "no known relationships" in ctx

    def test_level_1_default(self, rich_graph: KnowledgeGraph):
        # Default level is 1
        ctx = rich_graph.format_context("Alice")
        assert "uses" in ctx

    def test_level_2_includes_metadata(self, rich_graph: KnowledgeGraph):
        ctx = rich_graph.format_context("Alice", level=2)
        assert "Primary language" in ctx
        assert "confidence: 0.9" in ctx

    def test_level_2_includes_neighbors(self, rich_graph: KnowledgeGraph):
        ctx = rich_graph.format_context("Alice", level=2)
        assert "Neighbors:" in ctx
        assert "Python" in ctx

    def test_level_2_multiline(self, rich_graph: KnowledgeGraph):
        ctx = rich_graph.format_context("Alice", level=2)
        lines = ctx.split("\n")
        assert len(lines) >= 3  # At least header, relationships, neighbors

    def test_level_2_includes_relationship_section(self, rich_graph: KnowledgeGraph):
        ctx = rich_graph.format_context("Alice", level=2)
        assert "Relationships:" in ctx

    def test_level_2_includes_neighbor_type(self, rich_graph: KnowledgeGraph):
        ctx = rich_graph.format_context("Alice", level=2)
        assert "technology" in ctx

    def test_level_2_neighbor_cap(self, graph: KnowledgeGraph):
        """Neighbors are capped at 10 in L2 output."""
        graph.add_entity("Center", "hub")
        for i in range(15):
            name = f"N{i}"
            graph.add_entity(name, "leaf")
            graph.add_relationship("Center", name, "links")
        ctx = graph.format_context("Center", level=2)
        # Count lines starting with "  N" in the Neighbors section
        lines = ctx.split("\n")
        neighbor_lines = [
            line for line in lines if line.strip().startswith("N") and "relationships" in line
        ]
        assert len(neighbor_lines) <= 10
