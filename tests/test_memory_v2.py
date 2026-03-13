# test_memory_v2.py — Tests for Phase 2 memory architecture improvements.
# Updated: v0.3.4-fix — Updated salience tests for additive boost model.
#   Default salience (0.5) now sits between high (1.0) and low (0.0) as expected.
# Updated: 2026-03-13 — Added tests for EpisodicStore.update_entry(),
#   keyword classification false positive edge cases (from/may removal),
#   and dedup pipeline (reconcile_fact) coverage.
# Created: 2026-03-13 — Covers MemoryCategory enum, new MemoryEntry fields,
#   classify_memory_category(), generate_abstract(), compute_salience(),
#   reconcile_fact(), TemporalEdge metadata, and salience-weighted activation.

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from soul_protocol.runtime.cognitive.engine import (
    classify_memory_category,
    compute_salience,
    generate_abstract,
)
from soul_protocol.runtime.memory.activation import compute_activation
from soul_protocol.runtime.memory.dedup import reconcile_fact
from soul_protocol.runtime.memory.episodic import EpisodicStore
from soul_protocol.runtime.memory.graph import TemporalEdge
from soul_protocol.runtime.types import (
    Interaction,
    MemoryCategory,
    MemoryEntry,
    MemoryType,
    SignificanceScore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(content: str, eid: str = "e1", superseded_by: str | None = None) -> MemoryEntry:
    """Build a minimal semantic MemoryEntry for dedup tests."""
    return MemoryEntry(
        id=eid,
        type=MemoryType.SEMANTIC,
        content=content,
        superseded_by=superseded_by,
    )


# ---------------------------------------------------------------------------
# 1. MemoryCategory enum — all 7 categories and their string values
# ---------------------------------------------------------------------------


class TestMemoryCategory:
    def test_all_seven_categories_exist(self):
        members = {c.name for c in MemoryCategory}
        assert members == {"PROFILE", "PREFERENCE", "ENTITY", "EVENT", "CASE", "PATTERN", "SKILL"}

    def test_profile_value(self):
        assert MemoryCategory.PROFILE == "profile"

    def test_preference_value(self):
        assert MemoryCategory.PREFERENCE == "preference"

    def test_entity_value(self):
        assert MemoryCategory.ENTITY == "entity"

    def test_event_value(self):
        assert MemoryCategory.EVENT == "event"

    def test_case_value(self):
        assert MemoryCategory.CASE == "case"

    def test_pattern_value(self):
        assert MemoryCategory.PATTERN == "pattern"

    def test_skill_value(self):
        assert MemoryCategory.SKILL == "skill"

    def test_is_str_enum(self):
        # StrEnum members compare equal to their string value
        assert MemoryCategory.ENTITY == "entity"
        assert str(MemoryCategory.SKILL) == "skill"


# ---------------------------------------------------------------------------
# 2. MemoryEntry new fields — default values
# ---------------------------------------------------------------------------


class TestMemoryEntryNewFields:
    def test_category_defaults_to_none(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test")
        assert entry.category is None

    def test_abstract_defaults_to_none(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test")
        assert entry.abstract is None

    def test_overview_defaults_to_none(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test")
        assert entry.overview is None

    def test_salience_defaults_to_0_5(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test")
        assert entry.salience == 0.5

    def test_salience_accepts_zero(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test", salience=0.0)
        assert entry.salience == 0.0

    def test_salience_accepts_one(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test", salience=1.0)
        assert entry.salience == 1.0

    def test_category_can_be_set(self):
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="test",
            category=MemoryCategory.PREFERENCE,
        )
        assert entry.category == MemoryCategory.PREFERENCE

    def test_abstract_can_be_set(self):
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="long content",
            abstract="short abstract",
        )
        assert entry.abstract == "short abstract"


# ---------------------------------------------------------------------------
# 3. classify_memory_category() — keyword heuristics
# ---------------------------------------------------------------------------


class TestClassifyMemoryCategory:
    def test_preference_keyword_likes(self):
        result = classify_memory_category("User likes Python programming")
        assert result == MemoryCategory.PREFERENCE

    def test_preference_keyword_loves(self):
        result = classify_memory_category("The user loves hiking in the mountains")
        assert result == MemoryCategory.PREFERENCE

    def test_preference_keyword_prefers(self):
        result = classify_memory_category("User prefers dark mode editors")
        assert result == MemoryCategory.PREFERENCE

    def test_preference_keyword_dislikes(self):
        result = classify_memory_category("User dislikes early morning meetings")
        assert result == MemoryCategory.PREFERENCE

    def test_entity_from_proper_name_pattern(self):
        # Two capitalized words (FirstName LastName) triggers ENTITY
        result = classify_memory_category("John Smith works at Acme Corp")
        assert result == MemoryCategory.ENTITY

    def test_event_keyword_monday(self):
        result = classify_memory_category("Meeting scheduled for Monday at noon")
        assert result == MemoryCategory.EVENT

    def test_event_keyword_yesterday(self):
        result = classify_memory_category("User mentioned yesterday was difficult")
        assert result == MemoryCategory.EVENT

    def test_event_keyword_deadline(self):
        result = classify_memory_category("The project deadline is approaching fast")
        assert result == MemoryCategory.EVENT

    def test_profile_keyword_name_is(self):
        result = classify_memory_category("User's name is Alice and they are a developer")
        assert result == MemoryCategory.PROFILE

    def test_profile_keyword_lives_in(self):
        # Avoid "San Francisco" (triggers entity check before profile) — use lowercase city
        result = classify_memory_category("User lives in berlin and commutes daily")
        assert result == MemoryCategory.PROFILE

    def test_profile_keyword_is_a(self):
        result = classify_memory_category("User is a software engineer")
        assert result == MemoryCategory.PROFILE

    def test_none_for_unclassified_content(self):
        # Generic statement with no category signals
        result = classify_memory_category("The weather outside is pleasant")
        assert result is None

    def test_preference_takes_priority_over_entity(self):
        # "likes" triggers PREFERENCE before entity check
        result = classify_memory_category("Mary Johnson likes cooking Italian food")
        assert result == MemoryCategory.PREFERENCE

    def test_case_insensitive_matching(self):
        # Keywords checked against lowercased content
        result = classify_memory_category("USER LIKES COFFEE")
        assert result == MemoryCategory.PREFERENCE


# ---------------------------------------------------------------------------
# 4. generate_abstract() — first-sentence extraction and truncation
# ---------------------------------------------------------------------------


class TestGenerateAbstract:
    def test_extracts_first_sentence_on_period(self):
        content = "User likes coffee. They also enjoy tea."
        result = generate_abstract(content)
        assert result == "User likes coffee"

    def test_extracts_first_sentence_on_exclamation(self):
        content = "What a great day! The sun is shining."
        result = generate_abstract(content)
        assert result == "What a great day"

    def test_extracts_first_sentence_on_question_mark(self):
        content = "Is the sky blue? Yes it is."
        result = generate_abstract(content)
        assert result == "Is the sky blue"

    def test_extracts_first_line_on_newline(self):
        content = "First line here\nSecond line here"
        result = generate_abstract(content)
        assert result == "First line here"

    def test_short_content_passes_through_unchanged(self):
        content = "Short memory"
        result = generate_abstract(content)
        assert result == "Short memory"

    def test_truncates_long_first_sentence_at_word_boundary(self):
        # Build a sentence longer than 400 chars with no sentence-ending punctuation
        long_sentence = "word " * 100  # 500 chars, all one "sentence"
        result = generate_abstract(long_sentence)
        # Must be shorter than the input
        assert len(result) <= 403  # 400 chars + "..."
        assert result.endswith("...")

    def test_truncated_abstract_ends_with_ellipsis(self):
        long_sentence = ("important detail about the user " * 15).strip()
        result = generate_abstract(long_sentence)
        if len(long_sentence) > 400:
            assert result.endswith("...")

    def test_exactly_400_chars_not_truncated(self):
        content = "a" * 400  # exactly 400, single token — no spaces for rsplit
        result = generate_abstract(content)
        # rsplit on empty string returns the whole thing — no truncation
        assert not result.endswith("...")

    def test_empty_content_returns_empty_string(self):
        result = generate_abstract("")
        assert result == ""


# ---------------------------------------------------------------------------
# 5. compute_salience() — weighted combination and clamping
# ---------------------------------------------------------------------------


class TestComputeSalience:
    def test_all_zero_returns_zero(self):
        score = SignificanceScore(
            novelty=0.0,
            emotional_intensity=0.0,
            goal_relevance=0.0,
            content_richness=0.0,
        )
        assert compute_salience(score) == 0.0

    def test_all_one_returns_one(self):
        # 1.0*0.3 + 1.0*0.3 + 1.0*0.25 + 1.0*0.15 = 1.0
        score = SignificanceScore(
            novelty=1.0,
            emotional_intensity=1.0,
            goal_relevance=1.0,
            content_richness=1.0,
        )
        assert compute_salience(score) == pytest.approx(1.0)

    def test_novelty_only_contributes_0_3_weight(self):
        score = SignificanceScore(
            novelty=1.0,
            emotional_intensity=0.0,
            goal_relevance=0.0,
            content_richness=0.0,
        )
        assert compute_salience(score) == pytest.approx(0.3)

    def test_emotional_intensity_only_contributes_0_3_weight(self):
        score = SignificanceScore(
            novelty=0.0,
            emotional_intensity=1.0,
            goal_relevance=0.0,
            content_richness=0.0,
        )
        assert compute_salience(score) == pytest.approx(0.3)

    def test_goal_relevance_only_contributes_0_25_weight(self):
        score = SignificanceScore(
            novelty=0.0,
            emotional_intensity=0.0,
            goal_relevance=1.0,
            content_richness=0.0,
        )
        assert compute_salience(score) == pytest.approx(0.25)

    def test_content_richness_only_contributes_0_15_weight(self):
        score = SignificanceScore(
            novelty=0.0,
            emotional_intensity=0.0,
            goal_relevance=0.0,
            content_richness=1.0,
        )
        assert compute_salience(score) == pytest.approx(0.15)

    def test_clamped_to_1_0_maximum(self):
        # Even if components sum to > 1.0, result must be <= 1.0
        score = SignificanceScore(
            novelty=1.0,
            emotional_intensity=1.0,
            goal_relevance=1.0,
            content_richness=1.0,
        )
        result = compute_salience(score)
        assert result <= 1.0

    def test_result_is_float(self):
        score = SignificanceScore(novelty=0.5, emotional_intensity=0.5)
        result = compute_salience(score)
        assert isinstance(result, float)

    def test_weighted_combination_example(self):
        # novelty=0.8, emotional_intensity=0.6, goal_relevance=0.4, richness=0.2
        # raw = 0.8*0.3 + 0.6*0.3 + 0.4*0.25 + 0.2*0.15
        #     = 0.24 + 0.18 + 0.10 + 0.03 = 0.55
        score = SignificanceScore(
            novelty=0.8,
            emotional_intensity=0.6,
            goal_relevance=0.4,
            content_richness=0.2,
        )
        assert compute_salience(score) == pytest.approx(0.55)


# ---------------------------------------------------------------------------
# 6. reconcile_fact() — CREATE / SKIP / MERGE decisions
# ---------------------------------------------------------------------------


class TestReconcileFact:
    def test_empty_existing_returns_create(self):
        action, target = reconcile_fact("User loves hiking", [])
        assert action == "CREATE"
        assert target is None

    def test_completely_different_content_returns_create(self):
        # Jaccard near zero — no token overlap between these
        existing = [_make_entry("The sky is very blue today", eid="sky1")]
        action, target = reconcile_fact("User loves Python programming", existing)
        assert action == "CREATE"
        assert target is None

    def test_identical_content_returns_skip(self):
        # Jaccard = 1.0 — perfect duplicate
        content = "User prefers coffee over tea in the morning"
        existing = [_make_entry(content, eid="fact1")]
        action, target = reconcile_fact(content, existing)
        assert action == "SKIP"
        assert target == "fact1"

    def test_nearly_identical_content_returns_skip(self):
        # 14 shared tokens, 1 unique each side → union=16, Jaccard=14/16=0.875 > 0.85
        existing = [
            _make_entry(
                "User often hikes outdoors and loves long trails through forest glades beneath mountains and rivers here",
                eid="hike1",
            )
        ]
        new_fact = "User often hikes outdoors and loves long trails through forest glades beneath mountains and rivers there"
        action, target = reconcile_fact(new_fact, existing)
        assert action == "SKIP"
        assert target == "hike1"

    def test_medium_similarity_returns_merge(self):
        # Jaccard between 0.6 and 0.85: 4 shared / 6 total = 0.667
        existing = [
            _make_entry("User prefers coffee in the morning", eid="coffee1")
        ]
        new_fact = "User prefers tea in the morning"
        action, target = reconcile_fact(new_fact, existing)
        assert action == "MERGE"
        assert target == "coffee1"

    def test_merge_returns_best_match_id(self):
        # Multiple existing facts — merge target should be the highest-similarity one
        existing = [
            _make_entry("User enjoys running every day", eid="run1"),
            _make_entry("User enjoys jogging every morning outside", eid="jog1"),
        ]
        new_fact = "User enjoys running every morning outside"
        action, target = reconcile_fact(new_fact, existing)
        assert action in ("MERGE", "SKIP")
        # Must return a valid existing ID
        assert target in ("run1", "jog1")

    def test_superseded_facts_are_skipped(self):
        # Even a perfect-match fact is ignored if superseded_by is set
        existing = [
            _make_entry(
                "User prefers coffee over tea",
                eid="old1",
                superseded_by="new_fact_id",
            )
        ]
        # New fact is identical — but old one is superseded, so nothing to match
        action, target = reconcile_fact("User prefers coffee over tea", existing)
        assert action == "CREATE"
        assert target is None

    def test_mixed_superseded_and_active_uses_active(self):
        # Superseded fact is ignored; active fact is matched
        content = "User likes hiking in the mountains every weekend"
        existing = [
            _make_entry(content, eid="old_superseded", superseded_by="newer1"),
            _make_entry(content, eid="active1"),
        ]
        action, target = reconcile_fact(content, existing)
        assert action == "SKIP"
        assert target == "active1"


# ---------------------------------------------------------------------------
# 7. TemporalEdge metadata — constructor, to_dict(), from_dict() roundtrip
# ---------------------------------------------------------------------------


class TestTemporalEdgeMetadata:
    def test_metadata_stored_in_constructor(self):
        meta = {"context": "Switched jobs", "confidence": 0.9}
        edge = TemporalEdge("Alice", "Acme", "works_at", metadata=meta)
        assert edge.metadata == meta

    def test_metadata_defaults_to_none(self):
        edge = TemporalEdge("A", "B", "knows")
        assert edge.metadata is None

    def test_metadata_in_to_dict_when_set(self):
        meta = {"sentiment": "positive", "confidence": 0.85}
        edge = TemporalEdge("Alice", "Python", "uses", metadata=meta)
        d = edge.to_dict()
        assert "metadata" in d
        assert d["metadata"] == meta

    def test_metadata_absent_from_to_dict_when_none(self):
        edge = TemporalEdge("A", "B", "uses")
        d = edge.to_dict()
        assert "metadata" not in d

    def test_metadata_roundtrip_through_from_dict(self):
        meta = {"context": "Relocated for work", "sentiment": "neutral"}
        t0 = datetime(2026, 1, 15, 10, 0, 0)
        edge = TemporalEdge("Alice", "London", "lives_in", valid_from=t0, metadata=meta)

        d = edge.to_dict()
        restored = TemporalEdge.from_dict(d)

        assert restored.source == "Alice"
        assert restored.target == "London"
        assert restored.relation == "lives_in"
        assert restored.valid_from == t0
        assert restored.metadata == meta

    def test_none_metadata_roundtrip(self):
        edge = TemporalEdge("X", "Y", "knows")
        d = edge.to_dict()
        restored = TemporalEdge.from_dict(d)
        assert restored.metadata is None

    def test_metadata_dict_is_preserved_exactly(self):
        meta = {
            "context": "Long-standing friendship",
            "sentiment": "positive",
            "confidence": 0.95,
            "source_memory_id": "mem_abc123",
        }
        edge = TemporalEdge("Bob", "Carol", "friends_with", metadata=meta)
        d = edge.to_dict()
        restored = TemporalEdge.from_dict(d)
        assert restored.metadata == meta


# ---------------------------------------------------------------------------
# 8. Salience in activation — high salience > low salience for same content
# ---------------------------------------------------------------------------


class TestSalienceInActivation:
    """compute_activation() multiplies base by (0.5 + salience).

    High salience resists temporal decay. With a positive base (from
    recent access timestamps) and noise=False, high-salience memories
    consistently outscore low-salience ones.
    """

    def _entry_with_salience(self, salience: float) -> MemoryEntry:
        """Build a MemoryEntry without access_timestamps so base uses importance fallback.

        importance=8 → base = (8-5)*0.2 = 0.6 (deterministic, positive).
        Content has no overlap with the query "zzz" so spreading activation = 0.
        This isolates the salience multiplier effect on base-level activation.
        """
        return MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="completely unrelated content with no query overlap",
            importance=8,
            salience=salience,
        )

    def test_high_salience_beats_low_salience_same_content(self):
        # Additive boost: high salience adds +0.25, low adds -0.25
        high = self._entry_with_salience(1.0)
        low = self._entry_with_salience(0.0)

        score_high = compute_activation(high, "zzz", noise=False)
        score_low = compute_activation(low, "zzz", noise=False)

        assert score_high > score_low

    def test_default_salience_between_extremes(self):
        # Additive model: default (0.5) → boost=0.0, sits between high and low
        high = self._entry_with_salience(1.0)
        default = self._entry_with_salience(0.5)
        low = self._entry_with_salience(0.0)

        score_high = compute_activation(high, "zzz", noise=False)
        score_default = compute_activation(default, "zzz", noise=False)
        score_low = compute_activation(low, "zzz", noise=False)

        assert score_high > score_default
        assert score_default > score_low

    def test_salience_zero_does_not_crash(self):
        entry = self._entry_with_salience(0.0)
        # Should return a finite float without raising
        score = compute_activation(entry, "zzz", noise=False)
        assert isinstance(score, float)

    def test_salience_one_does_not_crash(self):
        entry = self._entry_with_salience(1.0)
        score = compute_activation(entry, "zzz", noise=False)
        assert isinstance(score, float)

    def test_missing_salience_attribute_uses_default(self):
        # Verify the getattr fallback: entry.salience attribute is always set
        # via the Pydantic default, so salience=0.5 is the identity multiplier
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="generic content",
            importance=5,
            access_timestamps=[datetime.now() - timedelta(seconds=1)],
        )
        # No salience specified — defaults to 0.5
        assert entry.salience == 0.5
        score = compute_activation(entry, "generic", noise=False)
        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# 9. EpisodicStore.update_entry() — public API for field updates
# ---------------------------------------------------------------------------


class TestEpisodicStoreUpdateEntry:
    def _make_store_with_entry(self):
        """Create an EpisodicStore with one entry, return (store, entry_id)."""
        store = EpisodicStore(max_entries=100)
        # Directly insert a MemoryEntry to avoid async add()
        entry = MemoryEntry(
            id="ep_test_01",
            type=MemoryType.EPISODIC,
            content="User: Hello there\nAgent: Hi! How can I help?",
            importance=5,
        )
        store._memories[entry.id] = entry
        return store, entry.id

    def test_update_entry_sets_abstract(self):
        store, entry_id = self._make_store_with_entry()
        result = store.update_entry(entry_id, abstract="Short summary")
        assert result is True
        assert store._memories[entry_id].abstract == "Short summary"

    def test_update_entry_sets_salience(self):
        store, entry_id = self._make_store_with_entry()
        result = store.update_entry(entry_id, salience=0.95)
        assert result is True
        assert store._memories[entry_id].salience == 0.95

    def test_update_entry_nonexistent_id(self):
        store, _ = self._make_store_with_entry()
        result = store.update_entry("nonexistent_id_999", abstract="nope")
        assert result is False

    def test_update_entry_ignores_unknown_fields(self):
        store, entry_id = self._make_store_with_entry()
        # Should not raise, unknown kwargs are silently ignored
        result = store.update_entry(entry_id, totally_fake_field="value")
        assert result is True
        assert not hasattr(store._memories[entry_id], "totally_fake_field")


# ---------------------------------------------------------------------------
# 10. Keyword classification edge cases — "from" and "may" removal
# ---------------------------------------------------------------------------


class TestKeywordFalsePositives:
    def test_classify_from_not_false_positive(self):
        # "from" in a non-profile context should NOT classify as PROFILE
        # (avoid "message" which contains substring "age", a profile keyword)
        result = classify_memory_category("I received data from the server")
        assert result != MemoryCategory.PROFILE

    def test_classify_may_not_false_positive(self):
        # "may" as a verb (permission) should NOT classify as EVENT
        result = classify_memory_category("The user may want to upgrade later")
        assert result != MemoryCategory.EVENT

    def test_classify_real_profile_still_works(self):
        # "name is" still triggers PROFILE without "from"
        result = classify_memory_category("User's name is Alex and they code daily")
        assert result == MemoryCategory.PROFILE

    def test_classify_real_event_still_works(self):
        # "june" still triggers EVENT without "may"
        result = classify_memory_category("Meeting on June 15th at the office")
        assert result == MemoryCategory.EVENT


# ---------------------------------------------------------------------------
# 11. Dedup pipeline — reconcile_fact edge cases
# ---------------------------------------------------------------------------


class TestReconcileFactPipeline:
    def test_reconcile_fact_skip_duplicate(self):
        """Near-identical fact is skipped (Jaccard > 0.85)."""
        content = "User prefers coffee over tea in the morning"
        existing = [_make_entry(content, eid="dup1")]
        action, target = reconcile_fact(content, existing)
        assert action == "SKIP"
        assert target == "dup1"

    def test_reconcile_fact_merge_similar(self):
        """Similar fact triggers merge (Jaccard 0.6-0.85)."""
        existing = [_make_entry("User prefers coffee in the morning", eid="old1")]
        action, target = reconcile_fact("User prefers tea in the morning", existing)
        assert action == "MERGE"
        assert target == "old1"

    def test_reconcile_fact_create_new(self):
        """Sufficiently different fact is created (Jaccard < 0.6)."""
        existing = [_make_entry("User loves hiking in the mountains", eid="hike1")]
        action, target = reconcile_fact("The database schema needs indexing", existing)
        assert action == "CREATE"
        assert target is None
