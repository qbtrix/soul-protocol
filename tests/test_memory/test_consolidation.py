# tests/test_memory/test_consolidation.py — Tests for consolidate(), GeneralEvent wiring,
#   and fact conflict resolution.
# Created: v0.2.2 — Covers reflect auto-apply, Conway hierarchy, supersede logic,
#   serialization round-trips, and backwards compatibility.

from __future__ import annotations

from datetime import datetime

import pytest

from soul_protocol.memory.manager import MemoryManager
from soul_protocol.soul import Soul
from soul_protocol.types import (
    CoreMemory,
    GeneralEvent,
    Interaction,
    MemoryEntry,
    MemorySettings,
    MemoryType,
    ReflectionResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager() -> MemoryManager:
    return MemoryManager(core=CoreMemory(), settings=MemorySettings())


def _make_reflection(
    *,
    summaries: list[dict] | None = None,
    themes: list[str] | None = None,
    self_insight: str = "",
    emotional_patterns: str = "",
) -> ReflectionResult:
    return ReflectionResult(
        summaries=summaries or [],
        themes=themes or [],
        self_insight=self_insight,
        emotional_patterns=emotional_patterns,
    )


# ---------------------------------------------------------------------------
# consolidate() — summaries → semantic
# ---------------------------------------------------------------------------


class TestConsolidateSummaries:
    async def test_summaries_become_semantic_memories(self, manager):
        result = _make_reflection(summaries=[
            {"summary": "User is learning Rust programming", "importance": 7},
            {"summary": "User prefers typed languages", "importance": 6},
        ])
        applied = await manager.consolidate(result)
        assert applied["summaries"] == 2

        facts = manager._semantic.facts()
        contents = [f.content for f in facts]
        assert "User is learning Rust programming" in contents
        assert "User prefers typed languages" in contents

    async def test_empty_summary_skipped(self, manager):
        result = _make_reflection(summaries=[{"summary": "", "importance": 5}])
        applied = await manager.consolidate(result)
        assert applied["summaries"] == 0

    async def test_importance_clamped(self, manager):
        result = _make_reflection(summaries=[
            {"summary": "High importance fact", "importance": 999},
            {"summary": "Low importance fact", "importance": -5},
        ])
        await manager.consolidate(result)
        facts = manager._semantic.facts()
        importances = {f.content: f.importance for f in facts}
        assert importances["High importance fact"] == 10
        assert importances["Low importance fact"] == 1

    async def test_no_summaries_noop(self, manager):
        result = _make_reflection()
        applied = await manager.consolidate(result)
        assert applied["summaries"] == 0
        assert len(manager._semantic.facts()) == 0


# ---------------------------------------------------------------------------
# consolidate() — themes → GeneralEvents
# ---------------------------------------------------------------------------


class TestConsolidateGeneralEvents:
    async def test_themes_create_general_events(self, manager):
        result = _make_reflection(themes=["python development", "data science"])
        applied = await manager.consolidate(result)
        assert applied["general_events"] == 2
        assert len(manager._general_events) == 2

        themes = [ge.theme for ge in manager._general_events.values()]
        assert "python development" in themes
        assert "data science" in themes

    async def test_duplicate_theme_updates_not_duplicates(self, manager):
        r1 = _make_reflection(themes=["testing"])
        r2 = _make_reflection(themes=["testing"])
        await manager.consolidate(r1)
        await manager.consolidate(r2)
        assert len(manager._general_events) == 1

    async def test_episodes_linked_to_matching_theme(self, manager):
        # Add an episodic memory about python
        await manager.add_episodic(Interaction(
            user_input="I love writing Python scripts for automation",
            agent_output="Python is great for automation!",
        ))

        result = _make_reflection(themes=["python automation"])
        await manager.consolidate(result)

        event = list(manager._general_events.values())[0]
        assert len(event.episode_ids) >= 1

    async def test_no_link_without_match(self, manager):
        await manager.add_episodic(Interaction(
            user_input="The weather is nice today",
            agent_output="Indeed it is!",
        ))

        result = _make_reflection(themes=["quantum computing research"])
        await manager.consolidate(result)

        event = list(manager._general_events.values())[0]
        assert len(event.episode_ids) == 0

    async def test_general_event_id_set_on_episode(self, manager):
        await manager.add_episodic(Interaction(
            user_input="Help me debug this Python error in my FastAPI app",
            agent_output="Let me look at the traceback.",
        ))

        result = _make_reflection(themes=["python debugging"])
        await manager.consolidate(result)

        event = list(manager._general_events.values())[0]
        if event.episode_ids:
            episode = next(
                e for e in manager._episodic.entries()
                if e.id == event.episode_ids[0]
            )
            assert episode.general_event_id == event.id

    async def test_empty_theme_skipped(self, manager):
        result = _make_reflection(themes=["", "valid theme"])
        applied = await manager.consolidate(result)
        assert applied["general_events"] == 1


# ---------------------------------------------------------------------------
# consolidate() — self_insight → self-model
# ---------------------------------------------------------------------------


class TestConsolidateSelfInsight:
    async def test_self_insight_stored(self, manager):
        result = _make_reflection(self_insight="I tend to be most helpful with technical questions")
        applied = await manager.consolidate(result)
        assert applied["self_insight"] is True
        assert "self_insight" in manager._self_model._relationship_notes

    async def test_no_self_insight_noop(self, manager):
        result = _make_reflection(self_insight="")
        applied = await manager.consolidate(result)
        assert applied["self_insight"] is False


# ---------------------------------------------------------------------------
# consolidate() — emotional_patterns → semantic
# ---------------------------------------------------------------------------


class TestConsolidateEmotionalPatterns:
    async def test_emotional_pattern_stored(self, manager):
        result = _make_reflection(emotional_patterns="User shows excitement when discussing AI")
        applied = await manager.consolidate(result)
        assert applied["emotional_pattern"] is True

        facts = manager._semantic.facts()
        assert any("Emotional pattern:" in f.content for f in facts)

    async def test_no_pattern_noop(self, manager):
        result = _make_reflection(emotional_patterns="")
        applied = await manager.consolidate(result)
        assert applied["emotional_pattern"] is False


# ---------------------------------------------------------------------------
# consolidate() — full integration
# ---------------------------------------------------------------------------


class TestConsolidateIntegration:
    async def test_all_fields_applied(self, manager):
        result = _make_reflection(
            summaries=[{"summary": "User is a Python developer", "importance": 8}],
            themes=["software development"],
            self_insight="Good at technical assistance",
            emotional_patterns="Enthusiasm about coding",
        )
        applied = await manager.consolidate(result)
        assert applied["summaries"] == 1
        assert applied["general_events"] == 1
        assert applied["self_insight"] is True
        assert applied["emotional_pattern"] is True

    async def test_empty_result_noop(self, manager):
        result = _make_reflection()
        applied = await manager.consolidate(result)
        assert applied == {
            "summaries": 0,
            "general_events": 0,
            "self_insight": False,
            "emotional_pattern": False,
        }


# ---------------------------------------------------------------------------
# Soul.reflect(apply=True/False)
# ---------------------------------------------------------------------------


class TestReflectApply:
    async def test_reflect_no_engine_returns_none(self):
        soul = await Soul.birth("Aria")
        result = await soul.reflect()
        assert result is None

    async def test_reflect_apply_false_no_side_effects(self):
        """reflect(apply=False) should not consolidate anything.
        With no engine, returns None anyway — verify no crash."""
        soul = await Soul.birth("Aria")
        result = await soul.reflect(apply=False)
        assert result is None


# ---------------------------------------------------------------------------
# Fact conflict resolution
# ---------------------------------------------------------------------------


class TestFactConflicts:
    async def test_same_prefix_supersedes(self, manager):
        """New fact with same template prefix supersedes old fact."""
        old = MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in NYC", importance=7)
        await manager.add(old)

        # Simulate an observe that extracts "User lives in SF"
        new_facts = [MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in SF", importance=7)]
        await manager._resolve_fact_conflicts(new_facts)

        # Old fact should be marked superseded
        all_facts = manager._semantic.facts(include_superseded=True)
        old_fact = next(f for f in all_facts if f.content == "User lives in NYC")
        assert old_fact.superseded_by is not None

    async def test_superseded_filtered_from_search(self, manager):
        """Superseded facts don't appear in search results."""
        old = MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in NYC", importance=7)
        await manager.add(old)

        new = MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in SF", importance=7)
        await manager._resolve_fact_conflicts([new])
        await manager.add(new)

        results = await manager._semantic.search("lives")
        contents = [r.content for r in results]
        assert "User lives in SF" in contents
        assert "User lives in NYC" not in contents

    async def test_superseded_filtered_from_facts(self, manager):
        """facts() by default excludes superseded entries."""
        old = MemoryEntry(type=MemoryType.SEMANTIC, content="User prefers dark mode", importance=7)
        await manager.add(old)
        new = MemoryEntry(type=MemoryType.SEMANTIC, content="User prefers light mode", importance=7)
        await manager._resolve_fact_conflicts([new])
        await manager.add(new)

        active = manager._semantic.facts()
        assert not any(f.content == "User prefers dark mode" for f in active)
        assert any(f.content == "User prefers light mode" for f in active)

    async def test_include_superseded_shows_all(self, manager):
        """facts(include_superseded=True) shows old facts."""
        old = MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in NYC", importance=7)
        await manager.add(old)
        new = MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in SF", importance=7)
        await manager._resolve_fact_conflicts([new])
        await manager.add(new)

        all_facts = manager._semantic.facts(include_superseded=True)
        contents = [f.content for f in all_facts]
        assert "User lives in NYC" in contents
        assert "User lives in SF" in contents

    async def test_different_prefix_no_conflict(self, manager):
        """Facts with different prefixes don't conflict."""
        await manager.add(
            MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in NYC", importance=7)
        )
        new_facts = [
            MemoryEntry(type=MemoryType.SEMANTIC, content="User prefers dark mode", importance=7)
        ]
        await manager._resolve_fact_conflicts(new_facts)

        # No facts should be superseded
        all_facts = manager._semantic.facts(include_superseded=True)
        assert all(f.superseded_by is None for f in all_facts)

    async def test_exact_duplicate_not_conflicted(self, manager):
        """Identical content is not a conflict (it's a duplicate)."""
        await manager.add(
            MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in NYC", importance=7)
        )
        same = [MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in NYC", importance=7)]
        await manager._resolve_fact_conflicts(same)

        all_facts = manager._semantic.facts(include_superseded=True)
        assert all(f.superseded_by is None for f in all_facts)

    async def test_conflict_via_observe(self, manager):
        """Full pipeline: observe() detects and resolves conflicts."""
        # First interaction sets a fact
        await manager.observe(Interaction(
            user_input="I live in New York",
            agent_output="New York is a great city!",
        ))

        facts_before = manager._semantic.facts()
        ny_facts = [f for f in facts_before if "New York" in f.content or "new york" in f.content.lower()]

        # Second interaction updates the fact
        await manager.observe(Interaction(
            user_input="I live in San Francisco now",
            agent_output="SF is wonderful!",
        ))

        active_facts = manager._semantic.facts()
        all_facts = manager._semantic.facts(include_superseded=True)

        # Should have more total facts than active (some superseded)
        # At minimum, the new location fact should be active
        sf_active = [f for f in active_facts if "San Francisco" in f.content or "san francisco" in f.content.lower()]
        if ny_facts and sf_active:
            # If both were extracted, old should be superseded
            assert len(all_facts) > len(active_facts)


# ---------------------------------------------------------------------------
# MemoryEntry.superseded_by backwards compat
# ---------------------------------------------------------------------------


class TestSupersededByBackwardsCompat:
    def test_defaults_to_none(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test", importance=5)
        assert entry.superseded_by is None

    def test_serialization_roundtrip(self):
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="old fact",
            importance=5,
            superseded_by="new-fact-id",
        )
        data = entry.model_dump(mode="json")
        restored = MemoryEntry.model_validate(data)
        assert restored.superseded_by == "new-fact-id"

    def test_old_data_without_field(self):
        """v0.2.1 data without superseded_by still validates."""
        data = {
            "type": "semantic",
            "content": "some fact",
            "importance": 5,
        }
        entry = MemoryEntry.model_validate(data)
        assert entry.superseded_by is None


# ---------------------------------------------------------------------------
# GeneralEvent serialization round-trip
# ---------------------------------------------------------------------------


class TestGeneralEventSerialization:
    async def test_to_dict_includes_general_events(self, manager):
        result = _make_reflection(themes=["testing patterns"])
        await manager.consolidate(result)

        data = manager.to_dict()
        assert "general_events" in data
        assert len(data["general_events"]) == 1
        assert data["general_events"][0]["theme"] == "testing patterns"

    async def test_from_dict_restores_general_events(self, manager):
        result = _make_reflection(themes=["testing patterns"])
        await manager.consolidate(result)

        data = manager.to_dict()
        restored = MemoryManager.from_dict(data, MemorySettings())
        assert len(restored._general_events) == 1
        event = list(restored._general_events.values())[0]
        assert event.theme == "testing patterns"

    async def test_to_dict_preserves_superseded_facts(self, manager):
        """to_dict() includes superseded facts for full history."""
        old = MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in NYC", importance=7)
        await manager.add(old)
        new = MemoryEntry(type=MemoryType.SEMANTIC, content="User lives in SF", importance=7)
        await manager._resolve_fact_conflicts([new])
        await manager.add(new)

        data = manager.to_dict()
        contents = [f["content"] for f in data["semantic"]]
        assert "User lives in NYC" in contents
        assert "User lives in SF" in contents

    async def test_from_dict_without_general_events_key(self):
        """v0.2.1 data without general_events key still loads."""
        data = {
            "core": {"persona": "I am Aria.", "human": ""},
            "episodic": [],
            "semantic": [],
            "procedural": [],
            "graph": {},
            "self_model": {},
        }
        manager = MemoryManager.from_dict(data, MemorySettings())
        assert len(manager._general_events) == 0


# ---------------------------------------------------------------------------
# Export/awaken round-trip with general_events
# ---------------------------------------------------------------------------


class TestGeneralEventPersistence:
    async def test_export_awaken_preserves_general_events(self, tmp_path):
        soul = await Soul.birth("Aria")

        # Build up some episodes
        await soul.observe(Interaction(
            user_input="I love Python programming and building tools",
            agent_output="Python is wonderful for tool building!",
        ))

        # Consolidate to create general events
        result = _make_reflection(themes=["python tools"])
        await soul._memory.consolidate(result)

        assert len(soul.general_events) >= 1

        # Export
        path = tmp_path / "aria.soul"
        await soul.export(str(path))

        # Awaken
        restored = await Soul.awaken(str(path))
        assert len(restored.general_events) >= 1
        assert restored.general_events[0].theme == "python tools"

    async def test_save_load_preserves_general_events(self, tmp_path):
        from soul_protocol.storage.file import load_soul_full

        soul = await Soul.birth("Aria")
        result = _make_reflection(themes=["testing"])
        await soul._memory.consolidate(result)

        await soul.save(tmp_path)

        soul_dir = tmp_path / soul.did.replace(":", "_")
        assert (soul_dir / "memory" / "general_events.json").exists()

        _, memory_data = await load_soul_full(soul_dir)
        assert "general_events" in memory_data
        assert len(memory_data["general_events"]) >= 1


# ---------------------------------------------------------------------------
# Soul.general_events property
# ---------------------------------------------------------------------------


class TestSoulGeneralEventsProperty:
    async def test_initially_empty(self):
        soul = await Soul.birth("Aria")
        assert soul.general_events == []

    async def test_populated_after_consolidate(self):
        soul = await Soul.birth("Aria")
        result = _make_reflection(themes=["coding", "debugging"])
        await soul._memory.consolidate(result)
        assert len(soul.general_events) == 2
        themes = [ge.theme for ge in soul.general_events]
        assert "coding" in themes
        assert "debugging" in themes
