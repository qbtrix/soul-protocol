# test_retrieval.py — Tests for runtime/context/retrieval.py grep, expand, describe.
# Updated: feat/recall-graded-floor (#247) — Added TestRecallScoresAndFloor, an
#   end-to-end check that RecallEngine.recall() surfaces a per-result
#   activation score on recall_score and that a positive relevance_floor
#   drops weak query matches while strong matches remain. The memory recall
#   path uses in-memory dict stores (EpisodicStore / SemanticStore /
#   ProceduralStore), not the SQLiteContextStore exercised above — that store
#   backs the separate context subsystem. The async fixture style here is
#   kept; the populated_recall fixture builds an in-memory store directly.
#   Also added TestGraphAugmentationExemptFromFloor: graph-augmented recall
#   candidates (surfaced via a related graph entity term, not the original
#   query) survive a positive relevance_floor, while weak *direct* matches
#   are still floored out — the exemption is scoped, not a blanket bypass.
# Created: v0.3.0 — Regex search, DAG expansion, metadata snapshots,
# recursive expansion through multiple compaction levels, and edge cases.

from __future__ import annotations

import pytest

from soul_protocol.runtime.context.retrieval import describe, expand, grep
from soul_protocol.runtime.context.store import SQLiteContextStore
from soul_protocol.runtime.memory.episodic import EpisodicStore
from soul_protocol.runtime.memory.graph import KnowledgeGraph
from soul_protocol.runtime.memory.procedural import ProceduralStore
from soul_protocol.runtime.memory.recall import RecallEngine
from soul_protocol.runtime.memory.semantic import SemanticStore
from soul_protocol.runtime.types import MemoryEntry, MemoryType
from soul_protocol.spec.context.models import (
    CompactionLevel,
    ContextMessage,
    ContextNode,
)


@pytest.fixture
async def store():
    s = SQLiteContextStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
async def populated_store(store):
    """Store with 10 messages for grep/expand tests."""
    for i in range(10):
        await store.append_message(
            ContextMessage(
                id=f"msg{i}",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}: {'hello' if i < 5 else 'goodbye'} world",
                token_count=10,
            )
        )
    return store


# ---------------------------------------------------------------------------
# Grep
# ---------------------------------------------------------------------------


class TestGrep:
    async def test_simple_pattern(self, populated_store):
        results = await grep(populated_store, "hello")
        assert len(results) == 5

    async def test_regex_pattern(self, populated_store):
        results = await grep(populated_store, r"Message \d+:")
        assert len(results) == 10

    async def test_limit(self, populated_store):
        results = await grep(populated_store, "Message", limit=3)
        assert len(results) == 3

    async def test_no_match(self, populated_store):
        results = await grep(populated_store, "nonexistent_pattern_xyz")
        assert len(results) == 0

    async def test_empty_store(self, store):
        results = await grep(store, "anything")
        assert len(results) == 0

    async def test_result_has_message_id(self, populated_store):
        results = await grep(populated_store, "hello")
        for r in results:
            assert r.message_id.startswith("msg")

    async def test_result_has_role(self, populated_store):
        results = await grep(populated_store, "hello")
        roles = {r.role for r in results}
        assert "user" in roles or "assistant" in roles

    async def test_snippet_contains_match(self, populated_store):
        results = await grep(populated_store, "goodbye")
        for r in results:
            assert "goodbye" in r.content_snippet.lower()

    async def test_case_insensitive(self, store):
        await store.append_message(ContextMessage(id="upper", role="user", content="HELLO WORLD"))
        results = await grep(store, "hello")
        assert len(results) == 1

    async def test_special_regex_chars(self, store):
        await store.append_message(
            ContextMessage(id="special", role="user", content="price is $42.00")
        )
        results = await grep(store, r"\$\d+\.\d+")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Expand
# ---------------------------------------------------------------------------


class TestExpand:
    async def test_expand_nonexistent_node(self, store):
        result = await expand(store, "no-such-node")
        assert result.node_id == "no-such-node"
        assert result.original_messages == []

    async def test_expand_summary_node(self, populated_store):
        """Expanding a summary node should recover the original messages."""
        await populated_store.insert_node(
            ContextNode(
                id="sum1",
                level=CompactionLevel.SUMMARY,
                content="A summary",
                token_count=5,
                children_ids=["msg0", "msg1", "msg2"],
                seq_start=1,
                seq_end=3,
            )
        )
        result = await expand(populated_store, "sum1")
        assert result.node_id == "sum1"
        assert result.level == CompactionLevel.SUMMARY
        assert len(result.original_messages) == 3
        contents = [m.content for m in result.original_messages]
        assert any("Message 0" in c for c in contents)

    async def test_expand_preserves_order(self, populated_store):
        await populated_store.insert_node(
            ContextNode(
                id="sum2",
                level=CompactionLevel.SUMMARY,
                content="Summary",
                children_ids=["msg2", "msg0", "msg1"],  # Out of order
                seq_start=1,
                seq_end=3,
            )
        )
        result = await expand(populated_store, "sum2")
        seqs = [m.seq for m in result.original_messages]
        assert seqs == sorted(seqs)

    async def test_recursive_expansion(self, populated_store):
        """Expanding a bullets node that points to a summary that points to messages."""
        # Summary node covering msg0-msg4
        await populated_store.insert_node(
            ContextNode(
                id="sum1",
                level=CompactionLevel.SUMMARY,
                content="Summary",
                children_ids=["msg0", "msg1", "msg2", "msg3", "msg4"],
                seq_start=1,
                seq_end=5,
            )
        )
        # Bullets node covering the summary
        await populated_store.insert_node(
            ContextNode(
                id="bul1",
                level=CompactionLevel.BULLETS,
                content="- Point 1",
                children_ids=["sum1"],
                seq_start=1,
                seq_end=5,
            )
        )
        result = await expand(populated_store, "bul1")
        assert result.level == CompactionLevel.BULLETS
        assert len(result.original_messages) == 5

    async def test_expand_truncated_node(self, populated_store):
        """Truncated nodes should still expand to available messages."""
        await populated_store.insert_node(
            ContextNode(
                id="trunc1",
                level=CompactionLevel.TRUNCATED,
                content="[5 items truncated]",
                children_ids=["msg0", "msg1"],  # Only 2 of 5 are real messages
                seq_start=1,
                seq_end=5,
            )
        )
        result = await expand(populated_store, "trunc1")
        assert result.level == CompactionLevel.TRUNCATED
        assert len(result.original_messages) == 2


# ---------------------------------------------------------------------------
# Describe
# ---------------------------------------------------------------------------


class TestDescribe:
    async def test_empty_store(self, store):
        result = await describe(store)
        assert result.total_messages == 0
        assert result.total_nodes == 0
        assert result.total_tokens == 0
        assert result.date_range == (None, None)
        assert result.compaction_stats == {}

    async def test_messages_only(self, populated_store):
        result = await describe(populated_store)
        assert result.total_messages == 10
        assert result.total_tokens == 100  # 10 messages * 10 tokens
        assert result.date_range[0] is not None

    async def test_with_nodes(self, populated_store):
        await populated_store.insert_node(
            ContextNode(
                id="n1",
                level=CompactionLevel.SUMMARY,
                seq_start=1,
                seq_end=5,
            )
        )
        await populated_store.insert_node(
            ContextNode(
                id="n2",
                level=CompactionLevel.BULLETS,
                seq_start=1,
                seq_end=5,
            )
        )
        result = await describe(populated_store)
        assert result.total_nodes == 2
        assert "summary" in result.compaction_stats
        assert "bullets" in result.compaction_stats

    async def test_date_range(self, populated_store):
        result = await describe(populated_store)
        start, end = result.date_range
        assert start is not None
        assert end is not None
        assert start <= end


# ---------------------------------------------------------------------------
# Recall scores + graded relevance floor (#247)
# ---------------------------------------------------------------------------
#
# These cover the memory recall path (RecallEngine over the in-memory dict
# stores), separate from the context grep/expand/describe path above. They
# verify two things the #247 change introduced:
#   1. Every recalled entry carries its activation score on recall_score.
#   2. A positive relevance_floor drops weak query matches (low token
#      overlap) while strong matches survive.


def _semantic(content: str, importance: int = 6) -> MemoryEntry:
    """Build a minimal semantic MemoryEntry for recall tests."""
    return MemoryEntry(type=MemoryType.SEMANTIC, content=content, importance=importance)


@pytest.fixture
def recall_engine() -> RecallEngine:
    """A RecallEngine over empty in-memory stores (graph disabled by callers)."""
    return RecallEngine(
        episodic=EpisodicStore(),
        semantic=SemanticStore(),
        procedural=ProceduralStore(),
    )


@pytest.fixture
async def populated_recall(recall_engine: RecallEngine) -> RecallEngine:
    """Engine seeded with strong, weak, and unrelated matches for the query
    'kubernetes orchestration scaling'.

    - strong: carries all three query tokens (token overlap 1.0).
    - weak: shares exactly one query token, 'kubernetes' (overlap ~0.33).
    - unrelated: shares no query token at all (never a candidate).

    None of the content words collide with the synonym groups in search.py,
    so token overlap stays the clean signal under test.
    """
    await recall_engine._semantic.add(
        _semantic("Kubernetes orchestration handles pod scaling across the fleet"),
    )
    await recall_engine._semantic.add(
        _semantic("A passing footnote that mentions kubernetes and nothing else"),
    )
    await recall_engine._semantic.add(
        _semantic("The user enjoys baking sourdough bread on weekends"),
    )
    return recall_engine


class TestRecallScoresAndFloor:
    """RecallEngine surfaces per-result scores and honours the graded floor."""

    async def test_results_carry_scores(self, populated_recall: RecallEngine):
        """Every recalled entry has a populated, finite recall_score."""
        results = await populated_recall.recall(
            "kubernetes orchestration scaling", limit=10, use_graph=False
        )
        assert results, "expected at least one match"
        for entry in results:
            assert entry.recall_score is not None
            assert isinstance(entry.recall_score, float)

    async def test_score_matches_ranking_order(self, populated_recall: RecallEngine):
        """Results are ordered by recall_score descending."""
        results = await populated_recall.recall(
            "kubernetes orchestration scaling", limit=10, use_graph=False
        )
        scores = [e.recall_score for e in results]
        assert scores == sorted(scores, reverse=True)

    async def test_default_floor_keeps_weak_match(self, populated_recall: RecallEngine):
        """At the default floor (0.0) the weak single-token match is kept."""
        results = await populated_recall.recall(
            "kubernetes orchestration scaling", limit=10, use_graph=False
        )
        contents = " ".join(e.content for e in results)
        assert "orchestration handles pod scaling" in contents  # strong
        assert "passing footnote" in contents  # weak — still present
        assert len(results) == 2  # unrelated never matched

    async def test_graded_floor_drops_weak_match(self, populated_recall: RecallEngine):
        """A floor of 0.5 drops the weak match but keeps the strong one."""
        results = await populated_recall.recall(
            "kubernetes orchestration scaling",
            limit=10,
            use_graph=False,
            relevance_floor=0.5,
        )
        contents = [e.content for e in results]
        assert len(results) == 1
        assert "orchestration handles pod scaling" in contents[0]  # strong survives
        assert all("passing footnote" not in c for c in contents)  # weak dropped

    async def test_floor_above_all_matches_returns_empty(
        self, populated_recall: RecallEngine
    ):
        """A floor above every match's relevance yields no results."""
        # The floor gate keeps an entry when relevance >= floor, so floor=1.0
        # is inclusive — the strong match has overlap exactly 1.0 and would
        # survive a 1.0 floor. To assert an *empty* result we need a floor
        # strictly above the maximum possible relevance (1.0). 1.01 is used
        # deliberately here, just past the documented 0.0-1.0 range, as the
        # "reject even a perfect match" probe; production callers stay in
        # range.
        results = await populated_recall.recall(
            "kubernetes orchestration scaling",
            limit=10,
            use_graph=False,
            relevance_floor=1.01,
        )
        assert results == []

    async def test_strong_match_outscores_weak(self, populated_recall: RecallEngine):
        """The strong match ranks above the weak match by recall_score."""
        results = await populated_recall.recall(
            "kubernetes orchestration scaling", limit=10, use_graph=False
        )
        assert len(results) == 2
        strong, weak = results[0], results[1]
        assert "orchestration handles pod scaling" in strong.content
        assert strong.recall_score > weak.recall_score


# ---------------------------------------------------------------------------
# Graph augmentation vs the relevance floor (#247)
# ---------------------------------------------------------------------------
#
# A graph-augmented candidate is surfaced by searching a *graph entity term*,
# not the original user query, so its token overlap with the original query
# is typically ~0. Floor-checking it against the original query would drop
# every graph-augmented result whenever relevance_floor > 0, silently
# neutering graph augmentation. recall() exempts graph-augmented candidates
# from the floor; these tests pin that behaviour.


async def _graph_recall_engine() -> RecallEngine:
    """Engine whose graph connects FastAPI -> Python.

    The semantic store holds two memories, both keyed to the query
    'Tell me about FastAPI' (query tokens: tell, about, fastapi):

    - python_mem: about Python, *zero* overlap with the query. It only
      surfaces because the graph links FastAPI -> Python — a pure
      graph-augmented candidate.
    - weak_mem: a direct text match sharing exactly one query token
      ('fastapi'), token overlap ~0.33 — a genuine weak match.

    None of the content words collide with the synonym groups in search.py,
    so token overlap stays the clean signal under test.
    """
    graph = KnowledgeGraph()
    graph.add_entity("FastAPI", "framework")
    graph.add_entity("Python", "language")
    graph.add_relationship("FastAPI", "Python", "built_with")

    semantic = SemanticStore()
    # Pure graph-augmented candidate — no overlap with 'Tell me about FastAPI'.
    await semantic.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="Python remains the language teams reach for",
            importance=7,
        )
    )
    # Weak direct match — shares only the token 'fastapi' with the query.
    await semantic.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="A throwaway note that name-drops fastapi once",
            importance=7,
        )
    )
    return RecallEngine(
        episodic=EpisodicStore(),
        semantic=semantic,
        procedural=ProceduralStore(),
        graph=graph,
    )


class TestGraphAugmentationExemptFromFloor:
    """Graph-augmented recall candidates survive a positive relevance floor."""

    async def test_graph_candidate_survives_positive_floor(self):
        """A graph-augmented entry with zero query overlap is not floored out."""
        engine = await _graph_recall_engine()
        # 0.5 floor: the graph-augmented Python memory has 0.0 overlap with
        # 'Tell me about FastAPI'. Pre-fix the floor dropped it; it must
        # survive because the graph entity-term search already validated it.
        results = await engine.recall(
            "Tell me about FastAPI", limit=10, relevance_floor=0.5
        )
        assert any(
            "Python remains the language" in r.content for r in results
        ), "graph-augmented candidate was wrongly dropped by the relevance floor"

    async def test_floor_still_drops_weak_direct_match_with_graph(self):
        """The exemption is scoped: a weak *direct* match is still floored out."""
        engine = await _graph_recall_engine()
        results = await engine.recall(
            "Tell me about FastAPI", limit=10, relevance_floor=0.5
        )
        # 'name-drops fastapi' shares ~1/3 of the query tokens — it is a
        # direct text-search candidate, so the floor still applies to it.
        assert all(
            "throwaway note" not in r.content for r in results
        ), "weak direct match should still be dropped by the floor"

    async def test_graph_candidate_present_at_default_floor(self):
        """Sanity: at floor 0.0 the graph-augmented entry is present too."""
        engine = await _graph_recall_engine()
        results = await engine.recall(
            "Tell me about FastAPI", limit=10, relevance_floor=0.0
        )
        assert any("Python remains the language" in r.content for r in results)
