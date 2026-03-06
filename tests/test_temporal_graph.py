# test_temporal_graph.py — Tests for the temporal knowledge graph.
# Created: 2026-03-06 — Covers TemporalEdge, temporal relationship queries,
#   point-in-time queries, relationship evolution, expiration, and serialization.

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from soul_protocol.memory.graph import KnowledgeGraph, TemporalEdge


@pytest.fixture
def graph() -> KnowledgeGraph:
    return KnowledgeGraph()


class TestTemporalEdge:
    def test_default_valid_from(self):
        edge = TemporalEdge("Alice", "Python", "uses")
        assert edge.valid_from is not None
        assert edge.valid_to is None

    def test_is_active_at_within_range(self):
        t0 = datetime(2026, 1, 1)
        t1 = datetime(2026, 6, 1)
        edge = TemporalEdge("A", "B", "uses", valid_from=t0, valid_to=t1)

        assert edge.is_active_at(datetime(2026, 3, 1)) is True

    def test_is_active_at_before_start(self):
        t0 = datetime(2026, 3, 1)
        edge = TemporalEdge("A", "B", "uses", valid_from=t0)
        assert edge.is_active_at(datetime(2026, 1, 1)) is False

    def test_is_active_at_after_end(self):
        t0 = datetime(2026, 1, 1)
        t1 = datetime(2026, 3, 1)
        edge = TemporalEdge("A", "B", "uses", valid_from=t0, valid_to=t1)
        assert edge.is_active_at(datetime(2026, 6, 1)) is False

    def test_is_active_at_no_end(self):
        t0 = datetime(2026, 1, 1)
        edge = TemporalEdge("A", "B", "uses", valid_from=t0)
        # Still active far in the future
        assert edge.is_active_at(datetime(2030, 1, 1)) is True

    def test_is_currently_active(self):
        edge = TemporalEdge("A", "B", "uses")
        assert edge.is_currently_active() is True

        edge.valid_to = datetime.now()
        assert edge.is_currently_active() is False

    def test_as_tuple(self):
        edge = TemporalEdge("Alice", "Python", "uses")
        assert edge.as_tuple() == ("Alice", "Python", "uses")

    def test_serialization_roundtrip(self):
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        t1 = datetime(2026, 6, 1, 12, 0, 0)
        edge = TemporalEdge("A", "B", "uses", valid_from=t0, valid_to=t1)

        data = edge.to_dict()
        restored = TemporalEdge.from_dict(data)

        assert restored.source == "A"
        assert restored.target == "B"
        assert restored.relation == "uses"
        assert restored.valid_from == t0
        assert restored.valid_to == t1


class TestGraphAddRelationship:
    def test_add_with_temporal_fields(self, graph: KnowledgeGraph):
        t0 = datetime(2026, 1, 1)
        graph.add_relationship("Alice", "Python", "uses", valid_from=t0)

        related = graph.get_related("Alice")
        assert len(related) == 1
        assert related[0]["relation"] == "uses"

    def test_duplicate_active_edges_ignored(self, graph: KnowledgeGraph):
        graph.add_relationship("Alice", "Python", "uses")
        graph.add_relationship("Alice", "Python", "uses")

        # Should still only have one edge
        related = graph.get_related("Alice")
        assert len(related) == 1

    def test_expired_then_new_creates_two_edges(self, graph: KnowledgeGraph):
        t0 = datetime(2026, 1, 1)
        t1 = datetime(2026, 3, 1)
        # Add and expire
        graph.add_relationship("Alice", "Python", "uses", valid_from=t0)
        graph.expire_relationship("Alice", "Python", "uses", expire_at=t1)

        # Add a new active one
        graph.add_relationship("Alice", "Python", "uses", valid_from=t1)

        # get_related only shows active
        related = graph.get_related("Alice")
        assert len(related) == 1

        # But evolution shows both
        evolution = graph.relationship_evolution("Alice", "Python")
        assert len(evolution) == 2


class TestExpireRelationship:
    def test_expire_existing(self, graph: KnowledgeGraph):
        graph.add_relationship("A", "B", "uses")
        result = graph.expire_relationship("A", "B", "uses")
        assert result is True

        # No longer shows in get_related (not active)
        assert graph.get_related("A") == []

    def test_expire_nonexistent(self, graph: KnowledgeGraph):
        result = graph.expire_relationship("X", "Y", "uses")
        assert result is False


class TestAsOfDate:
    def test_point_in_time_query(self, graph: KnowledgeGraph):
        t0 = datetime(2026, 1, 1)
        t1 = datetime(2026, 3, 1)
        t2 = datetime(2026, 6, 1)

        # Alice used Python from Jan to Mar
        graph.add_relationship("Alice", "Python", "uses", valid_from=t0, valid_to=t1)
        # Alice uses Rust from Mar onward
        graph.add_relationship("Alice", "Rust", "uses", valid_from=t1)

        # In February: only Python
        feb = graph.as_of_date(datetime(2026, 2, 1))
        assert len(feb) == 1
        assert feb[0]["target"] == "Python"

        # In April: only Rust
        apr = graph.as_of_date(datetime(2026, 4, 1))
        assert len(apr) == 1
        assert apr[0]["target"] == "Rust"

    def test_no_results_before_any_edges(self, graph: KnowledgeGraph):
        graph.add_relationship(
            "A", "B", "uses", valid_from=datetime(2026, 6, 1)
        )
        result = graph.as_of_date(datetime(2026, 1, 1))
        assert result == []


class TestRelationshipEvolution:
    def test_chronological_order(self, graph: KnowledgeGraph):
        t0 = datetime(2026, 1, 1)
        t1 = datetime(2026, 3, 1)
        t2 = datetime(2026, 6, 1)

        graph.add_relationship("Alice", "Bob", "friends", valid_from=t0, valid_to=t1)
        graph.add_relationship("Alice", "Bob", "colleagues", valid_from=t1, valid_to=t2)
        graph.add_relationship("Alice", "Bob", "partners", valid_from=t2)

        evolution = graph.relationship_evolution("Alice", "Bob")
        assert len(evolution) == 3
        assert evolution[0]["relation"] == "friends"
        assert evolution[1]["relation"] == "colleagues"
        assert evolution[2]["relation"] == "partners"
        # Sorted by valid_from
        assert evolution[0]["valid_from"] < evolution[1]["valid_from"]
        assert evolution[1]["valid_from"] < evolution[2]["valid_from"]

    def test_empty_evolution(self, graph: KnowledgeGraph):
        result = graph.relationship_evolution("X", "Y")
        assert result == []


class TestGetRelatedFiltersExpired:
    def test_only_active_returned(self, graph: KnowledgeGraph):
        graph.add_relationship("A", "B", "uses")
        graph.add_relationship("A", "C", "uses")
        graph.expire_relationship("A", "B", "uses")

        related = graph.get_related("A")
        assert len(related) == 1
        assert related[0]["target"] == "C"


class TestSerializationRoundtrip:
    def test_to_dict_and_from_dict(self, graph: KnowledgeGraph):
        t0 = datetime(2026, 1, 1)
        t1 = datetime(2026, 6, 1)

        graph.add_entity("Alice", "person")
        graph.add_entity("Python", "technology")
        graph.add_relationship("Alice", "Python", "uses", valid_from=t0, valid_to=t1)
        graph.add_relationship("Alice", "Python", "teaches", valid_from=t1)

        data = graph.to_dict()
        restored = KnowledgeGraph.from_dict(data)

        assert set(restored.entities()) == {"Alice", "Python"}

        # Check temporal fidelity
        feb = restored.as_of_date(datetime(2026, 2, 1))
        assert len(feb) == 1
        assert feb[0]["relation"] == "uses"

        aug = restored.as_of_date(datetime(2026, 8, 1))
        assert len(aug) == 1
        assert aug[0]["relation"] == "teaches"

    def test_backward_compat_old_format(self, graph: KnowledgeGraph):
        """Old edge format without temporal fields should still work."""
        old_data = {
            "entities": {"Alice": "person", "Bob": "person"},
            "edges": [{"source": "Alice", "target": "Bob", "relation": "knows"}],
        }
        restored = KnowledgeGraph.from_dict(old_data)
        related = restored.get_related("Alice")
        assert len(related) == 1
        assert related[0]["relation"] == "knows"
