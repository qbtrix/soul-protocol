# tests.test_cli.test_setup — Tests for universal agent platform integration
# Updated: 2026-03-13 — Added test for _resolve_uvx absolute path resolution.

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

from soul_protocol.cli.setup import (
    Platform,
    _append_instructions,
    _mcp_server_entry,
    _rel_path,
    _resolve_uvx,
    _update_gitignore,
    _write_mcp_json,
    _write_mcp_toml,
    detect_platforms,
    get_platforms,
    setup_integrations,
)


def _isolated_setup(tmp_path, **kwargs):
    """Run setup_integrations with home dir isolated to tmp_path."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir(exist_ok=True)
    with patch("soul_protocol.cli.setup._home", return_value=fake_home):
        return setup_integrations(**kwargs)


# --- Platform detection ---


def test_get_platforms_returns_list(tmp_path):
    platforms = get_platforms(tmp_path)
    assert len(platforms) >= 9
    slugs = {p.slug for p in platforms}
    assert "claude-code" in slugs
    assert "cursor" in slugs
    assert "vscode" in slugs


def test_detect_platforms_empty_dir(tmp_path):
    detected = detect_platforms(tmp_path)
    # Only project-scoped platforms should NOT be detected in empty dir
    project_detected = [p for p in detected if p.scope == "project"]
    assert len(project_detected) == 0


def test_detect_platforms_with_cursor(tmp_path):
    (tmp_path / ".cursor").mkdir()
    detected = detect_platforms(tmp_path)
    slugs = {p.slug for p in detected}
    assert "cursor" in slugs


def test_detect_platforms_with_vscode(tmp_path):
    (tmp_path / ".vscode").mkdir()
    detected = detect_platforms(tmp_path)
    slugs = {p.slug for p in detected}
    assert "vscode" in slugs


def test_detect_platforms_with_claude_md(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").write_text("# Test")
    detected = detect_platforms(tmp_path)
    slugs = {p.slug for p in detected}
    assert "claude-code" in slugs


# --- MCP config writers ---


def test_write_mcp_json_creates_file(tmp_path):
    soul_path = tmp_path / ".soul"
    soul_path.mkdir()
    config_path = tmp_path / ".mcp.json"
    plat = Platform(name="Test", slug="test", mcp_config_paths=[config_path])

    result = _write_mcp_json(config_path, soul_path, plat)

    assert result is True
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "soul" in data["mcpServers"]
    assert data["mcpServers"]["soul"]["command"].endswith("uvx")


def test_write_mcp_json_merges_existing(tmp_path):
    soul_path = tmp_path / ".soul"
    soul_path.mkdir()
    config_path = tmp_path / ".mcp.json"
    config_path.write_text(json.dumps({"mcpServers": {"other-server": {"command": "node"}}}))
    plat = Platform(name="Test", slug="test", mcp_config_paths=[config_path])

    _write_mcp_json(config_path, soul_path, plat)

    data = json.loads(config_path.read_text())
    assert "other-server" in data["mcpServers"]
    assert "soul" in data["mcpServers"]


def test_write_mcp_json_vscode_uses_servers_key(tmp_path):
    soul_path = tmp_path / ".soul"
    soul_path.mkdir()
    config_path = tmp_path / ".vscode" / "mcp.json"
    plat = Platform(
        name="VS Code",
        slug="vscode",
        mcp_config_paths=[config_path],
        mcp_key="servers",
    )

    _write_mcp_json(config_path, soul_path, plat)

    data = json.loads(config_path.read_text())
    assert "servers" in data
    assert "mcpServers" not in data
    assert data["servers"]["soul"]["type"] == "stdio"


def test_write_mcp_toml_creates_file(tmp_path):
    soul_path = tmp_path / ".soul"
    config_path = tmp_path / ".codex" / "config.toml"

    result = _write_mcp_toml(config_path, soul_path)

    assert result is True
    assert config_path.exists()
    content = config_path.read_text()
    assert "[mcp_servers.soul]" in content
    assert "soul-mcp" in content


def test_write_mcp_toml_appends_to_existing(tmp_path):
    soul_path = tmp_path / ".soul"
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('[model]\nprovider = "openai"\n')

    _write_mcp_toml(config_path, soul_path)

    content = config_path.read_text()
    assert "[model]" in content  # existing preserved
    assert "[mcp_servers.soul]" in content  # new appended


def test_write_mcp_toml_idempotent(tmp_path):
    soul_path = tmp_path / ".soul"
    config_path = tmp_path / ".codex" / "config.toml"

    _write_mcp_toml(config_path, soul_path)
    result = _write_mcp_toml(config_path, soul_path)

    assert result is False  # not written again


# --- Instruction file writers ---


def test_append_instructions_creates_file(tmp_path):
    inst = tmp_path / "AGENTS.md"
    result = _append_instructions(inst, header="TestBot")

    assert result is True
    content = inst.read_text()
    assert "## Soul (Persistent Memory)" in content
    assert "soul_recall" in content
    assert "# TestBot" in content


def test_append_instructions_appends_to_existing(tmp_path):
    inst = tmp_path / "AGENTS.md"
    inst.write_text("# Existing content\n\nDo stuff.\n")

    _append_instructions(inst)

    content = inst.read_text()
    assert "# Existing content" in content
    assert "## Soul (Persistent Memory)" in content


def test_append_instructions_idempotent(tmp_path):
    inst = tmp_path / "AGENTS.md"
    _append_instructions(inst, header="TestBot")
    result = _append_instructions(inst)

    assert result is False


def test_append_instructions_nested_path(tmp_path):
    inst = tmp_path / ".cursor" / "rules" / "soul.mdc"
    result = _append_instructions(inst, header="TestBot")

    assert result is True
    assert inst.exists()


# --- Gitignore ---


def test_update_gitignore_creates_file(tmp_path):
    result = _update_gitignore(tmp_path)

    assert result is True
    content = (tmp_path / ".gitignore").read_text()
    assert ".soul/" in content


def test_update_gitignore_appends(tmp_path):
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    _update_gitignore(tmp_path)

    content = (tmp_path / ".gitignore").read_text()
    assert "node_modules/" in content
    assert ".soul/" in content


def test_update_gitignore_idempotent(tmp_path):
    (tmp_path / ".gitignore").write_text(".soul/\n")
    result = _update_gitignore(tmp_path)
    assert result is False


# --- Full integration ---


def test_setup_integrations_specific_platforms(tmp_path):
    soul_path = tmp_path / ".soul"
    soul_path.mkdir()

    messages = _isolated_setup(
        tmp_path,
        soul_path=soul_path,
        soul_name="TestBot",
        cwd=tmp_path,
        platforms=["claude-code", "cursor"],
    )

    # Should have created files
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".mcp.json").exists()
    assert (tmp_path / ".cursor" / "mcp.json").exists()
    assert (tmp_path / ".gitignore").exists()
    assert len(messages) >= 4  # AGENTS.md + 2 MCP + gitignore at minimum

    # Should NOT have created VS Code config
    assert not (tmp_path / ".vscode" / "mcp.json").exists()


def test_setup_integrations_auto_detect_empty(tmp_path):
    soul_path = tmp_path / ".soul"
    soul_path.mkdir()

    messages = _isolated_setup(
        tmp_path,
        soul_path=soul_path,
        soul_name="TestBot",
        cwd=tmp_path,
        platforms=None,  # auto-detect
    )

    # AGENTS.md should always be created
    assert (tmp_path / "AGENTS.md").exists()
    # No platforms detected in isolated dir, so no MCP configs
    assert not (tmp_path / ".mcp.json").exists()
    assert any("AGENTS.md" in m for m in messages)


def test_setup_continue_dropin_format(tmp_path):
    """Continue uses drop-in format: each file = one server entry."""
    soul_path = tmp_path / ".soul"
    soul_path.mkdir()
    fake_home = tmp_path / "fake_home"
    continue_dir = fake_home / ".continue" / "mcpServers"
    continue_dir.mkdir(parents=True)

    plat = Platform(
        name="Continue",
        slug="continue",
        mcp_config_paths=[continue_dir / "soul.json"],
    )

    result = _write_mcp_json(continue_dir / "soul.json", soul_path, plat)
    assert result is True

    data = json.loads((continue_dir / "soul.json").read_text())
    # Should be bare server entry, NOT wrapped in mcpServers
    assert "command" in data
    assert "mcpServers" not in data

    # Idempotent
    result2 = _write_mcp_json(continue_dir / "soul.json", soul_path, plat)
    assert result2 is False


# --- Helpers ---


def test_rel_path_project(tmp_path):
    result = _rel_path(tmp_path / ".mcp.json", tmp_path)
    assert result == ".mcp.json"


def test_rel_path_home():
    home = Path.home()
    result = _rel_path(home / ".codeium" / "windsurf" / "mcp_config.json", Path("/tmp"))
    assert result.startswith("~/")


def test_mcp_server_entry(tmp_path):
    entry = _mcp_server_entry(tmp_path / ".soul")
    assert entry["command"].endswith("uvx")
    assert "soul-mcp" in entry["args"]
    assert "SOUL_PATH" in entry["env"]


def test_resolve_uvx_returns_absolute_path():
    """uvx should resolve to an absolute path when available on PATH."""
    result = _resolve_uvx()
    # On a dev machine with uv installed, should be absolute
    # On CI without uv, falls back to bare "uvx"
    assert result.endswith("uvx")
    if shutil.which("uvx"):
        assert "/" in result or "\\" in result  # absolute path


def test_resolve_uvx_fallback():
    """When uvx is not on PATH, fall back to bare 'uvx'."""
    with patch("soul_protocol.cli.setup.shutil.which", return_value=None):
        result = _resolve_uvx()
    assert result == "uvx"
