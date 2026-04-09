# test_context_store.py — Tests for runtime/context/store.py SQLiteContextStore.
# Created: v0.3.0 — SQLite CRUD, immutability invariants, DAG integrity,
# persistence across reconnects, grep search, and metadata queries.

from __future__ import annotations

import pytest

from soul_protocol.runtime.context.store import SQLiteContextStore
from soul_protocol.spec.context.models import (
    CompactionLevel,
    ContextMessage,
    ContextNode,
)


@pytest.fixture
async def store():
    """In-memory SQLite store, initialized and ready."""
    s = SQLiteContextStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
async def persisted_store(tmp_path):
    """File-backed SQLite store for persistence tests."""
    db_path = tmp_path / "test_context.db"
    s = SQLiteContextStore(str(db_path))
    await s.initialize()
    yield s, str(db_path)
    await s.close()


# ---------------------------------------------------------------------------
# Message CRUD
# ---------------------------------------------------------------------------


class TestMessageAppend:
    async def test_append_assigns_seq(self, store):
        msg = ContextMessage(role="user", content="hello")
        result = await store.append_message(msg)
        assert result.seq == 1

    async def test_sequential_seq_numbers(self, store):
        m1 = await store.append_message(ContextMessage(role="user", content="a"))
        m2 = await store.append_message(ContextMessage(role="assistant", content="b"))
        m3 = await store.append_message(ContextMessage(role="user", content="c"))
        assert m1.seq == 1
        assert m2.seq == 2
        assert m3.seq == 3

    async def test_preserves_content(self, store):
        msg = ContextMessage(role="user", content="important message")
        await store.append_message(msg)
        retrieved = await store.get_messages()
        assert len(retrieved) == 1
        assert retrieved[0].content == "important message"
        assert retrieved[0].role == "user"

    async def test_preserves_token_count(self, store):
        msg = ContextMessage(role="user", content="hello", token_count=42)
        await store.append_message(msg)
        retrieved = await store.get_messages()
        assert retrieved[0].token_count == 42

    async def test_preserves_id(self, store):
        msg = ContextMessage(id="custom-id", role="user", content="test")
        await store.append_message(msg)
        retrieved = await store.get_message_by_id("custom-id")
        assert retrieved is not None
        assert retrieved.content == "test"


class TestMessageRetrieval:
    async def test_get_all_messages(self, store):
        for i in range(5):
            await store.append_message(ContextMessage(role="user", content=f"msg{i}"))
        messages = await store.get_messages()
        assert len(messages) == 5

    async def test_get_messages_ordered_by_seq(self, store):
        await store.append_message(ContextMessage(role="user", content="first"))
        await store.append_message(ContextMessage(role="user", content="second"))
        await store.append_message(ContextMessage(role="user", content="third"))
        messages = await store.get_messages()
        assert messages[0].content == "first"
        assert messages[2].content == "third"

    async def test_get_messages_with_seq_range(self, store):
        for i in range(10):
            await store.append_message(ContextMessage(role="user", content=f"msg{i}"))
        messages = await store.get_messages(seq_start=3, seq_end=7)
        assert len(messages) == 5
        assert messages[0].seq == 3
        assert messages[-1].seq == 7

    async def test_get_messages_with_limit(self, store):
        for i in range(10):
            await store.append_message(ContextMessage(role="user", content=f"msg{i}"))
        messages = await store.get_messages(limit=3)
        assert len(messages) == 3

    async def test_get_nonexistent_message(self, store):
        result = await store.get_message_by_id("nonexistent")
        assert result is None

    async def test_count_messages(self, store):
        assert await store.count_messages() == 0
        await store.append_message(ContextMessage(role="user", content="a"))
        await store.append_message(ContextMessage(role="user", content="b"))
        assert await store.count_messages() == 2

    async def test_total_tokens(self, store):
        await store.append_message(ContextMessage(role="user", content="a", token_count=10))
        await store.append_message(ContextMessage(role="user", content="b", token_count=20))
        assert await store.total_message_tokens() == 30

    async def test_empty_total_tokens(self, store):
        assert await store.total_message_tokens() == 0


class TestDateRange:
    async def test_empty_store(self, store):
        start, end = await store.get_date_range()
        assert start is None
        assert end is None

    async def test_single_message(self, store):
        await store.append_message(ContextMessage(role="user", content="hi"))
        start, end = await store.get_date_range()
        assert start is not None
        assert end is not None

    async def test_multiple_messages(self, store):
        await store.append_message(ContextMessage(role="user", content="first"))
        await store.append_message(ContextMessage(role="user", content="last"))
        start, end = await store.get_date_range()
        assert start <= end


# ---------------------------------------------------------------------------
# Grep
# ---------------------------------------------------------------------------


class TestGrep:
    async def test_simple_pattern(self, store):
        await store.append_message(ContextMessage(role="user", content="the quick brown fox"))
        await store.append_message(ContextMessage(role="user", content="jumped over the lazy dog"))
        results = await store.grep_messages("fox")
        assert len(results) == 1
        assert "fox" in results[0].content_snippet

    async def test_regex_pattern(self, store):
        await store.append_message(ContextMessage(role="user", content="error code 404"))
        await store.append_message(ContextMessage(role="user", content="error code 500"))
        await store.append_message(ContextMessage(role="user", content="success"))
        results = await store.grep_messages(r"error code \d+")
        assert len(results) == 2

    async def test_case_insensitive(self, store):
        await store.append_message(ContextMessage(role="user", content="Hello World"))
        results = await store.grep_messages("hello")
        assert len(results) == 1

    async def test_limit(self, store):
        for i in range(10):
            await store.append_message(ContextMessage(role="user", content=f"match {i}"))
        results = await store.grep_messages("match", limit=3)
        assert len(results) == 3

    async def test_no_match(self, store):
        await store.append_message(ContextMessage(role="user", content="hello"))
        results = await store.grep_messages("xyz")
        assert len(results) == 0

    async def test_ordered_by_recency(self, store):
        await store.append_message(ContextMessage(role="user", content="match first"))
        await store.append_message(ContextMessage(role="user", content="match second"))
        results = await store.grep_messages("match")
        assert results[0].seq > results[1].seq  # Most recent first


# ---------------------------------------------------------------------------
# Node operations (DAG)
# ---------------------------------------------------------------------------


class TestNodeOperations:
    async def test_insert_and_get_node(self, store):
        node = ContextNode(
            id="node1",
            level=CompactionLevel.SUMMARY,
            content="A summary",
            token_count=10,
            children_ids=["msg1", "msg2"],
            seq_start=1,
            seq_end=2,
        )
        await store.insert_node(node)
        retrieved = await store.get_node("node1")
        assert retrieved is not None
        assert retrieved.content == "A summary"
        assert retrieved.level == CompactionLevel.SUMMARY
        assert retrieved.children_ids == ["msg1", "msg2"]

    async def test_get_nonexistent_node(self, store):
        result = await store.get_node("nonexistent")
        assert result is None

    async def test_get_nodes_by_level(self, store):
        for i in range(3):
            await store.insert_node(
                ContextNode(
                    id=f"sum{i}",
                    level=CompactionLevel.SUMMARY,
                    content=f"summary {i}",
                    seq_start=i * 10,
                    seq_end=(i + 1) * 10,
                )
            )
        await store.insert_node(
            ContextNode(
                id="bul1",
                level=CompactionLevel.BULLETS,
                content="bullets",
                seq_start=0,
                seq_end=30,
            )
        )
        summaries = await store.get_nodes_by_level(CompactionLevel.SUMMARY)
        assert len(summaries) == 3
        bullets = await store.get_nodes_by_level(CompactionLevel.BULLETS)
        assert len(bullets) == 1

    async def test_count_nodes(self, store):
        assert await store.count_nodes() == 0
        await store.insert_node(
            ContextNode(id="n1", level=CompactionLevel.SUMMARY, seq_start=1, seq_end=5)
        )
        assert await store.count_nodes() == 1

    async def test_compaction_stats(self, store):
        await store.insert_node(
            ContextNode(id="s1", level=CompactionLevel.SUMMARY, seq_start=1, seq_end=5)
        )
        await store.insert_node(
            ContextNode(id="s2", level=CompactionLevel.SUMMARY, seq_start=6, seq_end=10)
        )
        await store.insert_node(
            ContextNode(id="b1", level=CompactionLevel.BULLETS, seq_start=1, seq_end=10)
        )
        stats = await store.compaction_stats()
        assert stats["summary"] == 2
        assert stats["bullets"] == 1

    async def test_covered_seq_ranges(self, store):
        await store.insert_node(
            ContextNode(
                id="s1",
                level=CompactionLevel.SUMMARY,
                seq_start=1,
                seq_end=5,
            )
        )
        await store.insert_node(
            ContextNode(
                id="s2",
                level=CompactionLevel.SUMMARY,
                seq_start=10,
                seq_end=15,
            )
        )
        ranges = await store.get_covered_seq_ranges()
        assert len(ranges) == 2
        assert (1, 5) in ranges
        assert (10, 15) in ranges

    async def test_verbatim_nodes_not_in_covered_ranges(self, store):
        await store.insert_node(
            ContextNode(
                id="v1",
                level=CompactionLevel.VERBATIM,
                seq_start=1,
                seq_end=1,
            )
        )
        ranges = await store.get_covered_seq_ranges()
        assert len(ranges) == 0


# ---------------------------------------------------------------------------
# Describe
# ---------------------------------------------------------------------------


class TestDescribe:
    async def test_empty_store(self, store):
        desc = await store.describe()
        assert desc.total_messages == 0
        assert desc.total_nodes == 0
        assert desc.total_tokens == 0

    async def test_with_data(self, store):
        await store.append_message(ContextMessage(role="user", content="hi", token_count=5))
        await store.append_message(ContextMessage(role="assistant", content="hello", token_count=3))
        await store.insert_node(
            ContextNode(id="n1", level=CompactionLevel.SUMMARY, seq_start=1, seq_end=2)
        )
        desc = await store.describe()
        assert desc.total_messages == 2
        assert desc.total_nodes == 1
        assert desc.total_tokens == 8


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    async def test_data_survives_reconnect(self, persisted_store):
        store, db_path = persisted_store
        await store.append_message(
            ContextMessage(id="persist-me", role="user", content="remember me")
        )
        await store.close()

        # Reopen
        store2 = SQLiteContextStore(db_path)
        await store2.initialize()
        msg = await store2.get_message_by_id("persist-me")
        assert msg is not None
        assert msg.content == "remember me"
        await store2.close()

    async def test_seq_continues_after_reconnect(self, persisted_store):
        store, db_path = persisted_store
        await store.append_message(ContextMessage(role="user", content="a"))
        await store.append_message(ContextMessage(role="user", content="b"))
        await store.close()

        store2 = SQLiteContextStore(db_path)
        await store2.initialize()
        msg = await store2.append_message(ContextMessage(role="user", content="c"))
        assert msg.seq == 3
        await store2.close()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    async def test_uninitialized_store_raises(self):
        store = SQLiteContextStore(":memory:")
        with pytest.raises(RuntimeError, match="not initialized"):
            await store.append_message(ContextMessage(role="user", content="fail"))
