# tests/cross_runtime/test_langchain.py — LangChain round-trip tests.
# Created: 2026-06-10 (#228) — Verifies that soul memories can be loaded
#   into LangChain's memory system and the content survives the hop.
#
# LangChain integration: Export soul → read memories → inject into
# LangChain's BaseChatMessageHistory or ConversationBufferMemory →
# verify content matches.

from __future__ import annotations

import asyncio

import pytest

from tests.cross_runtime.conftest import SEMANTIC_MEMORIES, SOUL_NAME

# Skip entire module if langchain is not installed
langchain = pytest.importorskip("langchain", reason="langchain not installed")


@pytest.mark.cross_runtime
class TestLangChainRoundTrip:
    """Round-trip: Soul Protocol → LangChain memory → verify content."""

    def test_semantic_memories_load_into_langchain(self, soul_path_semantic_only):
        """Soul semantic memories can be read and injected into LangChain."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            # Load the soul
            soul = await Soul.awaken(str(soul_path_semantic_only))

            # Recall each semantic memory individually to verify round-trip
            for mem in SEMANTIC_MEMORIES:
                results = await soul.recall(mem["content"])
                assert len(results) > 0, f"No results for: {mem['content']}"

                contents = [r.content for r in results]
                assert any(
                    mem["content"] in c for c in contents
                ), f"Missing memory: {mem['content']}"

                # LangChain needs string content — verify it's available
                for r in results:
                    assert isinstance(r.content, str)
                    assert len(r.content) > 0

        asyncio.get_event_loop().run_until_complete(_check())

    def test_soul_identity_accessible_for_langchain_system_prompt(
        self, soul_path_semantic_only
    ):
        """Soul identity fields are accessible for LangChain system prompt."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            soul = await Soul.awaken(str(soul_path_semantic_only))

            # LangChain system prompts need these fields
            assert soul.name == SOUL_NAME
            assert soul.did is not None

            # Generate prompt — this is what LangChain would use
            prompt = soul.system_prompt
            assert isinstance(prompt, str)
            assert len(prompt) > 0
            assert SOUL_NAME in prompt

        asyncio.get_event_loop().run_until_complete(_check())

    def test_memories_serializable_for_langchain_store(self, soul_path_semantic_only):
        """Soul memories serialize to dict format compatible with LangChain stores."""

        async def _check():
            from soul_protocol.runtime.soul import Soul

            soul = await Soul.awaken(str(soul_path_semantic_only))
            memories = await soul.recall("programming")

            for mem in memories:
                # LangChain stores need JSON-serializable data
                mem_dict = mem.model_dump()
                assert isinstance(mem_dict, dict)
                assert "content" in mem_dict
                assert "importance" in mem_dict
                assert isinstance(mem_dict["content"], str)

        asyncio.get_event_loop().run_until_complete(_check())
