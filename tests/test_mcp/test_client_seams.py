# tests/test_mcp/test_client_seams.py -- MCP registration and thin client seams.
# Created: 2026-07-24 (#289) -- Guards tools that previously existed only as
# Python functions, without an in-process FastMCP client smoke test.

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip(
    "fastmcp", reason="fastmcp required for MCP server tests -- pip install soul-protocol[mcp]"
)

from fastmcp import Client  # noqa: E402

import soul_protocol.mcp.server as server_module  # noqa: E402
from soul_protocol.mcp.server import mcp  # noqa: E402
from soul_protocol.runtime.soul import Soul  # noqa: E402
from soul_protocol.runtime.types import MemoryType  # noqa: E402

EXPECTED_MCP_TOOLS = {
    "soul_audit",
    "soul_birth",
    "soul_bond",
    "soul_cleanup",
    "soul_confirm",
    "soul_context_assemble",
    "soul_context_describe",
    "soul_context_expand",
    "soul_context_grep",
    "soul_context_ingest",
    "soul_dream",
    "soul_edit_core",
    "soul_eval",
    "soul_evaluate",
    "soul_evolve",
    "soul_export",
    "soul_feel",
    "soul_forget",
    "soul_graph_query",
    "soul_health",
    "soul_learn",
    "soul_list",
    "soul_observe",
    "soul_optimize",
    "soul_prompt",
    "soul_prune_chain",
    "soul_purge",
    "soul_recall",
    "soul_reflect",
    "soul_reinstate",
    "soul_reload",
    "soul_remember",
    "soul_save",
    "soul_skills",
    "soul_state",
    "soul_supersede",
    "soul_switch",
    "soul_update",
    "soul_verify",
}


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


@pytest.mark.asyncio
async def test_registered_tool_list_matches_public_mcp_surface():
    async with Client(mcp) as client:
        tools = await client.list_tools()

    names = {tool.name for tool in tools}
    assert EXPECTED_MCP_TOOLS <= names
    assert names - EXPECTED_MCP_TOOLS == set()


@pytest.mark.asyncio
async def test_soul_audit_crosses_fastmcp_client_seam():
    async with Client(mcp) as client:
        await client.call_tool("soul_birth", {"name": "AuditBot"})
        await client.call_tool("soul_bond", {"strengthen": 1.0})

        result = await client.call_tool("soul_audit", {"action_prefix": "bond."})

    data = json.loads(result.data)
    assert data["soul"] == "AuditBot"
    assert data["entries"]
    assert all(entry["action"].startswith("bond.") for entry in data["entries"])


@pytest.mark.asyncio
async def test_soul_dream_crosses_fastmcp_client_seam():
    async with Client(mcp) as client:
        await client.call_tool("soul_birth", {"name": "DreamBot"})
        soul = server_module._registry.get("DreamBot")
        await soul.remember(
            "DreamBot episodic memory for consolidation",
            type=MemoryType.EPISODIC,
            importance=7,
        )

        result = await client.call_tool("soul_dream", {})

    data = json.loads(result.data)
    assert "dreamed_at" in data
    assert data["episodes_reviewed"] >= 1
    assert "duration_ms" in data


@pytest.mark.asyncio
async def test_soul_reload_crosses_fastmcp_client_seam(tmp_path, monkeypatch):
    soul_v1 = await Soul.birth("ReloadBot")
    await soul_v1.remember(
        "ReloadBot initial memory",
        type=MemoryType.SEMANTIC,
        importance=5,
    )
    zip_path = tmp_path / "reloadbot.soul"
    await soul_v1.export(str(zip_path))
    monkeypatch.setenv("SOUL_PATH", str(zip_path))

    async with Client(mcp) as client:
        before = await client.call_tool("soul_recall", {"query": "external seam"})
        assert json.loads(before.data)["count"] == 0

        external = await Soul.awaken(str(zip_path))
        await external.remember(
            "External seam memory survives reload",
            type=MemoryType.SEMANTIC,
            importance=9,
        )
        await external.export(str(zip_path))

        reload_result = await client.call_tool("soul_reload", {})
        after = await client.call_tool("soul_recall", {"query": "external seam"})

    reload_data = json.loads(reload_result.data)
    recall_data = json.loads(after.data)
    assert reload_data["status"] == "reloaded"
    assert recall_data["count"] >= 1
    assert any("External seam memory" in m["content"] for m in recall_data["memories"])


@pytest.mark.asyncio
async def test_soul_context_tools_cross_fastmcp_client_seam():
    async with Client(mcp) as client:
        await client.call_tool("soul_birth", {"name": "ContextBot"})
        ingest = await client.call_tool(
            "soul_context_ingest",
            {"role": "user", "content": "Context seam token alpha"},
        )
        describe = await client.call_tool("soul_context_describe", {})
        grep = await client.call_tool("soul_context_grep", {"pattern": "alpha"})
        assemble = await client.call_tool("soul_context_assemble", {"max_tokens": 1000})
        expand = await client.call_tool(
            "soul_context_expand",
            {"node_id": "missing-node"},
        )

    ingest_data = json.loads(ingest.data)
    describe_data = json.loads(describe.data)
    grep_data = json.loads(grep.data)
    assemble_data = json.loads(assemble.data)
    expand_data = json.loads(expand.data)

    assert ingest_data["soul"] == "ContextBot"
    assert ingest_data["message_id"]
    assert describe_data["total_messages"] == 1
    assert grep_data["count"] == 1
    assert assemble_data["node_count"] == 1
    assert expand_data["node_id"] == "missing-node"
    assert expand_data["original_count"] == 0
