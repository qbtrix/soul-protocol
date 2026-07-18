# test_mcp.py — Tests for the soul_optimize MCP tool (#142).
# Created: 2026-04-29 — Drives soul_optimize via the FastMCP in-memory
#   client. Validates the yaml_path / yaml_string mutex, the apply=False
#   default, and that the tool runs against the active soul's live state.

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

pytest.importorskip("fastmcp", reason="fastmcp required — pip install soul-protocol[mcp]")

from fastmcp import Client  # noqa: E402

import soul_protocol.mcp.server as server_module  # noqa: E402
from soul_protocol.mcp.server import mcp  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_registry(tmp_path, monkeypatch):
    server_module._registry.clear()
    monkeypatch.delenv("SOUL_DIR", raising=False)
    monkeypatch.delenv("SOUL_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))


async def _birth(client: Client, name: str = "OptimizeTarget") -> None:
    await client.call_tool("soul_birth", {"name": name})


@pytest.mark.asyncio
async def test_soul_optimize_yaml_string_runs(tmp_path: Path) -> None:
    """`soul_optimize` accepts an inline YAML string and returns JSON."""
    yaml_text = dedent(
        """
        name: inline-optimize
        cases:
          - name: trivial
            inputs:
              message: anything
            scoring:
              kind: keyword
              expected: ["fallback"]
              mode: any
        """
    ).strip()
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_optimize",
            {"yaml_string": yaml_text, "iterations": 1},
        )
    payload = json.loads(result.content[0].text)
    assert payload.get("error") is None, payload
    assert payload["spec_name"] == "inline-optimize"
    assert "baseline_score" in payload
    assert "final_score" in payload
    assert payload["applied"] is False  # default dry-run


@pytest.mark.asyncio
async def test_soul_optimize_yaml_path_runs(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(
        dedent(
            """
            name: file-optimize
            cases:
              - name: trivial
                inputs: {message: hi}
                scoring: {kind: keyword, expected: [fallback], mode: any}
            """
        ).strip()
    )
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_optimize",
            {"yaml_path": str(spec_path), "iterations": 1},
        )
    payload = json.loads(result.content[0].text)
    assert payload.get("error") is None
    assert payload["spec_name"] == "file-optimize"


@pytest.mark.asyncio
async def test_soul_optimize_requires_exactly_one_input(tmp_path: Path) -> None:
    async with Client(mcp) as client:
        await _birth(client)
        # Neither
        result = await client.call_tool("soul_optimize", {})
        payload = json.loads(result.content[0].text)
        assert "error" in payload
        # Both
        result = await client.call_tool(
            "soul_optimize",
            {"yaml_path": "x", "yaml_string": "name: y\ncases: []"},
        )
        payload = json.loads(result.content[0].text)
        assert "error" in payload


@pytest.mark.asyncio
async def test_soul_optimize_invalid_yaml_returns_error(tmp_path: Path) -> None:
    bad_yaml = "name: bad\ncases: not-a-list"
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_optimize",
            {"yaml_string": bad_yaml},
        )
    payload = json.loads(result.content[0].text)
    assert "error" in payload


@pytest.mark.asyncio
async def test_soul_optimize_apply_flag_propagates(tmp_path: Path) -> None:
    """``apply=True`` is reflected on the returned OptimizeResult."""
    yaml_text = dedent(
        """
        name: apply-flag
        cases:
          - name: trivial
            inputs: {message: hi}
            scoring: {kind: keyword, expected: [fallback], mode: any}
        """
    ).strip()
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_optimize",
            {"yaml_string": yaml_text, "iterations": 1, "apply": True},
        )
    payload = json.loads(result.content[0].text)
    assert payload.get("error") is None
    assert payload["applied"] is True
