# test_mcp.py — Tests for the soul_eval MCP tool (#160).
# Created: 2026-04-29 — Uses the FastMCP in-memory Client to drive
#   soul_eval against a freshly-birthed soul. Validates yaml_path vs
#   yaml_string mutex, error reporting, and that the tool runs against
#   the soul's live state (not a re-birthed copy).

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
    """Reset the soul registry between tests, isolated from real .soul/ dirs."""
    server_module._registry.clear()
    monkeypatch.delenv("SOUL_DIR", raising=False)
    monkeypatch.delenv("SOUL_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))


async def _birth(client: Client, name: str = "EvalTarget") -> None:
    """Helper — birth a soul through the MCP tool."""
    await client.call_tool("soul_birth", {"name": name})


@pytest.mark.asyncio
async def test_soul_eval_yaml_string_runs(tmp_path: Path) -> None:
    """``soul_eval`` accepts an inline YAML string and returns JSON.

    Uses a structural recall case so the assertion doesn't depend on the
    fallback response template (which the MCP server can override with
    its own sampling engine).
    """
    yaml_text = dedent(
        """
        name: inline-eval
        cases:
          - name: trivial_recall
            inputs:
              message: anything
              mode: recall
              recall_limit: 5
            scoring:
              kind: structural
              expected:
                recall_min_results: 0
        """
    ).strip()
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_eval",
            {"yaml_string": yaml_text},
        )
    payload = json.loads(result.content[0].text)
    assert payload.get("error") is None, payload
    assert payload["spec_name"] == "inline-eval"
    assert len(payload["cases"]) == 1
    assert payload["cases"][0]["passed"]


@pytest.mark.asyncio
async def test_soul_eval_yaml_path_runs(tmp_path: Path) -> None:
    """``soul_eval`` reads a YAML file from disk."""
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(
        dedent(
            """
            name: file-eval
            cases:
              - name: trivial_recall
                inputs:
                  message: anything
                  mode: recall
                  recall_limit: 5
                scoring:
                  kind: structural
                  expected:
                    recall_min_results: 0
            """
        ).strip()
    )
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_eval",
            {"yaml_path": str(spec_path)},
        )
    payload = json.loads(result.content[0].text)
    assert payload.get("error") is None
    assert payload["cases"][0]["passed"]


@pytest.mark.asyncio
async def test_soul_eval_requires_exactly_one_input(tmp_path: Path) -> None:
    """Both inputs missing → error; both inputs present → error."""
    async with Client(mcp) as client:
        await _birth(client)
        # Neither
        result = await client.call_tool("soul_eval", {})
        payload = json.loads(result.content[0].text)
        assert "error" in payload

        # Both
        result = await client.call_tool(
            "soul_eval",
            {"yaml_path": "x", "yaml_string": "name: y\ncases: []"},
        )
        payload = json.loads(result.content[0].text)
        assert "error" in payload


@pytest.mark.asyncio
async def test_soul_eval_uses_active_soul_state(tmp_path: Path) -> None:
    """The MCP tool reads the live soul state, not a re-birthed copy.

    We seed a memory via ``soul_remember``, then ask the eval to recall
    it. If the eval re-birthed a soul from the (empty) seed block, recall
    would find nothing.
    """
    yaml_text = dedent(
        """
        name: live-soul-recall
        cases:
          - name: rust_recall
            inputs:
              message: rust
              mode: recall
              recall_limit: 5
            scoring:
              kind: structural
              expected:
                recall_min_results: 1
                recall_expected_substring: rust
        """
    ).strip()
    async with Client(mcp) as client:
        await _birth(client, name="LiveSoul")
        # Seed a memory through the MCP tool — exercises the same path
        # an agent would.
        await client.call_tool(
            "soul_remember",
            {"content": "I love rust programming", "importance": 8},
        )
        result = await client.call_tool(
            "soul_eval",
            {"yaml_string": yaml_text},
        )
    payload = json.loads(result.content[0].text)
    assert payload.get("error") is None
    assert payload["cases"][0]["passed"], payload["cases"][0]["details"]


@pytest.mark.asyncio
async def test_soul_eval_invalid_yaml_returns_error(tmp_path: Path) -> None:
    """A YAML string that doesn't match the schema returns an error JSON."""
    bad_yaml = "name: bad\ncases: not-a-list"
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_eval",
            {"yaml_string": bad_yaml},
        )
    payload = json.loads(result.content[0].text)
    assert "error" in payload


@pytest.mark.asyncio
async def test_soul_eval_case_filter(tmp_path: Path) -> None:
    """``case_filter`` narrows the case list."""
    yaml_text = dedent(
        """
        name: filter-eval
        cases:
          - name: alpha_case
            inputs: {message: hi}
            scoring: {kind: keyword, expected: [hi], mode: any, threshold: 0.0}
          - name: beta_case
            inputs: {message: hi}
            scoring: {kind: keyword, expected: [hi], mode: any, threshold: 0.0}
        """
    ).strip()
    async with Client(mcp) as client:
        await _birth(client)
        result = await client.call_tool(
            "soul_eval",
            {"yaml_string": yaml_text, "case_filter": "alpha"},
        )
    payload = json.loads(result.content[0].text)
    assert len(payload["cases"]) == 1
    assert payload["cases"][0]["name"] == "alpha_case"
