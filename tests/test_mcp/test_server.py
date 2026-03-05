# tests.test_mcp.test_server — MCP server integration tests
# Tests all 10 tools, 3 resources, 2 prompts using FastMCP in-memory Client
# Updated: Enum validation, core memory guard, export validation,
#          birth replacement warning, resource guards, lifespan

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from fastmcp import Client

import soul_protocol.mcp.server as server_module
from soul_protocol.mcp.server import mcp


@pytest.fixture(autouse=True)
def _reset_soul():
    """Reset global soul state between tests."""
    server_module._soul = None
    server_module._soul_path = None
    yield
    server_module._soul = None
    server_module._soul_path = None


# --- Helpers ---


async def _birth(client: Client, name: str = "TestBot") -> dict:
    result = await client.call_tool(
        "soul_birth",
        {"name": name, "archetype": "Test Archetype", "values": ["curiosity", "honesty"]},
    )
    return json.loads(result.data)


# --- Tool Tests ---


async def test_soul_birth():
    async with Client(mcp) as client:
        data = await _birth(client)
        assert data["name"] == "TestBot"
        assert data["status"] == "born"
        assert "did:" in data["did"]


async def test_soul_birth_minimal():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "soul_birth",
            {"name": "Minimal"},
        )
        data = json.loads(result.data)
        assert data["name"] == "Minimal"


async def test_soul_observe():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_observe",
            {
                "user_input": "I love Python",
                "agent_output": "Python is great!",
                "channel": "test",
            },
        )
        data = json.loads(result.data)
        assert data["status"] == "observed"
        assert "mood" in data
        assert "energy" in data


async def test_soul_remember_and_recall():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_remember",
            {
                "content": "User prefers dark mode",
                "importance": 8,
                "memory_type": "semantic",
            },
        )
        mem_data = json.loads(result.data)
        assert mem_data["type"] == "semantic"
        assert mem_data["importance"] == 8

        result = await client.call_tool(
            "soul_recall",
            {"query": "dark mode", "limit": 5},
        )
        data = json.loads(result.data)
        assert data["count"] >= 1
        assert any("dark mode" in m["content"] for m in data["memories"])


async def test_soul_remember_with_emotion():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_remember",
            {
                "content": "User had a great day",
                "importance": 7,
                "emotion": "joy",
            },
        )
        data = json.loads(result.data)
        assert "memory_id" in data


async def test_soul_remember_rejects_core_type():
    async with Client(mcp) as client:
        await _birth(client)
        with pytest.raises(Exception, match="core"):
            await client.call_tool(
                "soul_remember",
                {
                    "content": "test",
                    "memory_type": "core",
                },
            )


async def test_soul_remember_rejects_invalid_type():
    async with Client(mcp) as client:
        await _birth(client)
        with pytest.raises(Exception, match="Invalid memory_type"):
            await client.call_tool(
                "soul_remember",
                {
                    "content": "test",
                    "memory_type": "invalid",
                },
            )


async def test_soul_remember_clamps_importance():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_remember",
            {
                "content": "test",
                "importance": 99,
            },
        )
        data = json.loads(result.data)
        assert data["importance"] == 10


async def test_soul_recall_empty():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_recall",
            {"query": "nonexistent topic"},
        )
        data = json.loads(result.data)
        assert data["count"] == 0


async def test_soul_reflect():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool("soul_reflect", {})
        data = json.loads(result.data)
        assert data["status"] == "skipped"
        assert "reason" in data


async def test_soul_state():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool("soul_state", {})
        data = json.loads(result.data)
        assert "mood" in data
        assert "energy" in data
        assert "focus" in data
        assert "social_battery" in data
        assert "lifecycle" in data


async def test_soul_feel():
    async with Client(mcp) as client:
        await _birth(client)
        # energy is a delta — starts at 100, -20 -> 80
        result = await client.call_tool(
            "soul_feel",
            {"mood": "curious", "energy": -20.0},
        )
        data = json.loads(result.data)
        assert data["mood"] == "curious"
        assert data["energy"] == 80.0


async def test_soul_feel_partial():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_feel",
            {"mood": "focused"},
        )
        data = json.loads(result.data)
        assert data["mood"] == "focused"


async def test_soul_feel_rejects_invalid_mood():
    async with Client(mcp) as client:
        await _birth(client)
        with pytest.raises(Exception, match="Invalid mood"):
            await client.call_tool(
                "soul_feel",
                {"mood": "invalid_mood"},
            )


async def test_soul_feel_clamps_energy():
    async with Client(mcp) as client:
        await _birth(client)
        # Extreme delta should be clamped to -100..100
        result = await client.call_tool(
            "soul_feel",
            {"energy": -1e10},
        )
        data = json.loads(result.data)
        # Energy starts at 100, delta clamped to -100 -> 0
        assert data["energy"] == 0.0


async def test_soul_prompt():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool("soul_prompt", {})
        prompt_text = result.data
        assert isinstance(prompt_text, str)
        assert len(prompt_text) > 0
        assert "TestBot" in prompt_text


async def test_soul_save():
    async with Client(mcp) as client:
        await _birth(client)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_soul")
            result = await client.call_tool(
                "soul_save",
                {"path": path},
            )
            data = json.loads(result.data)
            assert data["status"] == "saved"
            # save() creates <path>/<soul_id>/ directory structure
            save_dir = Path(path)
            assert save_dir.is_dir()
            soul_dirs = list(save_dir.iterdir())
            assert len(soul_dirs) >= 1
            # Should contain soul.json inside the soul_id subdir
            soul_files = list(save_dir.glob("*/soul.json"))
            assert len(soul_files) == 1


async def test_soul_export():
    async with Client(mcp) as client:
        await _birth(client)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.soul")
            result = await client.call_tool(
                "soul_export",
                {"path": path},
            )
            data = json.loads(result.data)
            assert data["status"] == "exported"
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0


# --- Error Tests ---


async def test_no_soul_raises_error():
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("soul_state", {})


async def test_observe_without_soul_raises_error():
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "soul_observe",
                {
                    "user_input": "hello",
                    "agent_output": "hi",
                },
            )


# --- Validation Tests ---


async def test_soul_birth_replacement_warning():
    async with Client(mcp) as client:
        await _birth(client, "First")
        result = await client.call_tool(
            "soul_birth",
            {"name": "Second"},
        )
        data = json.loads(result.data)
        assert data["name"] == "Second"
        assert "warning" in data


async def test_soul_export_rejects_non_soul_extension():
    async with Client(mcp) as client:
        await _birth(client)
        with pytest.raises(Exception, match=r"\.soul"):
            await client.call_tool(
                "soul_export",
                {"path": "/tmp/evil.txt"},
            )


async def test_soul_export_rejects_missing_parent():
    async with Client(mcp) as client:
        await _birth(client)
        with pytest.raises(Exception, match="Parent directory"):
            await client.call_tool(
                "soul_export",
                {"path": "/nonexistent/dir/test.soul"},
            )


# --- Resource Tests ---


async def test_identity_resource():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.read_resource("soul://identity")
        assert result, "Expected non-empty resource response"
        data = json.loads(result[0].text)
        assert data["name"] == "TestBot"
        assert "did" in data
        assert "curiosity" in data["core_values"]


async def test_core_memory_resource():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.read_resource("soul://memory/core")
        assert result, "Expected non-empty resource response"
        data = json.loads(result[0].text)
        assert "persona" in data
        assert "human" in data


async def test_state_resource():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.read_resource("soul://state")
        assert result, "Expected non-empty resource response"
        data = json.loads(result[0].text)
        assert "mood" in data
        assert "energy" in data
        assert "lifecycle" in data


# --- Prompt Tests ---


async def test_system_prompt():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.get_prompt("soul_system_prompt", {})
        content = result.messages[0].content
        text = content if isinstance(content, str) else content.text
        assert "TestBot" in text


async def test_introduction_prompt():
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.get_prompt("soul_introduction", {})
        content = result.messages[0].content
        text = content if isinstance(content, str) else content.text
        assert "TestBot" in text
        assert "curiosity" in text or "honesty" in text


async def test_prompts_without_soul():
    async with Client(mcp) as client:
        result = await client.get_prompt("soul_system_prompt", {})
        content = result.messages[0].content
        text = content if isinstance(content, str) else content.text
        assert "No soul loaded" in text


# --- Resource Error Tests ---


async def test_resource_without_soul_raises():
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.read_resource("soul://identity")


# --- Lifespan Tests ---


async def test_lifespan_loads_soul_from_path(tmp_path):
    """Test that SOUL_PATH env var loads a soul on startup."""
    from soul_protocol import Soul

    # Create a real .soul file
    soul = await Soul.birth("LifespanTest", values=["testing"])
    soul_file = tmp_path / "test.soul"
    await soul.export(str(soul_file))

    # Patch env and reset state
    old_env = os.environ.get("SOUL_PATH")
    os.environ["SOUL_PATH"] = str(soul_file)
    server_module._soul = None
    server_module._soul_path = None
    try:
        async with Client(mcp) as client:
            result = await client.call_tool("soul_state", {})
            data = json.loads(result.data)
            assert "mood" in data
            assert data["lifecycle"] == "active"
    finally:
        if old_env is None:
            os.environ.pop("SOUL_PATH", None)
        else:
            os.environ["SOUL_PATH"] = old_env
        server_module._soul = None
        server_module._soul_path = None


async def test_lifespan_handles_bad_path(tmp_path):
    """Bad SOUL_PATH degrades gracefully — server starts without soul."""
    old_env = os.environ.get("SOUL_PATH")
    os.environ["SOUL_PATH"] = str(tmp_path / "nonexistent.soul")
    server_module._soul = None
    server_module._soul_path = None
    try:
        async with Client(mcp) as client:
            # Server should start, but no soul loaded
            with pytest.raises(Exception):
                await client.call_tool("soul_state", {})
    finally:
        if old_env is None:
            os.environ.pop("SOUL_PATH", None)
        else:
            os.environ["SOUL_PATH"] = old_env
        server_module._soul = None
        server_module._soul_path = None
