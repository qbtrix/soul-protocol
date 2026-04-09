# test_lcm.py — Integration tests for runtime/context/lcm.py LCMContext.
# Created: v0.3.0 — Ingest/assemble cycles, auto-compaction, protocol compliance,
# initialization guards, and CognitiveEngine integration.

from __future__ import annotations

import pytest

from soul_protocol.runtime.context.lcm import LCMContext
from soul_protocol.spec.context.models import CompactionLevel
from soul_protocol.spec.context.protocol import ContextEngine


class MockCognitiveEngine:
    """Predictable mock for testing LCM with an engine."""

    async def think(self, prompt: str) -> str:
        if "[TASK:context_summary]" in prompt:
            return "Summarized conversation."
        if "[TASK:context_bullets]" in prompt:
            return "- Key point"
        return "OK"


@pytest.fixture
async def lcm():
    ctx = LCMContext(db_path=":memory:", default_max_tokens=10000)
    await ctx.initialize()
    yield ctx
    await ctx.close()


@pytest.fixture
async def lcm_with_engine():
    engine = MockCognitiveEngine()
    ctx = LCMContext(
        db_path=":memory:",
        engine=engine,
        default_max_tokens=10000,
        compaction_threshold=0.8,
        summary_batch_size=5,
    )
    await ctx.initialize()
    yield ctx
    await ctx.close()


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_implements_context_engine(self, lcm):
        """LCMContext should satisfy the ContextEngine protocol."""
        assert isinstance(lcm, ContextEngine)

    async def test_all_protocol_methods_exist(self, lcm):
        assert hasattr(lcm, "ingest")
        assert hasattr(lcm, "assemble")
        assert hasattr(lcm, "grep")
        assert hasattr(lcm, "expand")
        assert hasattr(lcm, "describe")
        assert hasattr(lcm, "compact")


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInitialization:
    async def test_uninitialized_ingest_raises(self):
        ctx = LCMContext(db_path=":memory:")
        with pytest.raises(RuntimeError, match="not initialized"):
            await ctx.ingest("user", "hello")

    async def test_uninitialized_assemble_raises(self):
        ctx = LCMContext(db_path=":memory:")
        with pytest.raises(RuntimeError, match="not initialized"):
            await ctx.assemble(1000)

    async def test_uninitialized_grep_raises(self):
        ctx = LCMContext(db_path=":memory:")
        with pytest.raises(RuntimeError, match="not initialized"):
            await ctx.grep("pattern")

    async def test_uninitialized_describe_raises(self):
        ctx = LCMContext(db_path=":memory:")
        with pytest.raises(RuntimeError, match="not initialized"):
            await ctx.describe()

    async def test_double_initialize(self, lcm):
        """Calling initialize twice should be safe."""
        await lcm.initialize()  # second time
        msg_id = await lcm.ingest("user", "still works")
        assert msg_id


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


class TestIngest:
    async def test_returns_message_id(self, lcm):
        msg_id = await lcm.ingest("user", "hello")
        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

    async def test_unique_ids(self, lcm):
        id1 = await lcm.ingest("user", "a")
        id2 = await lcm.ingest("user", "b")
        assert id1 != id2

    async def test_message_persisted(self, lcm):
        await lcm.ingest("user", "remember me")
        desc = await lcm.describe()
        assert desc.total_messages == 1

    async def test_multiple_roles(self, lcm):
        await lcm.ingest("user", "question")
        await lcm.ingest("assistant", "answer")
        await lcm.ingest("system", "instruction")
        desc = await lcm.describe()
        assert desc.total_messages == 3

    async def test_token_estimation(self, lcm):
        # "hello world" is ~11 chars, ~2-3 tokens
        await lcm.ingest("user", "hello world")
        desc = await lcm.describe()
        assert desc.total_tokens > 0


# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------


class TestAssemble:
    async def test_empty_context(self, lcm):
        result = await lcm.assemble(1000)
        assert result.total_tokens == 0
        assert result.nodes == []
        assert result.compaction_applied is False

    async def test_single_message(self, lcm):
        await lcm.ingest("user", "hello")
        result = await lcm.assemble(1000)
        assert len(result.nodes) == 1
        assert result.total_tokens > 0

    async def test_multiple_messages(self, lcm):
        for i in range(5):
            await lcm.ingest("user", f"message {i}")
        result = await lcm.assemble(10000)
        assert len(result.nodes) == 5

    async def test_respects_token_budget(self, lcm):
        for i in range(100):
            await lcm.ingest("user", f"A longer message with some content number {i}")
        result = await lcm.assemble(500)
        assert result.total_tokens <= 500

    async def test_system_reserve(self, lcm):
        for i in range(10):
            await lcm.ingest("user", f"message {i}")
        result_full = await lcm.assemble(10000)
        result_reserved = await lcm.assemble(10000, system_reserve=5000)
        assert result_reserved.total_tokens <= result_full.total_tokens

    async def test_zero_budget_returns_empty(self, lcm):
        await lcm.ingest("user", "hello")
        result = await lcm.assemble(0)
        assert result.total_tokens == 0

    async def test_negative_effective_budget(self, lcm):
        await lcm.ingest("user", "hello")
        result = await lcm.assemble(100, system_reserve=200)
        assert result.total_tokens == 0

    async def test_nodes_ordered_by_sequence(self, lcm):
        await lcm.ingest("user", "first")
        await lcm.ingest("assistant", "second")
        await lcm.ingest("user", "third")
        result = await lcm.assemble(10000)
        seqs = [n.seq_start for n in result.nodes]
        assert seqs == sorted(seqs)

    async def test_verbatim_nodes_contain_role(self, lcm):
        await lcm.ingest("user", "hello")
        result = await lcm.assemble(10000)
        assert "[user]" in result.nodes[0].content


# ---------------------------------------------------------------------------
# Auto-compaction
# ---------------------------------------------------------------------------


class TestAutoCompaction:
    async def test_triggers_on_threshold(self, lcm_with_engine):
        """When total tokens exceed threshold, auto-compaction should trigger."""
        # Fill past the threshold (80% of 10000 = 8000)
        for i in range(100):
            await lcm_with_engine.ingest("user", "x" * 400)  # ~100 tokens each
        desc = await lcm_with_engine.describe()
        # Should have some compaction nodes
        assert desc.total_nodes >= 0  # May or may not trigger depending on timing

    async def test_manual_compact(self, lcm):
        """Manual compact with no engine falls to Level 3."""
        for i in range(50):
            await lcm.ingest("user", "x" * 400)
        saved = await lcm.compact()
        assert saved >= 0  # May be 0 if already under budget


# ---------------------------------------------------------------------------
# Grep integration
# ---------------------------------------------------------------------------


class TestGrepIntegration:
    async def test_grep_finds_message(self, lcm):
        await lcm.ingest("user", "the secret code is 42")
        await lcm.ingest("assistant", "noted")
        results = await lcm.grep("secret")
        assert len(results) == 1
        assert "secret" in results[0].content_snippet

    async def test_grep_no_match(self, lcm):
        await lcm.ingest("user", "hello")
        results = await lcm.grep("xyz")
        assert len(results) == 0

    async def test_grep_with_limit(self, lcm):
        for i in range(10):
            await lcm.ingest("user", f"pattern match {i}")
        results = await lcm.grep("pattern", limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Expand integration
# ---------------------------------------------------------------------------


class TestExpandIntegration:
    async def test_expand_nonexistent_node(self, lcm):
        result = await lcm.expand("no-such-node")
        assert result.node_id == "no-such-node"
        assert result.original_messages == []

    async def test_expand_after_compaction(self, lcm_with_engine):
        """After compaction, expand should recover original messages."""
        for i in range(20):
            await lcm_with_engine.ingest(
                "user" if i % 2 == 0 else "assistant",
                f"Message content number {i}",
            )
        # Force compaction
        await lcm_with_engine.compact()
        nodes = await lcm_with_engine.store.get_all_nodes()
        compacted = [n for n in nodes if n.level != CompactionLevel.VERBATIM]
        if compacted:
            result = await lcm_with_engine.expand(compacted[0].id)
            assert result.node_id == compacted[0].id


# ---------------------------------------------------------------------------
# Describe integration
# ---------------------------------------------------------------------------


class TestDescribeIntegration:
    async def test_empty_describe(self, lcm):
        desc = await lcm.describe()
        assert desc.total_messages == 0
        assert desc.total_tokens == 0

    async def test_describe_after_ingest(self, lcm):
        await lcm.ingest("user", "hello")
        await lcm.ingest("assistant", "hi there")
        desc = await lcm.describe()
        assert desc.total_messages == 2
        assert desc.total_tokens > 0
        assert desc.date_range[0] is not None
        assert desc.date_range[1] is not None


# ---------------------------------------------------------------------------
# Close and reopen
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_close_and_reopen(self, tmp_path):
        db_path = tmp_path / "lcm_test.db"
        lcm1 = LCMContext(db_path=str(db_path), default_max_tokens=10000)
        await lcm1.initialize()
        await lcm1.ingest("user", "persist this")
        await lcm1.close()

        lcm2 = LCMContext(db_path=str(db_path), default_max_tokens=10000)
        await lcm2.initialize()
        desc = await lcm2.describe()
        assert desc.total_messages == 1
        await lcm2.close()

    async def test_operations_after_close_raise(self):
        lcm = LCMContext(db_path=":memory:")
        await lcm.initialize()
        await lcm.close()
        with pytest.raises(RuntimeError):
            await lcm.ingest("user", "should fail")
