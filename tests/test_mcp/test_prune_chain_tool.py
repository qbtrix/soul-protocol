# tests/test_mcp/test_prune_chain_tool.py — soul_prune_chain MCP tool (#203).
# Created: 2026-04-29 — Touch-time pruning over MCP. Dry-run preview by default;
# apply=True mutates the chain. Errors out cleanly when no keep value is set
# and the soul has no biorhythm cap.

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip(
    "fastmcp", reason="fastmcp required for MCP server tests — pip install soul-protocol[mcp]"
)

from fastmcp import Client  # noqa: E402

import soul_protocol.mcp.server as server_module  # noqa: E402
from soul_protocol.mcp.server import mcp  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_registry(tmp_path, monkeypatch):
    """Mirror the global server-test isolation pattern."""
    server_module._registry.clear()
    monkeypatch.delenv("SOUL_DIR", raising=False)
    monkeypatch.delenv("SOUL_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    yield
    server_module._registry.clear()


async def _birth_with_chain(client: Client, n: int = 25) -> None:
    """Birth a soul and append several chain entries via observe."""
    await client.call_tool("soul_birth", {"name": "PruneBot"})
    for i in range(n):
        await client.call_tool(
            "soul_observe",
            {
                "user_input": f"q{i}",
                "agent_output": f"a{i}",
                "channel": "test",
            },
        )


async def test_soul_prune_chain_dry_run_preview():
    async with Client(mcp) as client:
        await _birth_with_chain(client)
        result = await client.call_tool(
            "soul_prune_chain",
            {"keep": 3, "apply": False},
        )
        data = json.loads(result.data)
        assert data["applied"] is False
        assert data["summary"]["count"] >= 1
        assert data["keep"] == 3


async def test_soul_prune_chain_apply_mutates_chain():
    async with Client(mcp) as client:
        await _birth_with_chain(client)
        # Snapshot length pre-prune
        verify_pre = await client.call_tool("soul_verify", {})
        pre_payload = json.loads(verify_pre.data)
        pre_len = pre_payload["length"]

        result = await client.call_tool(
            "soul_prune_chain",
            {"keep": 3, "apply": True},
        )
        data = json.loads(result.data)
        assert data["applied"] is True
        assert data["summary"]["count"] >= 1

        # Chain length should have shrunk
        verify_post = await client.call_tool("soul_verify", {})
        post_payload = json.loads(verify_post.data)
        assert post_payload["length"] < pre_len
        assert post_payload["valid"] is True


async def test_soul_prune_chain_below_threshold_no_op():
    async with Client(mcp) as client:
        await _birth_with_chain(client, n=2)
        result = await client.call_tool(
            "soul_prune_chain",
            {"keep": 1000, "apply": True},
        )
        data = json.loads(result.data)
        assert data["applied"] is False
        assert data["summary"]["count"] == 0


async def test_soul_prune_chain_errors_when_no_cap():
    """Without a keep value AND no biorhythm cap, the tool returns an error payload."""
    async with Client(mcp) as client:
        await client.call_tool("soul_birth", {"name": "PruneBot"})
        result = await client.call_tool(
            "soul_prune_chain",
            {"apply": False},
        )
        data = json.loads(result.data)
        assert data["applied"] is False
        assert "error" in data
