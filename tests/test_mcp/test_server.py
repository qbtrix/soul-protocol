# tests.test_mcp.test_server — MCP server integration tests
# Updated: feat/mcp-sampling-engine — soul_reflect now returns "reflected" (not "skipped")
#   because MCPSamplingEngine is lazily wired, which activates HeuristicEngine fallback.
#   Updated test_soul_reflect to accept both outcomes.
# Updated: 2026-03-18 — Auto-reload + background file watcher tests.
# Updated: 2026-03-13 — Multi-soul support: SoulRegistry, SOUL_DIR, soul_list, soul_switch.
# Tests 12 tools, 3 resources, 2 prompts using FastMCP in-memory Client.

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("fastmcp", reason="fastmcp required for MCP server tests — pip install soul-protocol[mcp]")

from fastmcp import Client  # noqa: E402

import soul_protocol.mcp.server as server_module  # noqa: E402
from soul_protocol.mcp.server import mcp  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_registry(tmp_path, monkeypatch):
    """Reset soul registry and isolate from real .soul/ directories."""
    server_module._registry.clear()
    # Prevent auto-detect from finding real .soul/ in the repo or ~/.soul/
    monkeypatch.delenv("SOUL_DIR", raising=False)
    monkeypatch.delenv("SOUL_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    _fake_home = tmp_path / "fake_home"
    _fake_home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: _fake_home))
    yield
    server_module._registry.clear()


# --- Helpers ---


async def _birth(client: Client, name: str = "TestBot") -> dict:
    result = await client.call_tool(
        "soul_birth",
        {"name": name, "archetype": "Test Archetype", "values": ["curiosity", "honesty"]},
    )
    return json.loads(result.data)


def _env_context(key: str, value: str | None):
    """Helper to set/unset env vars with cleanup."""
    class _Ctx:
        def __init__(self):
            self.old = os.environ.get(key)
        def __enter__(self):
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)
            return self
        def __exit__(self, *_):
            if self.old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = self.old
            server_module._registry.clear()
    return _Ctx()


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
        # With MCPSamplingEngine wired (falls back to HeuristicEngine), reflect() can
        # return either "reflected" (heuristic ran) or "skipped" (no episodes yet).
        # Both are valid outcomes — we just check the response is well-formed.
        assert data["status"] in ("reflected", "skipped")
        assert "soul" in data


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
        result = await client.call_tool(
            "soul_feel",
            {"energy": -1e10},
        )
        data = json.loads(result.data)
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
            save_dir = Path(path)
            assert save_dir.is_dir()
            assert (save_dir / "soul.json").exists()


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


# --- Multi-Soul Tests ---


async def test_soul_list_empty():
    async with Client(mcp) as client:
        result = await client.call_tool("soul_list", {})
        data = json.loads(result.data)
        assert data["count"] == 0
        assert data["souls"] == []


async def test_soul_list_after_births():
    async with Client(mcp) as client:
        await _birth(client, "Alpha")
        await _birth(client, "Beta")
        result = await client.call_tool("soul_list", {})
        data = json.loads(result.data)
        assert data["count"] == 2
        names = [s["name"] for s in data["souls"]]
        assert "Alpha" in names
        assert "Beta" in names
        # Last born should be active
        active = [s for s in data["souls"] if s["active"]]
        assert len(active) == 1
        assert active[0]["name"] == "Beta"


async def test_soul_switch():
    async with Client(mcp) as client:
        await _birth(client, "Alpha")
        await _birth(client, "Beta")
        # Beta is active after birth
        result = await client.call_tool("soul_switch", {"name": "Alpha"})
        data = json.loads(result.data)
        assert data["status"] == "switched"
        assert data["name"] == "Alpha"

        # Verify state comes from Alpha
        result = await client.call_tool("soul_state", {})
        state = json.loads(result.data)
        assert state["soul"] == "Alpha"


async def test_soul_switch_invalid_name():
    async with Client(mcp) as client:
        await _birth(client, "Alpha")
        with pytest.raises(Exception, match="No soul named"):
            await client.call_tool("soul_switch", {"name": "Nonexistent"})


async def test_soul_tool_with_name_param():
    """Target a specific soul by name without switching active."""
    async with Client(mcp) as client:
        await _birth(client, "Alpha")
        await _birth(client, "Beta")
        # Beta is active, but remember to Alpha
        await client.call_tool(
            "soul_remember",
            {"content": "Alpha-specific memory", "soul": "Alpha"},
        )
        # Recall from Alpha
        result = await client.call_tool(
            "soul_recall",
            {"query": "Alpha-specific", "soul": "Alpha"},
        )
        data = json.loads(result.data)
        assert data["soul"] == "Alpha"
        assert data["count"] >= 1

        # Beta should NOT have this memory
        result = await client.call_tool(
            "soul_recall",
            {"query": "Alpha-specific", "soul": "Beta"},
        )
        data = json.loads(result.data)
        assert data["count"] == 0


async def test_soul_birth_adds_to_registry():
    """Birth adds to registry, doesn't replace other souls."""
    async with Client(mcp) as client:
        await _birth(client, "First")
        await _birth(client, "Second")
        result = await client.call_tool("soul_list", {})
        data = json.loads(result.data)
        assert data["count"] == 2


async def test_multi_soul_autosave(tmp_path):
    """Only modified souls are auto-saved on shutdown."""
    from soul_protocol import Soul

    # Create two directory souls
    soul_a = await Soul.birth("Alpha", values=["testing"])
    dir_a = tmp_path / "alpha"
    await soul_a.save_local(str(dir_a))

    soul_b = await Soul.birth("Beta", values=["testing"])
    dir_b = tmp_path / "beta"
    await soul_b.save_local(str(dir_b))

    with _env_context("SOUL_DIR", str(tmp_path)), \
         _env_context("SOUL_PATH", None):
        async with Client(mcp) as client:
            # Only modify Alpha
            await client.call_tool(
                "soul_remember",
                {"content": "Modified alpha memory", "soul": "Alpha"},
            )
        # Client exited — auto-save ran

        # Verify Alpha's memory persisted
        reloaded = await Soul.awaken(str(dir_a))
        memories = await reloaded.recall("Modified alpha", limit=5)
        assert any("Modified alpha memory" in m.content for m in memories)


async def test_soul_dir_loads_mixed_formats(tmp_path):
    """SOUL_DIR loads both directory souls and .soul ZIP files."""
    from soul_protocol import Soul

    # Create a directory soul
    soul_dir = await Soul.birth("DirSoul", values=["testing"])
    dir_path = tmp_path / "dirsoul"
    await soul_dir.save_local(str(dir_path))

    # Create a ZIP soul
    soul_zip = await Soul.birth("ZipSoul", values=["testing"])
    zip_path = tmp_path / "zipsoul.soul"
    await soul_zip.export(str(zip_path))

    with _env_context("SOUL_DIR", str(tmp_path)), \
         _env_context("SOUL_PATH", None):
        async with Client(mcp) as client:
            result = await client.call_tool("soul_list", {})
            data = json.loads(result.data)
            assert data["count"] == 2
            names = {s["name"] for s in data["souls"]}
            assert "DirSoul" in names
            assert "ZipSoul" in names
            formats = {s["name"]: s["format"] for s in data["souls"]}
            assert formats["DirSoul"] == "directory"
            assert formats["ZipSoul"] == "zip"


async def test_newborn_soul_no_path_autosave():
    """Newborn soul (no save path) should not crash auto-save on shutdown."""
    async with Client(mcp) as client:
        await _birth(client, "Ephemeral")
        # Modify the soul so it's marked as modified
        await client.call_tool(
            "soul_remember",
            {"content": "ephemeral memory", "importance": 5},
        )
    # If we get here without error, auto-save handled empty path gracefully


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
        result = await client.get_prompt("soul_system_prompt_template", {})
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
        result = await client.get_prompt("soul_system_prompt_template", {})
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
    """SOUL_PATH env var loads a soul on startup (backward compat)."""
    from soul_protocol import Soul

    soul = await Soul.birth("LifespanTest", values=["testing"])
    soul_file = tmp_path / "test.soul"
    await soul.export(str(soul_file))

    with _env_context("SOUL_PATH", str(soul_file)), \
         _env_context("SOUL_DIR", None):
        async with Client(mcp) as client:
            result = await client.call_tool("soul_state", {})
            data = json.loads(result.data)
            assert "mood" in data
            assert data["lifecycle"] == "active"


async def test_lifespan_handles_bad_path(tmp_path):
    """Bad SOUL_PATH degrades gracefully — server starts without soul."""
    with _env_context("SOUL_PATH", str(tmp_path / "nonexistent.soul")), \
         _env_context("SOUL_DIR", None):
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("soul_state", {})


async def test_lifespan_loads_from_directory(tmp_path):
    """SOUL_PATH pointing to a directory loads correctly."""
    from soul_protocol import Soul

    soul = await Soul.birth("DirLoad", values=["testing"])
    await soul.remember("pre-existing memory", importance=7)
    soul_dir = tmp_path / "dir_soul"
    await soul.save_local(str(soul_dir))

    with _env_context("SOUL_PATH", str(soul_dir)), \
         _env_context("SOUL_DIR", None):
        async with Client(mcp) as client:
            result = await client.call_tool("soul_state", {})
            data = json.loads(result.data)
            assert data["lifecycle"] == "active"

            result = await client.call_tool(
                "soul_recall", {"query": "pre-existing memory", "limit": 5}
            )
            data = json.loads(result.data)
            assert data["count"] >= 1


# --- Auto-save Tests ---


async def test_autosave_to_soul_file(tmp_path):
    """Memories persist after MCP server shutdown (ZIP format)."""
    from soul_protocol import Soul

    soul = await Soul.birth("AutoSaveZip", values=["testing"])
    soul_file = tmp_path / "autosave.soul"
    await soul.export(str(soul_file))

    with _env_context("SOUL_PATH", str(soul_file)), \
         _env_context("SOUL_DIR", None):
        async with Client(mcp) as client:
            await client.call_tool(
                "soul_remember",
                {"content": "Auto-save test memory", "importance": 9},
            )

        reloaded = await Soul.awaken(str(soul_file))
        memories = await reloaded.recall("Auto-save test", limit=5)
        assert any("Auto-save test memory" in m.content for m in memories)


async def test_autosave_to_directory(tmp_path):
    """Memories persist after MCP server shutdown (directory format)."""
    from soul_protocol import Soul

    soul = await Soul.birth("AutoSaveDir", values=["testing"])
    soul_dir = tmp_path / "guardian"
    await soul.save_local(str(soul_dir))

    with _env_context("SOUL_PATH", str(soul_dir)), \
         _env_context("SOUL_DIR", None):
        async with Client(mcp) as client:
            await client.call_tool(
                "soul_remember",
                {"content": "Directory auto-save test", "importance": 8},
            )

        reloaded = await Soul.awaken(str(soul_dir))
        memories = await reloaded.recall("Directory auto-save", limit=5)
        assert any("Directory auto-save test" in m.content for m in memories)


async def test_soul_dir_autosave_zip(tmp_path):
    """SOUL_DIR auto-saves ZIP souls in ZIP format (not directory)."""
    from soul_protocol import Soul

    soul = await Soul.birth("ZipAutoSave", values=["testing"])
    zip_path = tmp_path / "zipsoul.soul"
    await soul.export(str(zip_path))

    with _env_context("SOUL_DIR", str(tmp_path)), \
         _env_context("SOUL_PATH", None):
        async with Client(mcp) as client:
            await client.call_tool(
                "soul_remember",
                {"content": "ZIP dir auto-save", "soul": "ZipAutoSave"},
            )

        # Should still be a ZIP file, not converted to directory
        assert zip_path.is_file()
        assert zip_path.suffix == ".soul"
        reloaded = await Soul.awaken(str(zip_path))
        memories = await reloaded.recall("ZIP dir auto-save", limit=5)
        assert any("ZIP dir auto-save" in m.content for m in memories)


# --- Auto-reload on external file change ---


async def test_auto_reload_on_external_change(tmp_path):
    """soul_recall auto-reloads when the .soul file was modified externally."""
    from soul_protocol import Soul

    # Create a soul and export to disk
    soul = await Soul.birth("AutoReloadTest", values=["testing"])
    zip_path = tmp_path / "autoreload.soul"
    await soul.export(str(zip_path))

    with _env_context("SOUL_PATH", str(zip_path)), \
         _env_context("SOUL_DIR", None):
        async with Client(mcp) as client:
            # Recall should return nothing initially
            result = await client.call_tool(
                "soul_recall",
                {"query": "external memory", "limit": 5},
            )
            data = json.loads(result.data)
            assert data["count"] == 0

            # Simulate an external process modifying the .soul file
            # (like Claude Desktop saving new memories)
            external_soul = await Soul.awaken(str(zip_path))
            await external_soul.remember(
                "external memory added by another process",
                importance=9,
            )
            await external_soul.export(str(zip_path))

            # Recall should now find the externally-added memory
            # WITHOUT needing an explicit soul_reload call
            result = await client.call_tool(
                "soul_recall",
                {"query": "external memory", "limit": 5},
            )
            data = json.loads(result.data)
            assert data["count"] >= 1, (
                "Auto-reload failed: soul_recall didn't pick up external changes. "
                f"Got {data['count']} results, expected >= 1."
            )
            assert any("external memory" in m["content"] for m in data["memories"])


async def test_background_watcher_reloads_on_change(tmp_path):
    """Background file watcher detects changes and reloads without any tool call."""
    from soul_protocol import Soul

    soul = await Soul.birth("WatcherTest", values=["testing"])
    zip_path = tmp_path / "watcher.soul"
    await soul.export(str(zip_path))

    with _env_context("SOUL_POLL_INTERVAL", "0.1"), \
         _env_context("SOUL_PATH", str(zip_path)), \
         _env_context("SOUL_DIR", None):
        async with Client(mcp) as client:
            # Verify initial soul has no extra memories
            initial_soul = server_module._registry.get("WatcherTest")
            initial_count = initial_soul.memory_count

            # Externally modify the .soul file
            external_soul = await Soul.awaken(str(zip_path))
            await external_soul.remember(
                "watcher detected this memory",
                importance=8,
            )
            await external_soul.export(str(zip_path))

            # Wait for the background watcher to pick it up
            # (poll interval is 0.1s, give it a few cycles)
            await asyncio.sleep(0.5)

            # The registry should have the updated soul
            # WITHOUT any tool call triggering the reload
            reloaded_soul = server_module._registry.get("WatcherTest")
            assert reloaded_soul.memory_count > initial_count, (
                "Background watcher failed: memory count didn't increase. "
                f"Before: {initial_count}, After: {reloaded_soul.memory_count}"
            )


# --- Auto-detect .soul/ directory tests ---


class TestAutoDetectSoulDir:
    """Test that the lifespan auto-detects .soul/ in CWD and ~/.soul/ fallback."""

    @pytest.mark.asyncio
    async def test_autodetect_cwd_soul_dir(self, tmp_path, monkeypatch):
        """With no env vars, .soul/ in CWD should be auto-detected."""
        soul_dir = tmp_path / ".soul"
        soul_dir.mkdir()

        # Create a soul subdirectory (scanner expects .soul/SoulName/soul.json)
        from soul_protocol.runtime.soul import Soul

        soul_subdir = soul_dir / "AutoCWD"
        soul_subdir.mkdir()
        soul = await Soul.birth("AutoCWD", archetype="Test", values=["curiosity"])
        await soul.save_local(str(soul_subdir))

        # Clear env vars and set CWD
        monkeypatch.delenv("SOUL_DIR", raising=False)
        monkeypatch.delenv("SOUL_PATH", raising=False)
        monkeypatch.chdir(tmp_path)

        async with Client(mcp) as client:
            result = await client.call_tool("soul_list", {})
            data = json.loads(result.data)
            names = [s["name"] for s in data["souls"]]
            assert "AutoCWD" in names, f"Expected AutoCWD in {names}"

    @pytest.mark.asyncio
    async def test_autodetect_home_soul_dir(self, tmp_path, monkeypatch):
        """With no CWD .soul/, falls back to ~/.soul/."""
        # The autouse fixture already points Path.home() to tmp_path/fake_home
        # and CWD to tmp_path (which has no .soul/ dir)
        fake_home = tmp_path / "fake_home"
        home_soul = fake_home / ".soul"
        home_soul.mkdir(parents=True)

        # Create a soul subdirectory in the fake home dir
        from soul_protocol.runtime.soul import Soul

        soul_subdir = home_soul / "AutoHome"
        soul_subdir.mkdir()
        soul = await Soul.birth("AutoHome", archetype="Test", values=["honesty"])
        await soul.save_local(str(soul_subdir))

        async with Client(mcp) as client:
            result = await client.call_tool("soul_list", {})
            data = json.loads(result.data)
            names = [s["name"] for s in data["souls"]]
            assert "AutoHome" in names, f"Expected AutoHome in {names}"
