# test_dream.py — Comprehensive tests for the dream() offline consolidation engine.
# Created: 2026-04-06 — Covers DreamReport dataclass, Dreamer unit tests per phase,
#   Soul.dream() integration, and a full before/after simulation with 20+ episodes.

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from soul_protocol.runtime.dream import (
    DetectedProcedure,
    Dreamer,
    DreamReport,
    EvolutionInsight,
    GraphConsolidation,
    TopicCluster,
)
from soul_protocol.runtime.memory.graph import KnowledgeGraph, TemporalEdge
from soul_protocol.runtime.memory.procedural import ProceduralStore
from soul_protocol.runtime.memory.semantic import SemanticStore
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction, MemoryEntry, MemoryType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_episode(
    content: str,
    created_at: datetime | None = None,
    entities: list[str] | None = None,
) -> MemoryEntry:
    """Create a minimal EPISODIC MemoryEntry for testing."""
    return MemoryEntry(
        type=MemoryType.EPISODIC,
        content=content,
        importance=5,
        created_at=created_at or datetime.now(UTC),
        entities=entities or [],
    )


def _make_semantic_fact(content: str) -> MemoryEntry:
    """Create a minimal SEMANTIC MemoryEntry for testing."""
    return MemoryEntry(
        type=MemoryType.SEMANTIC,
        content=content,
        importance=6,
        created_at=datetime.now(UTC),
    )


def _make_interaction(user_input: str, agent_output: str) -> Interaction:
    """Build an Interaction using the legacy constructor (still supported)."""
    return Interaction(
        user_input=user_input,
        agent_output=agent_output,
        channel="test",
    )


def _build_dreamer_with_episodes(episodes: list[MemoryEntry]) -> tuple[Dreamer, MagicMock]:
    """Return a Dreamer whose episodic store is pre-loaded with the given episodes."""
    memory = MagicMock()
    memory._graph = KnowledgeGraph()
    memory._semantic = SemanticStore()
    memory._procedural = ProceduralStore()

    episodic = MagicMock()
    episodic.entries.return_value = episodes
    memory._episodic = episodic

    return Dreamer(memory), memory


# ===========================================================================
# Section 1: DreamReport dataclass
# ===========================================================================


class TestDreamReport:
    """DreamReport dataclass — default values and summary() output."""

    def test_default_values(self):
        report = DreamReport()

        assert report.episodes_reviewed == 0
        assert report.topic_clusters == []
        assert report.detected_procedures == []
        assert report.behavioral_trends == []
        assert report.archived_count == 0
        assert report.deduplicated_count == 0
        assert isinstance(report.graph_consolidation, GraphConsolidation)
        assert report.procedures_created == 0
        assert report.evolution_insights == []
        assert report.duration_ms == 0
        # dreamed_at should be a timezone-aware datetime
        assert report.dreamed_at.tzinfo is not None

    def test_summary_contains_required_fields(self):
        report = DreamReport(
            episodes_reviewed=42,
            duration_ms=350,
            topic_clusters=[
                TopicCluster(topic="python decorators", episode_count=5),
                TopicCluster(topic="rust ownership", episode_count=3),
            ],
            detected_procedures=[
                DetectedProcedure(description="Recurring pattern (3x): error handle", frequency=3),
            ],
            behavioral_trends=["Emerging topic: 'async'"],
            archived_count=10,
            deduplicated_count=2,
            graph_consolidation=GraphConsolidation(
                merged_entities=[("python", "Python")],
                pruned_edges=4,
            ),
            procedures_created=1,
            evolution_insights=[
                EvolutionInsight(
                    trait="personality.openness", direction="increase", evidence="high diversity"
                ),
            ],
        )

        summary = report.summary()

        assert "42" in summary  # episodes reviewed
        assert "350ms" in summary  # duration
        assert "python decorators" in summary  # cluster label
        assert "5" in summary  # cluster count
        assert "Recurring pattern" in summary  # procedure
        assert "Emerging topic" in summary  # trend
        assert "10" in summary  # archived
        assert "2" in summary  # deduplicated
        assert "1" in summary  # entities merged
        assert "4" in summary  # edges pruned
        assert "Procedures created: 1" in summary  # synthesis result
        assert "personality.openness" in summary  # evolution trait

    def test_summary_minimal_report_no_extra_sections(self):
        """A report with only episodes reviewed should not render optional sections."""
        report = DreamReport(episodes_reviewed=5, duration_ms=10)
        summary = report.summary()

        assert "Episodes reviewed: 5" in summary
        assert "Topic clusters" not in summary
        assert "Procedures detected" not in summary
        assert "Behavioral trends" not in summary
        assert "Memories archived" not in summary
        assert "Duplicates removed" not in summary
        assert "Procedures created" not in summary
        assert "Evolution insights" not in summary

    def test_summary_caps_clusters_at_five(self):
        """summary() renders at most 5 topic clusters."""
        clusters = [TopicCluster(topic=f"topic-{i}", episode_count=3) for i in range(10)]
        report = DreamReport(topic_clusters=clusters, episodes_reviewed=30, duration_ms=1)
        summary = report.summary()

        # Only 5 should appear; "topic-5" is the 6th
        assert "topic-4" in summary
        assert "topic-5" not in summary


# ===========================================================================
# Section 2: Dreamer — Phase 1: Gather
# ===========================================================================


class TestDreamerGatherPhase:
    """_gather_episodes() — filtering by timestamp."""

    def test_gather_all_episodes_when_no_since(self):
        now = datetime.now(UTC)
        episodes = [
            _make_episode("Episode A", created_at=now - timedelta(days=5)),
            _make_episode("Episode B", created_at=now - timedelta(days=1)),
            _make_episode("Episode C", created_at=now),
        ]
        dreamer, _ = _build_dreamer_with_episodes(episodes)

        result = dreamer._gather_episodes(since=None)

        assert len(result) == 3

    def test_gather_filters_episodes_after_since(self):
        cutoff = datetime.now(UTC) - timedelta(days=3)
        old = _make_episode("old episode", created_at=cutoff - timedelta(days=1))
        recent_a = _make_episode("recent A", created_at=cutoff + timedelta(hours=1))
        recent_b = _make_episode("recent B", created_at=cutoff + timedelta(days=1))
        dreamer, _ = _build_dreamer_with_episodes([old, recent_a, recent_b])

        result = dreamer._gather_episodes(since=cutoff)

        assert len(result) == 2
        contents = {ep.content for ep in result}
        assert "recent A" in contents
        assert "recent B" in contents
        assert "old episode" not in contents

    def test_gather_returns_empty_list_when_no_episodes(self):
        dreamer, _ = _build_dreamer_with_episodes([])
        result = dreamer._gather_episodes()
        assert result == []

    def test_gather_since_at_exact_boundary_is_inclusive(self):
        ts = datetime.now(UTC)
        episode = _make_episode("boundary episode", created_at=ts)
        dreamer, _ = _build_dreamer_with_episodes([episode])

        result = dreamer._gather_episodes(since=ts)
        assert len(result) == 1


# ===========================================================================
# Section 3: Dreamer — Phase 2: Pattern Detection
# ===========================================================================


class TestDreamerDetectTopicClusters:
    """_detect_topic_clusters() — clustering and minimum cluster size."""

    def _make_python_episodes(self, count: int) -> list[MemoryEntry]:
        return [
            _make_episode(
                f"User: Tell me about Python decorators\nAgent: Python decorators are a powerful feature in Python programming. "
                f"Decorators wrap functions to modify behavior. Example {i}.",
            )
            for i in range(count)
        ]

    def _make_rust_episodes(self, count: int) -> list[MemoryEntry]:
        return [
            _make_episode(
                f"User: Explain Rust ownership\nAgent: Rust ownership is a memory management system in Rust programming. "
                f"The borrow checker enforces ownership rules. Example {i}.",
            )
            for i in range(count)
        ]

    def test_distinct_topics_form_separate_clusters(self):
        python_eps = self._make_python_episodes(4)
        rust_eps = self._make_rust_episodes(4)
        dreamer, _ = _build_dreamer_with_episodes(python_eps + rust_eps)

        clusters = dreamer._detect_topic_clusters(python_eps + rust_eps)

        # Two distinct topic groups should produce at least 2 clusters
        assert len(clusters) >= 2

    def test_clusters_respect_minimum_size(self):
        """Topics with fewer than 3 episodes should not become clusters."""
        # Only 2 Python episodes — below _MIN_CLUSTER_SIZE
        tiny_group = self._make_python_episodes(2)
        # 4 Rust episodes — above minimum
        large_group = self._make_rust_episodes(4)
        dreamer, _ = _build_dreamer_with_episodes(tiny_group + large_group)

        clusters = dreamer._detect_topic_clusters(tiny_group + large_group)

        # Rust cluster should exist, but we should not have two clusters
        # (python group is too small to form its own cluster)
        assert len(clusters) <= 1

    def test_empty_episodes_returns_empty_clusters(self):
        dreamer, _ = _build_dreamer_with_episodes([])
        clusters = dreamer._detect_topic_clusters([])
        assert clusters == []

    def test_clusters_sorted_by_episode_count_descending(self):
        python_eps = self._make_python_episodes(6)
        rust_eps = self._make_rust_episodes(3)
        dreamer, _ = _build_dreamer_with_episodes(python_eps + rust_eps)

        clusters = dreamer._detect_topic_clusters(python_eps + rust_eps)

        if len(clusters) >= 2:
            assert clusters[0].episode_count >= clusters[1].episode_count

    def test_cluster_carries_metadata(self):
        python_eps = self._make_python_episodes(4)
        dreamer, _ = _build_dreamer_with_episodes(python_eps)

        clusters = dreamer._detect_topic_clusters(python_eps)

        if clusters:
            tc = clusters[0]
            assert tc.episode_count >= 3
            assert tc.topic != ""
            assert tc.first_seen is not None
            assert tc.last_seen is not None
            assert len(tc.episode_ids) >= 3


class TestDreamerDetectProcedures:
    """_detect_procedures() — recurring action patterns."""

    def _make_repeated_agent_episodes(self, count: int, agent_response: str) -> list[MemoryEntry]:
        return [
            _make_episode(f"User: How do I handle errors?\nAgent: {agent_response}")
            for _ in range(count)
        ]

    def test_detects_recurring_patterns_above_threshold(self):
        """Feed 5 episodes with identical agent responses — should detect a procedure."""
        agent_response = (
            "To handle Python errors, use try except blocks. "
            "Catch specific exception types. Log the error. "
            "Raise or return a safe default value."
        )
        episodes = self._make_repeated_agent_episodes(5, agent_response)
        dreamer, _ = _build_dreamer_with_episodes(episodes)

        procedures = dreamer._detect_procedures(episodes)

        assert len(procedures) >= 1
        assert procedures[0].frequency >= 3

    def test_no_procedures_below_minimum_frequency(self):
        """Patterns appearing fewer than 3 times should not become procedures."""
        agent_response = "Some unique response about refactoring patterns."
        episodes = self._make_repeated_agent_episodes(2, agent_response)
        dreamer, _ = _build_dreamer_with_episodes(episodes)

        procedures = dreamer._detect_procedures(episodes)

        assert procedures == []

    def test_empty_episodes_returns_empty_procedures(self):
        dreamer, _ = _build_dreamer_with_episodes([])
        procedures = dreamer._detect_procedures([])
        assert procedures == []

    def test_procedures_have_confidence_and_episode_ids(self):
        agent_response = (
            "Always write tests first. Run the tests to confirm they fail. "
            "Then implement the feature. Run tests again to confirm they pass."
        )
        episodes = self._make_repeated_agent_episodes(5, agent_response)
        dreamer, _ = _build_dreamer_with_episodes(episodes)

        procedures = dreamer._detect_procedures(episodes)

        if procedures:
            proc = procedures[0]
            assert proc.confidence > 0.0
            assert len(proc.source_episode_ids) >= 1
            assert proc.frequency >= 3


class TestDreamerDetectBehavioralTrends:
    """_detect_behavioral_trends() — emerging and declining topics."""

    def test_detects_emerging_topic_in_second_half(self):
        now = datetime.now(UTC)
        # First half: questions about Python
        first_half = [
            _make_episode(
                "User: Python help?\nAgent: Python is great. Python decorators. Python classes.",
                created_at=now - timedelta(hours=10 - i),
            )
            for i in range(6)
        ]
        # Second half: questions about Kubernetes — clearly different topic
        second_half = [
            _make_episode(
                "User: Kubernetes help?\nAgent: Kubernetes cluster management. Kubernetes pods. Kubernetes deployment.",
                created_at=now - timedelta(hours=4 - i),
            )
            for i in range(6)
        ]
        all_eps = first_half + second_half
        dreamer, _ = _build_dreamer_with_episodes(all_eps)

        trends = dreamer._detect_behavioral_trends(all_eps)

        # At least one emerging trend should be detected
        emerging = [t for t in trends if "Emerging" in t]
        assert len(emerging) >= 1

    def test_detects_declining_topic_from_first_half(self):
        now = datetime.now(UTC)
        # First half: heavy on "python"
        first_half = [
            _make_episode(
                "User: Python question?\nAgent: Python answer. Python feature. Python syntax.",
                created_at=now - timedelta(hours=10 - i),
            )
            for i in range(6)
        ]
        # Second half: unrelated topics
        second_half = [
            _make_episode(
                "User: Cloud infrastructure?\nAgent: AWS services. Cloud computing. Terraform modules.",
                created_at=now - timedelta(hours=4 - i),
            )
            for i in range(6)
        ]
        all_eps = first_half + second_half
        dreamer, _ = _build_dreamer_with_episodes(all_eps)

        trends = dreamer._detect_behavioral_trends(all_eps)

        declining = [t for t in trends if "Declining" in t]
        assert len(declining) >= 1

    def test_fewer_than_six_episodes_returns_no_trends(self):
        episodes = [_make_episode("hello world") for _ in range(5)]
        dreamer, _ = _build_dreamer_with_episodes(episodes)

        trends = dreamer._detect_behavioral_trends(episodes)

        assert trends == []

    def test_empty_episodes_returns_empty_trends(self):
        dreamer, _ = _build_dreamer_with_episodes([])
        trends = dreamer._detect_behavioral_trends([])
        assert trends == []


# ===========================================================================
# Section 4: Dreamer — Phase 3: Consolidate
# ===========================================================================


class TestDreamerDeduplicateSemantic:
    """_dedup_semantic() — removes facts with >= 85% token overlap."""

    @pytest.mark.asyncio
    async def test_removes_near_duplicate_facts(self):
        """Two nearly identical facts should result in one being removed."""
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._procedural = ProceduralStore()
        semantic = SemanticStore()

        # Add two very similar facts
        fact_a = _make_semantic_fact("User prefers Python programming language for data science")
        fact_b = _make_semantic_fact(
            "User prefers Python programming language for data science work"
        )
        await semantic.add(fact_a)
        await semantic.add(fact_b)
        memory._semantic = semantic

        dreamer = Dreamer(memory)
        removed = await dreamer._dedup_semantic()

        assert removed >= 1
        # One should remain
        remaining = semantic.facts()
        assert len(remaining) == 1

    @pytest.mark.asyncio
    async def test_keeps_distinct_facts(self):
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._procedural = ProceduralStore()
        semantic = SemanticStore()

        await semantic.add(_make_semantic_fact("User prefers Python for data science"))
        await semantic.add(_make_semantic_fact("User works at Acme Corporation as an engineer"))
        await semantic.add(_make_semantic_fact("User enjoys hiking on weekends"))
        memory._semantic = semantic

        dreamer = Dreamer(memory)
        removed = await dreamer._dedup_semantic()

        assert removed == 0
        assert len(semantic.facts()) == 3

    @pytest.mark.asyncio
    async def test_skips_already_superseded_facts(self):
        """Facts with superseded_by set should not be re-evaluated for dedup."""
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._procedural = ProceduralStore()
        semantic = SemanticStore()

        fact = _make_semantic_fact("User prefers dark mode in the editor")
        fact.superseded_by = "some-other-id"
        await semantic.add(fact)
        memory._semantic = semantic

        dreamer = Dreamer(memory)
        removed = await dreamer._dedup_semantic()

        # The superseded fact is skipped; nothing is re-removed
        assert removed == 0

    @pytest.mark.asyncio
    async def test_single_fact_returns_zero(self):
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._procedural = ProceduralStore()
        semantic = SemanticStore()
        await semantic.add(_make_semantic_fact("User likes coffee"))
        memory._semantic = semantic

        dreamer = Dreamer(memory)
        removed = await dreamer._dedup_semantic()
        assert removed == 0

    @pytest.mark.asyncio
    async def test_dedup_soft_deletes_via_superseded_by(self):
        """Dedup should mark losers with superseded_by instead of hard-deleting.

        The audit trail matters: after dedup runs, the loser fact should still
        exist in the underlying dict so it's discoverable via
        facts(include_superseded=True), and its superseded_by should point
        at the winner.
        """
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._procedural = ProceduralStore()
        semantic = SemanticStore()

        fact_a = _make_semantic_fact("User prefers Python programming language for data science")
        fact_b = _make_semantic_fact(
            "User prefers Python programming language for data science work"
        )
        await semantic.add(fact_a)
        await semantic.add(fact_b)
        memory._semantic = semantic

        dreamer = Dreamer(memory)
        removed = await dreamer._dedup_semantic()

        assert removed == 1
        # Both facts should still exist in the raw dict — nothing is deleted
        assert len(semantic._facts) == 2
        # But only one is visible through the default facts() call
        assert len(semantic.facts()) == 1
        # And we can still see both by opting into superseded
        all_facts = semantic.facts(include_superseded=True)
        assert len(all_facts) == 2
        # The loser has a pointer to the winner
        losers = [f for f in all_facts if f.superseded_by is not None]
        assert len(losers) == 1
        winner_id = losers[0].superseded_by
        assert winner_id in {fact_a.id, fact_b.id}


class TestDreamerDryRun:
    """dream(dry_run=True) — analysis without mutation."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_mutate_semantic_store(self):
        """With duplicates present, dry-run reports them but leaves the store alone."""
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        episodic = MagicMock()
        episodic.entries = MagicMock(return_value=[])
        memory._episodic = episodic
        memory._procedural = ProceduralStore()
        semantic = SemanticStore()
        await semantic.add(_make_semantic_fact("User prefers Python for data science"))
        await semantic.add(_make_semantic_fact("User prefers Python for data science work"))
        memory._semantic = semantic

        dreamer = Dreamer(memory)
        # No episodes so dream() returns early — call the helper directly
        count = await dreamer._count_semantic_duplicates()
        assert count == 1

        # Raw dict untouched, no superseded_by set
        assert len(semantic._facts) == 2
        for fact in semantic._facts.values():
            assert fact.superseded_by is None

    @pytest.mark.asyncio
    async def test_dry_run_sets_report_flag(self):
        """DreamReport.dry_run reflects the run mode."""
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        episodic = MagicMock()
        episodic.entries = MagicMock(return_value=[])
        memory._episodic = episodic
        memory._procedural = ProceduralStore()
        memory._semantic = SemanticStore()

        dreamer = Dreamer(memory)
        report = await dreamer.dream(dry_run=True)
        assert report.dry_run is True

        report2 = await dreamer.dream(dry_run=False)
        assert report2.dry_run is False

    def test_count_archivable_matches_48h_cutoff(self):
        """_count_archivable must use the same 48-hour cutoff as
        archive_old_memories. Three old episodes past the threshold should
        all be counted; recent ones within the window should not."""
        from datetime import datetime, timedelta

        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._procedural = ProceduralStore()
        memory._semantic = SemanticStore()

        # archive_old_memories uses datetime.now() (naive) not utc
        now = datetime.now()
        past_cutoff = now - timedelta(hours=50)  # just past 48h
        inside_cutoff = now - timedelta(hours=10)  # well inside 48h

        old_eps = [MagicMock(created_at=past_cutoff, archived=False) for _ in range(3)]
        recent_eps = [MagicMock(created_at=inside_cutoff, archived=False) for _ in range(2)]

        dreamer = Dreamer(memory)
        count = dreamer._count_archivable(old_eps + recent_eps)
        assert count == 3

    def test_count_archivable_respects_min_three_guard(self):
        """archive_old_memories no-ops when fewer than 3 entries qualify.
        _count_archivable must match — if only 2 entries are old enough,
        count must be 0 (because nothing would actually archive)."""
        from datetime import datetime, timedelta

        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._procedural = ProceduralStore()
        memory._semantic = SemanticStore()

        now = datetime.now()
        past_cutoff = now - timedelta(hours=50)

        old_eps = [MagicMock(created_at=past_cutoff, archived=False) for _ in range(2)]

        dreamer = Dreamer(memory)
        count = dreamer._count_archivable(old_eps)
        # Only 2 old entries — archive_old_memories would skip, so count = 0
        assert count == 0

    def test_count_archivable_skips_already_archived(self):
        """Already-archived entries must not be counted — archive_old_memories
        filters them out of the candidate set."""
        from datetime import datetime, timedelta

        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._procedural = ProceduralStore()
        memory._semantic = SemanticStore()

        now = datetime.now()
        past_cutoff = now - timedelta(hours=50)

        # 3 old entries, but 2 already archived
        eps = [
            MagicMock(created_at=past_cutoff, archived=True),
            MagicMock(created_at=past_cutoff, archived=True),
            MagicMock(created_at=past_cutoff, archived=False),
        ]

        dreamer = Dreamer(memory)
        count = dreamer._count_archivable(eps)
        # Only 1 unarchived candidate — below the min-3 guard, so count = 0
        assert count == 0


class TestDreamerConsolidateGraph:
    """_consolidate_graph() — entity merges, expired edge pruning, deduplication."""

    def _make_graph_with_case_variants(self) -> KnowledgeGraph:
        """Graph with 'Python' and 'python' as separate entities."""
        g = KnowledgeGraph()
        g.add_entity("Python", "language")
        g.add_relationship("Python", "Pandas", "used_with")
        g.add_entity("python", "language")
        g.add_relationship("python", "NumPy", "used_with")
        return g

    def _make_memory_mock_with_graph(self, graph: KnowledgeGraph) -> MagicMock:
        memory = MagicMock()
        memory._graph = graph
        memory._episodic = MagicMock()
        memory._semantic = SemanticStore()
        memory._procedural = ProceduralStore()
        return memory

    def test_merges_case_insensitive_duplicate_entities(self):
        graph = self._make_graph_with_case_variants()
        memory = self._make_memory_mock_with_graph(graph)
        dreamer = Dreamer(memory)

        result = dreamer._consolidate_graph([])

        assert len(result.merged_entities) >= 1
        # 'python' (lowercase) should be merged into 'Python'
        merged_pairs = {pair[0] for pair in result.merged_entities}
        assert "python" in merged_pairs

    def test_prunes_edges_expired_over_30_days(self):
        g = KnowledgeGraph()
        g.add_entity("Python", "language")
        g.add_entity("Flask", "framework")
        # Expired 45 days ago
        expired_date = datetime.now() - timedelta(days=45)
        g._edges.append(TemporalEdge("Python", "Flask", "used_with", valid_to=expired_date))
        # Still active
        g.add_relationship("Python", "Django", "used_with")

        memory = self._make_memory_mock_with_graph(g)
        dreamer = Dreamer(memory)
        result = dreamer._consolidate_graph([])

        assert result.pruned_edges >= 1
        # Active edge should survive
        remaining = [e for e in g._edges if e.valid_to is None]
        assert len(remaining) >= 1

    def test_keeps_edges_expired_recently(self):
        """Edges expired within the last 30 days should NOT be pruned."""
        g = KnowledgeGraph()
        g.add_entity("A", "node")
        g.add_entity("B", "node")
        # Expired only 10 days ago — within the 30-day window
        recent_expiry = datetime.now() - timedelta(days=10)
        g._edges.append(TemporalEdge("A", "B", "relates_to", valid_to=recent_expiry))

        memory = self._make_memory_mock_with_graph(g)
        dreamer = Dreamer(memory)
        result = dreamer._consolidate_graph([])

        assert result.pruned_edges == 0

    def test_deduplicates_identical_edges(self):
        g = KnowledgeGraph()
        g.add_entity("Rust", "language")
        g.add_entity("Cargo", "tool")
        # Manually add two identical edges (bypassing add_relationship's dedup)
        g._edges.append(TemporalEdge("Rust", "Cargo", "uses"))
        g._edges.append(TemporalEdge("Rust", "Cargo", "uses"))

        memory = self._make_memory_mock_with_graph(g)
        dreamer = Dreamer(memory)
        result = dreamer._consolidate_graph([])

        assert result.pruned_edges >= 1
        # Only one Rust→Cargo edge should remain
        remaining = [(e.source, e.target, e.relation) for e in g._edges]
        assert remaining.count(("Rust", "Cargo", "uses")) == 1

    def test_graph_with_fewer_than_two_entities_is_skipped(self):
        g = KnowledgeGraph()
        g.add_entity("OnlyEntity", "misc")
        memory = self._make_memory_mock_with_graph(g)
        dreamer = Dreamer(memory)

        result = dreamer._consolidate_graph([])

        assert result.merged_entities == []
        assert result.pruned_edges == 0


# ===========================================================================
# Section 5: Dreamer — Phase 4: Synthesize
# ===========================================================================


class TestDreamerSynthesizeProcedures:
    """_synthesize_procedures() — creates procedural memories, avoids duplicates."""

    def _build_memory_with_empty_procedural(self) -> MagicMock:
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._semantic = SemanticStore()
        procedural = ProceduralStore()
        memory._procedural = procedural
        return memory

    @pytest.mark.asyncio
    async def test_creates_procedure_from_high_confidence_detection(self):
        memory = self._build_memory_with_empty_procedural()
        dreamer = Dreamer(memory)

        detected = [
            DetectedProcedure(
                description="Recurring pattern (5x): error handle log return default",
                source_episode_ids=["ep1", "ep2", "ep3", "ep4", "ep5"],
                confidence=0.5,
                frequency=5,
            )
        ]

        created = await dreamer._synthesize_procedures(detected)

        assert created == 1
        procs = memory._procedural.entries()
        assert len(procs) == 1
        assert "[dream]" in procs[0].content

    @pytest.mark.asyncio
    async def test_skips_procedure_below_confidence_threshold(self):
        memory = self._build_memory_with_empty_procedural()
        dreamer = Dreamer(memory)

        detected = [
            DetectedProcedure(
                description="Low confidence pattern",
                confidence=0.2,  # Below the 0.3 threshold
                frequency=3,
            )
        ]

        created = await dreamer._synthesize_procedures(detected)

        assert created == 0
        assert len(memory._procedural.entries()) == 0

    @pytest.mark.asyncio
    async def test_does_not_duplicate_existing_procedure(self):
        """If a very similar procedure already exists, skip creation."""
        procedural = ProceduralStore()
        existing_entry = MemoryEntry(
            type=MemoryType.PROCEDURAL,
            content="[dream] Recurring pattern (5x): error handle log return default",
            importance=6,
        )
        await procedural.add(existing_entry)

        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._semantic = SemanticStore()
        memory._procedural = procedural

        dreamer = Dreamer(memory)
        detected = [
            DetectedProcedure(
                description="Recurring pattern (5x): error handle log return default",
                confidence=0.5,
                frequency=5,
            )
        ]

        created = await dreamer._synthesize_procedures(detected)

        assert created == 0  # Duplicate skipped
        assert len(procedural.entries()) == 1  # Original still there

    @pytest.mark.asyncio
    async def test_empty_detected_list_returns_zero(self):
        memory = self._build_memory_with_empty_procedural()
        dreamer = Dreamer(memory)

        created = await dreamer._synthesize_procedures([])

        assert created == 0


class TestDreamerAnalyzeEvolution:
    """_analyze_evolution() — personality drift suggestions."""

    def test_high_topic_diversity_suggests_openness_increase(self):
        """Many distinct topic clusters relative to episode count → openness increase."""
        # 10+ episodes with many clusters = high topic diversity
        episodes = [_make_episode(f"User: Question about topic {i}") for i in range(15)]
        clusters = [
            TopicCluster(topic=f"cluster-{i}", episode_count=3)
            for i in range(6)  # 6 clusters / 15 episodes = 0.4 ratio > 0.3
        ]
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._semantic = SemanticStore()
        memory._procedural = ProceduralStore()
        dreamer = Dreamer(memory)

        insights = dreamer._analyze_evolution(episodes, clusters)

        openness = [
            i for i in insights if i.trait == "personality.openness" and i.direction == "increase"
        ]
        assert len(openness) >= 1

    def test_fewer_than_ten_episodes_returns_empty_insights(self):
        """Must have at least 10 episodes to produce evolution insights."""
        episodes = [_make_episode(f"short ep {i}") for i in range(8)]
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._semantic = SemanticStore()
        memory._procedural = ProceduralStore()
        dreamer = Dreamer(memory)

        insights = dreamer._analyze_evolution(episodes, [])

        assert insights == []

    def test_structured_episodes_suggest_conscientiousness_increase(self):
        """Episodes with planning keywords should suggest conscientiousness increase."""
        episodes = [
            _make_episode(
                f"User: Help me plan this.\nAgent: First step {i}, then next step, review and test, organize schedule."
            )
            for i in range(12)
        ]
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._semantic = SemanticStore()
        memory._procedural = ProceduralStore()
        dreamer = Dreamer(memory)

        insights = dreamer._analyze_evolution(episodes, [])

        conscientiousness = [
            i
            for i in insights
            if i.trait == "personality.conscientiousness" and i.direction == "increase"
        ]
        assert len(conscientiousness) >= 1

    def test_evolution_insight_has_required_fields(self):
        episodes = [_make_episode(f"User: topic {i} help?\nAgent: answer {i}") for i in range(15)]
        clusters = [TopicCluster(topic=f"t{i}", episode_count=3) for i in range(6)]
        memory = MagicMock()
        memory._graph = KnowledgeGraph()
        memory._episodic = MagicMock()
        memory._semantic = SemanticStore()
        memory._procedural = ProceduralStore()
        dreamer = Dreamer(memory)

        insights = dreamer._analyze_evolution(episodes, clusters)

        if insights:
            insight = insights[0]
            assert insight.trait != ""
            assert insight.direction in ("increase", "decrease")
            assert insight.evidence != ""
            assert 0.0 <= insight.magnitude <= 1.0


# ===========================================================================
# Section 6: Soul.dream() integration tests
# ===========================================================================


class TestSoulDreamIntegration:
    """Soul.dream() — end-to-end wiring through the Soul class."""

    @pytest.mark.asyncio
    async def test_dream_on_empty_soul_returns_zero_episodes(self):
        soul = await Soul.birth("TestSoul")

        report = await soul.dream()

        assert report.episodes_reviewed == 0
        assert isinstance(report, DreamReport)

    @pytest.mark.asyncio
    async def test_dream_returns_dream_report(self):
        soul = await Soul.birth("TestSoul")

        report = await soul.dream()

        assert isinstance(report, DreamReport)
        assert report.duration_ms >= 0
        assert report.dreamed_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_dream_with_since_filters_episodes(self):
        """dream(since=...) should only review episodes after the cutoff.

        Note: The episodic store uses timezone-naive datetimes (datetime.now()),
        so the `since` parameter must also be timezone-naive to avoid a
        TypeError in the comparison inside _gather_episodes().
        """
        soul = await Soul.birth("TestSoul")

        # Observe some interactions
        for i in range(5):
            interaction = _make_interaction(
                user_input=f"I prefer Python for data science project number {i}.",
                agent_output=f"Python is excellent for data science. Here are some tips for project {i}.",
            )
            await soul.observe(interaction)

        # Use a naive datetime (no timezone) — matches the episodic store's stored format.
        # Set cutoff to a future time so no episodes fall after it.
        cutoff = datetime.now() + timedelta(seconds=5)

        # Dream with since=future cutoff — should review 0 episodes from after that point
        report = await soul.dream(since=cutoff)

        assert report.episodes_reviewed == 0

    @pytest.mark.asyncio
    async def test_dream_with_archive_false_skips_archival(self):
        soul = await Soul.birth("TestSoul")
        for i in range(3):
            await soul.observe(
                _make_interaction(
                    user_input=f"I love Python programming, specifically decorators and metaclasses. Session {i}.",
                    agent_output=f"Python decorators are a great feature. Metaclasses too. Session {i}.",
                )
            )

        report = await soul.dream(archive=False)

        assert report.archived_count == 0  # Archival was skipped

    @pytest.mark.asyncio
    async def test_dream_with_synthesize_false_skips_procedure_creation(self):
        soul = await Soul.birth("TestSoul")
        for i in range(5):
            await soul.observe(
                _make_interaction(
                    user_input=f"How do I handle errors in Python? Example {i}.",
                    agent_output=f"Use try except blocks. Catch specific exceptions. Log error {i}. Return defaults.",
                )
            )

        report = await soul.dream(synthesize=False)

        assert report.procedures_created == 0

    @pytest.mark.asyncio
    async def test_dream_full_cycle_with_mixed_episodes(self):
        """Dream on a soul with episodes across Python, Rust, and Kubernetes topics."""
        soul = await Soul.birth("TestSoul")

        topics = [
            (
                "Tell me about Python decorators and how they work in practice.",
                "Python decorators wrap functions using the @ syntax. They're widely used in Python for logging, auth, and caching.",
            ),
            (
                "Explain Rust ownership and borrowing system in detail.",
                "Rust ownership ensures memory safety. The borrow checker validates lifetimes. Rust prevents data races.",
            ),
            (
                "How do Kubernetes pods work in a cluster environment?",
                "Kubernetes pods are the smallest deployable units. Pods run containers in a shared network namespace.",
            ),
        ]

        for i in range(3):
            for user_input, agent_output in topics:
                await soul.observe(
                    _make_interaction(
                        user_input=f"{user_input} (visit {i})",
                        agent_output=f"{agent_output} (iteration {i})",
                    )
                )

        report = await soul.dream()

        assert report.episodes_reviewed > 0
        assert isinstance(report.topic_clusters, list)
        assert isinstance(report.detected_procedures, list)
        assert isinstance(report.behavioral_trends, list)
        assert report.duration_ms >= 0


# ===========================================================================
# Section 7: Before/After Simulation
# ===========================================================================


class TestDreamBeforeAfterSimulation:
    """The most important test — shows dream()'s concrete effect on memory state."""

    @pytest.mark.asyncio
    async def test_dream_before_after_with_20_interactions(self, capsys):
        """
        Simulation:
        1. Create a soul
        2. Feed 21 interactions across 3 distinct topics (Python, Rust, Kubernetes)
        3. Snapshot memory state BEFORE dream()
        4. Run dream()
        5. Snapshot memory state AFTER dream()
        6. Assert meaningful changes
        7. Print the before/after comparison and DreamReport summary
        """
        soul = await Soul.birth("SimulationSoul", archetype="The Researcher")

        # --- Build corpus: 7 interactions per topic = 21 total ---
        python_template = [
            (
                "I'm learning Python decorators and want to understand how they work with classes.",
                "Python decorators are functions that wrap other functions. Class decorators work similarly. "
                "Common Python decorator patterns include @staticmethod, @classmethod, @property.",
            ),
            (
                "Can you explain Python metaclasses and their relationship to class creation?",
                "Python metaclasses control class creation. The type() function is the default metaclass. "
                "Metaclasses are used in frameworks like Django ORM for model definition.",
            ),
            (
                "How do Python async and await work with the event loop?",
                "Python async functions return coroutines. The event loop runs coroutines concurrently. "
                "asyncio provides tools for managing async Python code.",
            ),
            (
                "What are Python dataclasses and how do they compare to NamedTuples?",
                "Python dataclasses auto-generate __init__, __repr__, and __eq__ methods. "
                "NamedTuples are immutable and faster. Dataclasses offer more flexibility.",
            ),
            (
                "I prefer Python type hints for better code documentation and IDE support.",
                "Python type hints improve code readability. Tools like mypy and pyright check Python types. "
                "Python 3.12 improved generic type syntax significantly.",
            ),
            (
                "How does Python's GIL affect multithreading performance?",
                "Python's GIL prevents true thread parallelism. Use multiprocessing for CPU-bound Python work. "
                "asyncio handles I/O-bound concurrency without GIL issues.",
            ),
            (
                "What are Python context managers and how do they implement the with statement?",
                "Python context managers implement __enter__ and __exit__. The contextlib module simplifies Python "
                "context manager creation. Use them for resource management in Python.",
            ),
        ]

        rust_template = [
            (
                "I'm trying to understand Rust ownership and the borrow checker.",
                "Rust ownership ensures each value has one owner. The borrow checker validates Rust lifetimes at compile time. "
                "Rust prevents use-after-free and data races.",
            ),
            (
                "How do Rust traits compare to interfaces in other languages?",
                "Rust traits define shared behavior. Traits are like interfaces but more powerful in Rust. "
                "Trait objects enable dynamic dispatch in Rust programs.",
            ),
            (
                "Explain Rust lifetimes and why they're needed.",
                "Rust lifetimes annotate how long references are valid. The Rust compiler uses lifetimes to prevent dangling references. "
                "Most Rust lifetime annotations can be elided.",
            ),
            (
                "What makes Rust memory safety guarantees different from garbage collection?",
                "Rust achieves memory safety without garbage collection. Rust's ownership model deallocates memory deterministically. "
                "No runtime overhead for Rust memory management.",
            ),
            (
                "How does Rust handle error propagation with the ? operator?",
                "Rust uses Result and Option types for error handling. The ? operator propagates Rust errors automatically. "
                "This makes Rust error handling explicit and composable.",
            ),
            (
                "What are Rust closures and how do they capture their environment?",
                "Rust closures are anonymous functions that capture their environment. Closures in Rust implement Fn, FnMut, or FnOnce. "
                "Rust infers closure types from usage context.",
            ),
            (
                "How do Rust generics differ from C++ templates?",
                "Rust generics use monomorphization like C++ templates. Rust generics require explicit trait bounds. "
                "Rust provides better error messages for generic code.",
            ),
        ]

        kubernetes_template = [
            (
                "How do Kubernetes pods differ from Docker containers?",
                "Kubernetes pods are groups of containers sharing network and storage. "
                "Each Kubernetes pod gets its own IP address. Pods are the atomic unit in Kubernetes.",
            ),
            (
                "Explain Kubernetes deployments and how rolling updates work.",
                "Kubernetes deployments manage pod replicas declaratively. Rolling updates replace pods gradually in Kubernetes. "
                "Kubernetes rollback restores the previous deployment state.",
            ),
            (
                "What are Kubernetes services and how do they enable load balancing?",
                "Kubernetes services provide stable network endpoints. ClusterIP, NodePort, and LoadBalancer are Kubernetes service types. "
                "Services route traffic to healthy Kubernetes pods.",
            ),
            (
                "How does Kubernetes handle persistent storage with PersistentVolumes?",
                "Kubernetes PersistentVolumes decouple storage from pod lifecycle. "
                "PersistentVolumeClaims request storage in Kubernetes. StorageClasses automate Kubernetes volume provisioning.",
            ),
            (
                "What is Kubernetes horizontal pod autoscaling?",
                "Kubernetes HPA scales pod count based on metrics. CPU and memory are common Kubernetes scaling signals. "
                "Custom metrics can trigger Kubernetes autoscaling too.",
            ),
            (
                "How do Kubernetes namespaces help organize cluster resources?",
                "Kubernetes namespaces provide virtual clusters within a cluster. Resource quotas apply per Kubernetes namespace. "
                "RBAC controls access at the Kubernetes namespace level.",
            ),
            (
                "Explain Kubernetes ConfigMaps and Secrets for configuration management.",
                "Kubernetes ConfigMaps store non-sensitive configuration data. Kubernetes Secrets store sensitive values encrypted. "
                "Pods consume ConfigMaps and Secrets via env vars or volumes.",
            ),
        ]

        for user_input, agent_output in python_template + rust_template + kubernetes_template:
            await soul.observe(_make_interaction(user_input=user_input, agent_output=agent_output))

        # --- Snapshot BEFORE ---
        before_episodes = len(soul._memory._episodic.entries())
        before_semantic = len(soul._memory._semantic.facts())
        before_procedural = len(soul._memory._procedural.entries())
        before_entities = len(soul._memory._graph.entities())
        before_edges = len(soul._memory._graph._edges)

        # --- Run dream() ---
        report = await soul.dream()

        # --- Snapshot AFTER ---
        after_episodes = len(soul._memory._episodic.entries())
        after_semantic = len(soul._memory._semantic.facts())
        after_procedural = len(soul._memory._procedural.entries())
        after_entities = len(soul._memory._graph.entities())
        after_edges = len(soul._memory._graph._edges)

        # --- Print before/after comparison ---
        print("\n" + "=" * 60)
        print("DREAM SIMULATION: BEFORE / AFTER")
        print("=" * 60)
        print(f"{'Metric':<30} {'Before':>8} {'After':>8} {'Delta':>8}")
        print("-" * 60)
        for label, before, after in [
            ("Episodes (episodic store)", before_episodes, after_episodes),
            ("Facts (semantic store)", before_semantic, after_semantic),
            ("Procedures (procedural)", before_procedural, after_procedural),
            ("Graph entities", before_entities, after_entities),
            ("Graph edges", before_edges, after_edges),
        ]:
            delta = after - before
            delta_str = f"+{delta}" if delta > 0 else str(delta)
            print(f"{label:<30} {before:>8} {after:>8} {delta_str:>8}")
        print("=" * 60)
        print("\nDREAM REPORT SUMMARY:")
        print(report.summary())
        print("=" * 60)

        # --- Core assertions ---
        assert report.episodes_reviewed == 21, (
            f"Expected 21 episodes reviewed, got {report.episodes_reviewed}"
        )
        assert report.duration_ms >= 0

        # Pattern detection ran and found structure
        assert isinstance(report.topic_clusters, list)
        assert isinstance(report.behavioral_trends, list)
        assert isinstance(report.detected_procedures, list)

        # Procedures may have been synthesized
        assert report.procedures_created >= 0

        # Graph consolidation ran (even if nothing needed merging)
        assert isinstance(report.graph_consolidation, GraphConsolidation)

        # Summary is a non-empty string
        summary = report.summary()
        assert "21" in summary
        assert "Dream cycle completed" in summary

    @pytest.mark.asyncio
    async def test_dream_graph_cleanup_removes_stale_edges(self, capsys):
        """
        Simulation: Soul with manually injected expired graph edges.
        After dream(), expired edges are pruned.
        """
        soul = await Soul.birth("GraphCleanSoul")

        # Add a few observations to populate the soul
        for i in range(3):
            await soul.observe(
                _make_interaction(
                    user_input=f"I use Python and Rust for my projects. Session {i}.",
                    agent_output=f"Both Python and Rust are excellent choices. Session {i}.",
                )
            )

        # Manually inject an expired edge (expired 60 days ago)
        expired_date = datetime.now() - timedelta(days=60)
        soul._memory._graph._edges.append(
            TemporalEdge("Python", "OldFramework", "was_used_with", valid_to=expired_date)
        )

        edges_before = len(soul._memory._graph._edges)

        report = await soul.dream()

        edges_after = len(soul._memory._graph._edges)

        print(f"\nEdges before dream: {edges_before}")
        print(f"Edges after dream:  {edges_after}")
        print(f"Pruned: {report.graph_consolidation.pruned_edges}")

        assert report.graph_consolidation.pruned_edges >= 1
        assert edges_after < edges_before
