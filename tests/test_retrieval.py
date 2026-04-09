# test_retrieval.py — Tests for runtime/context/retrieval.py grep, expand, describe.
# Created: v0.3.0 — Regex search, DAG expansion, metadata snapshots,
# recursive expansion through multiple compaction levels, and edge cases.

from __future__ import annotations

import pytest

from soul_protocol.runtime.context.retrieval import describe, expand, grep
from soul_protocol.runtime.context.store import SQLiteContextStore
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
