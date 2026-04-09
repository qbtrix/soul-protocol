# test_context_models.py — Tests for spec/context/models.py Pydantic models.
# Created: v0.3.0 — Validates CompactionLevel enum, ContextMessage, ContextNode,
# AssembleResult, GrepResult, ExpandResult, DescribeResult serialization and defaults.

from __future__ import annotations

from datetime import datetime

from soul_protocol.spec.context.models import (
    AssembleResult,
    CompactionLevel,
    ContextMessage,
    ContextNode,
    DescribeResult,
    ExpandResult,
    GrepResult,
)

# ---------------------------------------------------------------------------
# CompactionLevel
# ---------------------------------------------------------------------------


class TestCompactionLevel:
    def test_values(self):
        assert CompactionLevel.VERBATIM == "verbatim"
        assert CompactionLevel.SUMMARY == "summary"
        assert CompactionLevel.BULLETS == "bullets"
        assert CompactionLevel.TRUNCATED == "truncated"

    def test_is_str_enum(self):
        assert isinstance(CompactionLevel.VERBATIM, str)

    def test_all_levels_exist(self):
        assert len(CompactionLevel) == 4

    def test_string_comparison(self):
        assert CompactionLevel.VERBATIM == "verbatim"
        assert CompactionLevel.SUMMARY != "verbatim"


# ---------------------------------------------------------------------------
# ContextMessage
# ---------------------------------------------------------------------------


class TestContextMessage:
    def test_defaults(self):
        msg = ContextMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.token_count == 0
        assert msg.seq == 0
        assert msg.id  # auto-generated
        assert isinstance(msg.created_at, datetime)
        assert msg.metadata == {}

    def test_custom_fields(self):
        msg = ContextMessage(
            id="abc123",
            role="assistant",
            content="world",
            token_count=42,
            seq=7,
            metadata={"key": "value"},
        )
        assert msg.id == "abc123"
        assert msg.token_count == 42
        assert msg.seq == 7
        assert msg.metadata == {"key": "value"}

    def test_unique_ids(self):
        m1 = ContextMessage(role="user", content="a")
        m2 = ContextMessage(role="user", content="b")
        assert m1.id != m2.id

    def test_serialization_roundtrip(self):
        msg = ContextMessage(role="user", content="test")
        data = msg.model_dump()
        restored = ContextMessage(**data)
        assert restored.role == msg.role
        assert restored.content == msg.content
        assert restored.id == msg.id


# ---------------------------------------------------------------------------
# ContextNode
# ---------------------------------------------------------------------------


class TestContextNode:
    def test_defaults(self):
        node = ContextNode()
        assert node.level == CompactionLevel.VERBATIM
        assert node.content == ""
        assert node.token_count == 0
        assert node.children_ids == []
        assert node.seq_start == 0
        assert node.seq_end == 0

    def test_summary_node(self):
        node = ContextNode(
            level=CompactionLevel.SUMMARY,
            content="A summary of the conversation",
            token_count=15,
            children_ids=["msg1", "msg2", "msg3"],
            seq_start=1,
            seq_end=3,
        )
        assert node.level == CompactionLevel.SUMMARY
        assert len(node.children_ids) == 3
        assert node.seq_start == 1
        assert node.seq_end == 3

    def test_serialization_roundtrip(self):
        node = ContextNode(
            level=CompactionLevel.BULLETS,
            content="- point 1\n- point 2",
            children_ids=["a", "b"],
            seq_start=1,
            seq_end=5,
        )
        data = node.model_dump()
        restored = ContextNode(**data)
        assert restored.level == CompactionLevel.BULLETS
        assert restored.children_ids == ["a", "b"]


# ---------------------------------------------------------------------------
# AssembleResult
# ---------------------------------------------------------------------------


class TestAssembleResult:
    def test_defaults(self):
        result = AssembleResult()
        assert result.nodes == []
        assert result.total_tokens == 0
        assert result.compaction_applied is False

    def test_with_nodes(self):
        nodes = [ContextNode(content="a"), ContextNode(content="b")]
        result = AssembleResult(nodes=nodes, total_tokens=100, compaction_applied=True)
        assert len(result.nodes) == 2
        assert result.total_tokens == 100
        assert result.compaction_applied is True


# ---------------------------------------------------------------------------
# GrepResult
# ---------------------------------------------------------------------------


class TestGrepResult:
    def test_construction(self):
        result = GrepResult(
            message_id="abc",
            seq=5,
            role="user",
            content_snippet="...hello world...",
        )
        assert result.message_id == "abc"
        assert result.seq == 5
        assert result.role == "user"
        assert "hello world" in result.content_snippet


# ---------------------------------------------------------------------------
# ExpandResult
# ---------------------------------------------------------------------------


class TestExpandResult:
    def test_defaults(self):
        result = ExpandResult(node_id="node1")
        assert result.node_id == "node1"
        assert result.level == CompactionLevel.VERBATIM
        assert result.original_messages == []

    def test_with_messages(self):
        msgs = [
            ContextMessage(role="user", content="hi"),
            ContextMessage(role="assistant", content="hello"),
        ]
        result = ExpandResult(
            node_id="n1",
            level=CompactionLevel.SUMMARY,
            original_messages=msgs,
        )
        assert len(result.original_messages) == 2
        assert result.level == CompactionLevel.SUMMARY


# ---------------------------------------------------------------------------
# DescribeResult
# ---------------------------------------------------------------------------


class TestDescribeResult:
    def test_defaults(self):
        result = DescribeResult()
        assert result.total_messages == 0
        assert result.total_nodes == 0
        assert result.total_tokens == 0
        assert result.date_range == (None, None)
        assert result.compaction_stats == {}

    def test_with_data(self):
        now = datetime.now()
        result = DescribeResult(
            total_messages=100,
            total_nodes=5,
            total_tokens=50000,
            date_range=(now, now),
            compaction_stats={"summary": 3, "bullets": 2},
        )
        assert result.total_messages == 100
        assert result.compaction_stats["summary"] == 3
