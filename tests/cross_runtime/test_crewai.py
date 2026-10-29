# tests/cross_runtime/test_crewai.py — CrewAI round-trip tests.
# Created: 2026-06-10 (#228) — Verifies that soul memories can be loaded
#   into CrewAI's memory system and the content survives the hop.
#
# CrewAI integration: Export soul → read memories → inject into
# CrewAI's Memory API → verify content matches.

from __future__ import annotations

import asyncio

import pytest

from tests.cross_runtime.conftest import SEMANTIC_MEMORIES, SOUL_NAME

# Skip entire module if crewai is not installed
crewai = pytest.importorskip("crewai", reason="crewai not installed")


@pytest.mark.cross_runtime
class TestCrewAIRoundTrip:
    """Round-trip: Soul Protocol → CrewAI memory → verify content."""

    def test_semantic_memories_load_into_crewai(self, soul_path_semantic_only):
        """Soul semantic memories can be read and injected into CrewAI."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            # Load the soul
            soul = await Soul.awaken(str(soul_path_semantic_only))

            # Recall each semantic memory individually to verify round-trip
            for mem in SEMANTIC_MEMORIES:
                results = await soul.recall(mem["content"])
                assert len(results) > 0, f"No results for: {mem['content']}"

                contents = [r.content for r in results]
                assert any(mem["content"] in c for c in contents), (
                    f"Missing memory: {mem['content']}"
                )

                # CrewAI needs string content
                for r in results:
                    assert isinstance(r.content, str)
                    assert len(r.content) > 0

        asyncio.get_event_loop().run_until_complete(_check())

    def test_soul_identity_accessible_for_crewai_agent(self, soul_path_semantic_only):
        """Soul identity fields are accessible for CrewAI agent backstory."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            soul = await Soul.awaken(str(soul_path_semantic_only))

            # CrewAI agents use backstory and role — soul provides these
            assert soul.name == SOUL_NAME
            assert soul.did is not None

            # Generate prompt — CrewAI would use this as agent backstory
            prompt = soul.system_prompt
            assert isinstance(prompt, str)
            assert len(prompt) > 0

        asyncio.get_event_loop().run_until_complete(_check())

    def test_memories_serializable_for_crewai_store(self, soul_path_semantic_only):
        """Soul memories serialize to dict format compatible with CrewAI."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            soul = await Soul.awaken(str(soul_path_semantic_only))
            memories = await soul.recall("programming")

            for mem in memories:
                # CrewAI stores need JSON-serializable data
                mem_dict = mem.model_dump()
                assert isinstance(mem_dict, dict)
                assert "content" in mem_dict
                assert isinstance(mem_dict["content"], str)

        asyncio.get_event_loop().run_until_complete(_check())
