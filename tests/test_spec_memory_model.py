# test_spec_memory_model.py — Tests for v0.3.4 spec-level data model additions.
# Updated: v0.3.4-fix — Rewrote salience activation tests for additive boost model.
#   Added: test_salience_helps_negative_base, test_salience_zero_does_not_penalize,
#   test_salience_additive_range, test_memory_entry_salience_default.
# Tests: MemoryCategory enum, MemoryEntry new fields (category, abstract,
# overview, salience), salience boost in activation, TemporalEdge metadata
# roundtrip and surfacing in query methods.

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from soul_protocol.runtime.memory.activation import compute_activation
from soul_protocol.runtime.memory.graph import KnowledgeGraph, TemporalEdge
from soul_protocol.runtime.types import MemoryCategory, MemoryEntry, MemoryType

# ============ MemoryCategory Enum ============


class TestMemoryCategory:
    def test_all_seven_categories_exist(self):
        assert len(MemoryCategory) == 7

    def test_category_values(self):
        assert MemoryCategory.PROFILE == "profile"
        assert MemoryCategory.PREFERENCE == "preference"
        assert MemoryCategory.ENTITY == "entity"
        assert MemoryCategory.EVENT == "event"
        assert MemoryCategory.CASE == "case"
        assert MemoryCategory.PATTERN == "pattern"
        assert MemoryCategory.SKILL == "skill"

    def test_is_str_enum(self):
        assert isinstance(MemoryCategory.PROFILE, str)
        assert f"category={MemoryCategory.PROFILE}" == "category=profile"


# ============ MemoryEntry New Fields ============


class TestMemoryEntryNewFields:
    def test_defaults(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test")
        assert entry.category is None
        assert entry.abstract is None
        assert entry.overview is None
        assert entry.salience == 0.5

    def test_assignment(self):
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="User prefers dark mode",
            category=MemoryCategory.PREFERENCE,
            abstract="User prefers dark mode",
            salience=0.8,
        )
        assert entry.category == MemoryCategory.PREFERENCE
        assert entry.abstract == "User prefers dark mode"
        assert entry.salience == 0.8

    def test_salience_validation_lower_bound(self):
        with pytest.raises(ValidationError):
            MemoryEntry(type=MemoryType.SEMANTIC, content="x", salience=-0.1)

    def test_salience_validation_upper_bound(self):
        with pytest.raises(ValidationError):
            MemoryEntry(type=MemoryType.SEMANTIC, content="x", salience=1.1)

    def test_json_roundtrip(self):
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="test",
            category=MemoryCategory.ENTITY,
            abstract="short",
            overview="longer overview",
            salience=0.9,
        )
        data = entry.model_dump()
        restored = MemoryEntry(**data)
        assert restored.category == MemoryCategory.ENTITY
        assert restored.abstract == "short"
        assert restored.overview == "longer overview"
        assert restored.salience == 0.9


# ============ Salience in Activation ============


class TestSalienceActivation:
    """Test that salience additive boost behaves correctly in compute_activation."""

    def _make_entry(self, salience: float, importance: int = 8) -> MemoryEntry:
        return MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="unique content for testing",
            importance=importance,
            salience=salience,
        )

    def test_neutral_salience_is_identity(self):
        """salience=0.5 → boost=0.0, no effect on activation."""
        entry = self._make_entry(salience=0.5)
        score = compute_activation(entry, "unrelated query", noise=False)
        assert isinstance(score, float)

    def test_high_salience_beats_low_salience(self):
        """salience=1.0 should score higher than salience=0.0 for same content."""
        high = self._make_entry(salience=1.0)
        low = self._make_entry(salience=0.0)
        high_score = compute_activation(high, "zzzzz", noise=False)
        low_score = compute_activation(low, "zzzzz", noise=False)
        assert high_score > low_score

    def test_high_salience_boosts_negative_base(self):
        """salience=1.0 should IMPROVE activation for low-importance (negative base) memories."""
        high_sal = self._make_entry(salience=1.0, importance=2)
        neutral_sal = self._make_entry(salience=0.5, importance=2)
        high_score = compute_activation(high_sal, "zzzzz", noise=False)
        neutral_score = compute_activation(neutral_sal, "zzzzz", noise=False)
        # Key fix: high salience must HELP negative base, not amplify the penalty
        assert high_score > neutral_score

    def test_salience_helps_negative_base(self):
        """High salience should make a low-importance memory's activation less negative or positive."""
        # importance=1 → base = (1-5)*0.2 = -0.8 (most negative possible)
        low_imp_high_sal = self._make_entry(salience=1.0, importance=1)
        low_imp_neutral_sal = self._make_entry(salience=0.5, importance=1)
        high_score = compute_activation(low_imp_high_sal, "zzzzz", noise=False)
        neutral_score = compute_activation(low_imp_neutral_sal, "zzzzz", noise=False)
        # Salience boost of +0.25 should lift the activation
        assert high_score > neutral_score
        assert high_score - neutral_score == pytest.approx(0.25, abs=0.01)

    def test_salience_zero_does_not_penalize(self):
        """salience=0.0 should not make activation drastically worse than salience=0.5."""
        zero_sal = self._make_entry(salience=0.0, importance=3)
        neutral_sal = self._make_entry(salience=0.5, importance=3)
        zero_score = compute_activation(zero_sal, "zzzzz", noise=False)
        neutral_score = compute_activation(neutral_sal, "zzzzz", noise=False)
        # Difference should be exactly 0.25 (additive), not a huge multiplied gap
        diff = abs(neutral_score - zero_score)
        assert diff == pytest.approx(0.25, abs=0.01)
        # Zero salience is lower but not catastrophically so
        assert zero_score < neutral_score

    def test_salience_additive_range(self):
        """Salience boost should be bounded between -0.25 and +0.25."""
        min_entry = self._make_entry(salience=0.0)
        max_entry = self._make_entry(salience=1.0)
        min_score = compute_activation(min_entry, "zzzzz", noise=False)
        max_score = compute_activation(max_entry, "zzzzz", noise=False)
        # Total range of salience effect = 0.5 (from -0.25 to +0.25)
        assert max_score - min_score == pytest.approx(0.5, abs=0.01)

    def test_memory_entry_salience_default(self):
        """MemoryEntry.salience should default to 0.5."""
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test content")
        assert entry.salience == 0.5


# ============ TemporalEdge Metadata ============


class TestTemporalEdgeMetadata:
    def test_metadata_default_none(self):
        edge = TemporalEdge(source="A", target="B", relation="knows")
        assert edge.metadata is None

    def test_metadata_stored(self):
        meta = {"context": "met at conference", "confidence": 0.9}
        edge = TemporalEdge(source="A", target="B", relation="knows", metadata=meta)
        assert edge.metadata == meta

    def test_to_dict_includes_metadata(self):
        meta = {"source_id": "mem-123"}
        edge = TemporalEdge(source="A", target="B", relation="knows", metadata=meta)
        d = edge.to_dict()
        assert d["metadata"] == meta

    def test_to_dict_omits_metadata_when_none(self):
        edge = TemporalEdge(source="A", target="B", relation="knows")
        d = edge.to_dict()
        assert "metadata" not in d

    def test_from_dict_roundtrip(self):
        meta = {"reason": "co-authored paper"}
        original = TemporalEdge(source="A", target="B", relation="collaborates", metadata=meta)
        restored = TemporalEdge.from_dict(original.to_dict())
        assert restored.metadata == meta

    def test_from_dict_without_metadata_key(self):
        data = {
            "source": "A",
            "target": "B",
            "relation": "knows",
            "valid_from": datetime.now().isoformat(),
        }
        edge = TemporalEdge.from_dict(data)
        assert edge.metadata is None


# ============ KnowledgeGraph Metadata in Query Methods ============


class TestGraphMetadataInQueries:
    def test_get_related_includes_metadata(self):
        g = KnowledgeGraph()
        g.add_relationship("Alice", "Bob", "mentors", metadata={"since": "2024"})
        results = g.get_related("Alice")
        assert len(results) == 1
        assert results[0]["metadata"] == {"since": "2024"}

    def test_get_related_omits_metadata_when_none(self):
        g = KnowledgeGraph()
        g.add_relationship("Alice", "Bob", "knows")
        results = g.get_related("Alice")
        assert "metadata" not in results[0]

    def test_as_of_date_includes_metadata(self):
        g = KnowledgeGraph()
        now = datetime.now()
        g.add_relationship(
            "A", "B", "works_at", metadata={"role": "engineer"}, valid_from=now - timedelta(days=1)
        )
        results = g.as_of_date(now)
        assert any(r.get("metadata") == {"role": "engineer"} for r in results)

    def test_relationship_evolution_includes_metadata(self):
        g = KnowledgeGraph()
        now = datetime.now()
        g.add_relationship(
            "A", "B", "friend", metadata={"context": "school"}, valid_from=now - timedelta(days=100)
        )
        g.expire_relationship("A", "B", "friend")
        g.add_relationship("A", "B", "colleague", metadata={"context": "work"})
        results = g.relationship_evolution("A", "B")
        assert len(results) == 2
        assert results[0].get("metadata") == {"context": "school"}
        assert results[1].get("metadata") == {"context": "work"}
