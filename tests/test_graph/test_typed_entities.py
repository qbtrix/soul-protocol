# test_graph/test_typed_entities.py — Tests for the typed entity ontology.
# Created: 2026-04-29 (#190) — Verifies that built-in EntityType members are
# accepted, arbitrary strings are accepted, and the GraphView ``type`` filter
# works correctly. Also covers entity provenance round-trip through to_dict.

from __future__ import annotations

import pytest

from soul_protocol import EntityType, GraphView, RelationType
from soul_protocol.runtime.memory.graph import KnowledgeGraph


class TestBuiltInEntityTypes:
    """All eight built-in EntityType members round-trip through the graph."""

    @pytest.mark.parametrize(
        "etype",
        [
            EntityType.PERSON,
            EntityType.PLACE,
            EntityType.ORG,
            EntityType.CONCEPT,
            EntityType.TOOL,
            EntityType.DOCUMENT,
            EntityType.EVENT,
            EntityType.RELATION,
        ],
    )
    def test_built_in_entity_type_round_trips(self, etype: EntityType) -> None:
        g = KnowledgeGraph()
        g.add_entity("Alice", str(etype.value))
        nodes = g.list_nodes()
        assert len(nodes) == 1
        assert nodes[0].type == etype.value

    def test_string_values_match_enum(self) -> None:
        # StrEnum members compare equal to their string values.
        assert EntityType.PERSON == "person"
        assert EntityType.TOOL == "tool"


class TestArbitraryEntityStrings:
    """Custom type strings pass through untouched (open-vocabulary contract)."""

    @pytest.mark.parametrize(
        "custom_type",
        ["pr", "channel", "library", "issue", "repo", "namespace", "kind:custom"],
    )
    def test_arbitrary_type_accepted(self, custom_type: str) -> None:
        g = KnowledgeGraph()
        g.add_entity("X", custom_type)
        nodes = g.list_nodes()
        assert nodes[0].type == custom_type


class TestTypeFilter:
    """GraphView.nodes(type=...) filters by entity type."""

    @pytest.fixture
    def graph(self) -> KnowledgeGraph:
        g = KnowledgeGraph()
        g.add_entity("Alice", "person")
        g.add_entity("Bob", "person")
        g.add_entity("Acme", "org")
        g.add_entity("Python", "tool")
        return g

    def test_filter_by_person(self, graph: KnowledgeGraph) -> None:
        view = GraphView(graph)
        people = view.nodes(type="person")
        names = {n.id for n in people}
        assert names == {"Alice", "Bob"}

    def test_filter_by_org(self, graph: KnowledgeGraph) -> None:
        view = GraphView(graph)
        orgs = view.nodes(type="org")
        assert len(orgs) == 1
        assert orgs[0].id == "Acme"

    def test_filter_by_tool(self, graph: KnowledgeGraph) -> None:
        view = GraphView(graph)
        tools = view.nodes(type="tool")
        assert len(tools) == 1
        assert tools[0].id == "Python"

    def test_filter_unknown_type_returns_empty(self, graph: KnowledgeGraph) -> None:
        view = GraphView(graph)
        assert view.nodes(type="nonexistent") == []

    def test_no_filter_returns_all(self, graph: KnowledgeGraph) -> None:
        view = GraphView(graph)
        assert len(view.nodes()) == 4

    def test_name_match_filter(self, graph: KnowledgeGraph) -> None:
        view = GraphView(graph)
        # Substring, case-insensitive
        results = view.nodes(name_match="ali")
        assert {n.id for n in results} == {"Alice"}

    def test_limit(self, graph: KnowledgeGraph) -> None:
        view = GraphView(graph)
        results = view.nodes(limit=2)
        assert len(results) == 2

    def test_combined_filter(self, graph: KnowledgeGraph) -> None:
        view = GraphView(graph)
        # All people whose name starts with B
        results = view.nodes(type="person", name_match="b")
        assert {n.id for n in results} == {"Bob"}


class TestProvenance:
    """Entity provenance (memory IDs that produced the entity) round-trips."""

    def test_add_with_source_memory_id(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("Alice", "person", source_memory_id="mem-1")
        g.add_entity("Alice", "person", source_memory_id="mem-2")
        nodes = g.list_nodes()
        assert nodes[0].provenance == ["mem-1", "mem-2"]

    def test_dedup_source_memory_id(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("Alice", "person", source_memory_id="mem-1")
        g.add_entity("Alice", "person", source_memory_id="mem-1")
        nodes = g.list_nodes()
        assert nodes[0].provenance == ["mem-1"]

    def test_no_source_memory_means_empty_provenance(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("Alice", "person")
        nodes = g.list_nodes()
        assert nodes[0].provenance == []

    def test_provenance_round_trips_through_to_dict(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("Alice", "person", source_memory_id="mem-1")
        g.add_entity("Alice", "person", source_memory_id="mem-2")
        data = g.to_dict()
        g2 = KnowledgeGraph.from_dict(data)
        nodes = g2.list_nodes()
        assert nodes[0].provenance == ["mem-1", "mem-2"]

    def test_legacy_graph_without_provenance_loads(self) -> None:
        # Pre-0.5.0 graph data has no provenance key
        legacy_data = {
            "entities": {"Alice": "person"},
            "edges": [],
        }
        g = KnowledgeGraph.from_dict(legacy_data)
        nodes = g.list_nodes()
        assert nodes[0].provenance == []

    def test_remove_entity_drops_provenance(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("Alice", "person", source_memory_id="mem-1")
        g.remove_entity("Alice")
        # Provenance should be gone too
        assert "Alice" not in g._provenance


class TestEntityTypeIsOpenString:
    """Type field accepts strings that aren't ontology members."""

    def test_meta_type_passes_through(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("My-PR-1234", "pr")
        nodes = g.list_nodes(type="pr")
        assert len(nodes) == 1
        assert nodes[0].type == "pr"

    def test_unknown_default_normalizes_to_concept_via_translation(self) -> None:
        # The translate_to_ontology helper normalizes "" / "unknown"
        from soul_protocol.runtime.memory.manager import translate_to_ontology

        assert translate_to_ontology("") == "concept"
        assert translate_to_ontology("unknown") == "concept"

    def test_translation_preserves_built_ins(self) -> None:
        from soul_protocol.runtime.memory.manager import translate_to_ontology

        for built_in in ("person", "place", "org", "concept", "tool", "document", "event"):
            assert translate_to_ontology(built_in) == built_in

    def test_translation_normalizes_synonyms(self) -> None:
        from soul_protocol.runtime.memory.manager import translate_to_ontology

        assert translate_to_ontology("technology") == "tool"
        assert translate_to_ontology("organization") == "org"

    def test_translation_passes_through_custom(self) -> None:
        from soul_protocol.runtime.memory.manager import translate_to_ontology

        assert translate_to_ontology("project") == "project"
        assert translate_to_ontology("library") == "library"


class TestRelationType:
    """RelationType enum members and arbitrary relation strings."""

    @pytest.mark.parametrize(
        "rel",
        [
            RelationType.MENTIONS,
            RelationType.RELATED,
            RelationType.DEPENDS_ON,
            RelationType.CONTRIBUTES_TO,
            RelationType.CAUSES,
            RelationType.FOLLOWS,
            RelationType.SUPERSEDES,
            RelationType.OWNED_BY,
        ],
    )
    def test_built_in_relations_round_trip(self, rel: RelationType) -> None:
        g = KnowledgeGraph()
        g.add_entity("A", "person")
        g.add_entity("B", "person")
        g.add_relationship("A", "B", str(rel.value))
        edges = g.list_edges()
        assert len(edges) == 1
        assert edges[0].relation == rel.value

    def test_custom_relation_string_accepted(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("A", "person")
        g.add_entity("B", "person")
        g.add_relationship("A", "B", "co_authored")
        edges = g.list_edges()
        assert edges[0].relation == "co_authored"
