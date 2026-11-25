# test_mcp/test_instinct_tools.py — MCP seam tests for Soul Instinct tools.
# Created: feat/soul-instinct — soul_decide (read-only typed decisions, input
#   validation, attached deciders) and soul_instinct_review (host-LLM reviewer,
#   empty queue, reviewing uncertain memories) through the FastMCP client.

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip(
    "fastmcp", reason="fastmcp not installed — install with: pip install soul-protocol[mcp]"
)

from fastmcp import Client  # noqa: E402

import soul_protocol.mcp.server as server_module  # noqa: E402
from soul_protocol.mcp.server import mcp  # noqa: E402
from soul_protocol.runtime.types import Interaction  # noqa: E402
from tests.test_decide.conftest import (  # noqa: E402
    KeywordContradictionDecider,
    ScriptedEngine,
)


@pytest.fixture(autouse=True)
def _reset_registry(tmp_path, monkeypatch):
    """Reset MCP module globals and isolate auto-discovery from local souls."""
    server_module._registry.clear()
    server_module._contexts.clear()
    server_module._engine = None
    monkeypatch.delenv("SOUL_DIR", raising=False)
    monkeypatch.delenv("SOUL_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    yield
    server_module._registry.clear()
    server_module._contexts.clear()
    server_module._engine = None


async def test_soul_decide_sentiment():
    async with Client(mcp) as client:
        await client.call_tool("soul_birth", {"name": "DecideBot"})
        result = await client.call_tool(
            "soul_decide", {"kind": "sentiment", "text": "I GOT PROMOTED!!!"}
        )
    data = json.loads(result.data)
    assert data["status"] == "ok"
    assert data["soul"] == "DecideBot"
    assert data["kind"] == "sentiment"
    assert data["value"]["label"] == "excitement"
    assert data["source"] == "cognitive"


async def test_soul_decide_uses_attached_deciders_and_is_read_only():
    async with Client(mcp) as client:
        await client.call_tool("soul_birth", {"name": "Instinct"})
        soul = server_module._registry.get("Instinct")
        steak_id = await soul.remember("User loves steak")
        soul.use_deciders([KeywordContradictionDecider()])

        result = await client.call_tool(
            "soul_decide", {"kind": "contradiction", "text": "I'm vegetarian now"}
        )

    data = json.loads(result.data)
    assert data["source"] == "keyword"
    assert [f["old_memory_id"] for f in data["value"]["findings"]] == [steak_id]
    assert data["attempts"][0]["outcome"] == "accepted"
    facts = soul._memory.semantic_facts()
    assert any(f.id == steak_id for f in facts)  # still live


async def test_soul_decide_rejects_unknown_kind():
    async with Client(mcp) as client:
        await client.call_tool("soul_birth", {"name": "Picky"})
        result = await client.call_tool("soul_decide", {"kind": "telepathy", "text": "hi"})
    data = json.loads(result.data)
    assert data["status"] == "error"
    assert "sentiment" in data["error"]


async def test_soul_instinct_review_uses_host_llm_and_handles_empty_queue():
    async with Client(mcp) as client:
        await client.call_tool("soul_birth", {"name": "Reviewer"})
        result = await client.call_tool("soul_instinct_review", {})
    data = json.loads(result.data)
    assert data["status"] == "ok"
    # Inside MCP the host LLM (MCP sampling) is wired in as the reviewer.
    assert data["reviewer"] == "llm"
    assert data["pending_before"] == 0
    assert data["reviewed"] == 0


async def test_soul_instinct_review_resolves_uncertain_memory():
    reviewer = ScriptedEngine(
        lambda p: (
            '{"contradicted": [1], "confidence": 0.9}' if "Decide which OLD memories" in p else "{}"
        )
    )
    async with Client(mcp) as client:
        await client.call_tool("soul_birth", {"name": "Fixer"})
        soul = server_module._registry.get("Fixer")
        await soul.remember("User loves steak")
        soul.use_deciders([KeywordContradictionDecider(confidence=0.4)])
        await soul.observe(Interaction.from_pair("I'm vegetarian now", "ok"))
        assert len(soul.uncertain_memories()) == 1
        soul.set_engine(reviewer)

        result = await client.call_tool("soul_instinct_review", {})

    data = json.loads(result.data)
    assert data["pending_before"] == 1
    assert data["reviewed"] == 1
    assert data["superseded"] == 1
    assert data["reviewer"] == "llm"
    assert soul.uncertain_memories() == []
