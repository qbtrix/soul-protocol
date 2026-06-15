# tests/cross_runtime/test_pocketpaw.py — PocketPaw round-trip tests.
# Created: 2026-06-10 (#228) — Round-trip a populated soul through
#   Soul Protocol's own export/import path (the same path PocketPaw uses).
#   PocketPaw reads .soul files via Soul.awaken(), so this test verifies
#   the exact code path that PocketPaw relies on.
#
# PocketPaw integration runs at the subprocess level: we export a .soul
# file, then re-import it via Soul.awaken() and check memories survive.

from __future__ import annotations

import asyncio

import pytest

from tests.cross_runtime.conftest import (
    EPISODIC_MEMORIES,
    SEMANTIC_MEMORIES,
    SOUL_NAME,
)


@pytest.mark.cross_runtime
class TestPocketPawRoundTrip:
    """Round-trip tests simulating PocketPaw's .soul file consumption.

    PocketPaw uses Soul.awaken() to load .soul files — the same code path
    we exercise here. If these tests pass, PocketPaw can read the file.
    """

    def test_semantic_memories_survive_round_trip(self, populated_soul_path):
        """Semantic (fact) memories survive export → import."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            soul = await Soul.awaken(str(populated_soul_path))

            # Check soul identity survived
            assert soul.name == SOUL_NAME

            # Recall each semantic memory individually to verify round-trip
            for mem in SEMANTIC_MEMORIES:
                results = await soul.recall(mem["content"])
                contents = [r.content for r in results]
                assert any(
                    mem["content"] in c for c in contents
                ), f"Missing semantic memory: {mem['content']}"

        asyncio.get_event_loop().run_until_complete(_check())

    def test_episodic_memories_survive_round_trip(self, populated_soul_path):
        """Episodic (event) memories survive export → import."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            soul = await Soul.awaken(str(populated_soul_path))

            # Recall episodic memories
            results = await soul.recall("debugging deployed production")
            contents = [r.content for r in results]

            # Every episodic memory should be present
            for mem in EPISODIC_MEMORIES:
                assert any(
                    mem["content"] in c for c in contents
                ), f"Missing episodic memory: {mem['content']}"

        asyncio.get_event_loop().run_until_complete(_check())

    def test_identity_survives_round_trip(self, populated_soul_path):
        """Soul identity (name, DID) survives export → import."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            soul = await Soul.awaken(str(populated_soul_path))

            assert soul.name == SOUL_NAME
            assert soul.did is not None
            assert soul.did.startswith("did:soul:")

        asyncio.get_event_loop().run_until_complete(_check())

    def test_memory_count_preserved(self, populated_soul_path):
        """Total memory count matches after round-trip."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            soul = await Soul.awaken(str(populated_soul_path))

            expected_count = len(SEMANTIC_MEMORIES) + len(EPISODIC_MEMORIES)
            assert soul.memory_count == expected_count, (
                f"Expected {expected_count} memories, got {soul.memory_count}"
            )

        asyncio.get_event_loop().run_until_complete(_check())

    def test_importance_scores_preserved(self, populated_soul_path):
        """Memory importance scores survive round-trip."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            soul = await Soul.awaken(str(populated_soul_path))

            # Query for a high-importance memory
            results = await soul.recall("production deployed")
            assert len(results) > 0

            # The deployment memory had importance=9
            deployment_mem = [r for r in results if "production" in r.content]
            assert len(deployment_mem) > 0
            assert deployment_mem[0].importance == 9

        asyncio.get_event_loop().run_until_complete(_check())

    def test_re_export_produces_valid_soul(self, populated_soul_path, tmp_path):
        """A re-exported soul can be loaded again (double round-trip)."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            # First import
            soul = await Soul.awaken(str(populated_soul_path))

            # Re-export to a new file
            re_exported = tmp_path / "re_exported.soul"
            await soul.export(str(re_exported), include_keys=True)

            # Second import
            soul2 = await Soul.awaken(str(re_exported))

            assert soul2.name == SOUL_NAME
            assert soul2.memory_count == soul.memory_count

        asyncio.get_event_loop().run_until_complete(_check())
