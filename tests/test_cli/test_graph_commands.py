# test_cli/test_graph_commands.py — CLI coverage for ``soul graph`` subcommands.
# Created: 2026-04-29 (#108, #190) — Smokes the new ``soul graph nodes``,
# ``soul graph edges``, ``soul graph neighbors``, ``soul graph path``, and
# ``soul graph mermaid`` commands. Tests focus on exit codes + JSON output so
# they don't break on cosmetic table layout changes.

from __future__ import annotations

import asyncio
import json

import pytest
from click.testing import CliRunner

from soul_protocol import Soul
from soul_protocol.cli.main import cli


@pytest.fixture
def populated_soul(tmp_path):
    """Birth a soul with a small hand-built graph and save to disk."""
    soul_path = tmp_path / "graph-cli.soul"

    async def _build():
        soul = await Soul.birth(name="GraphCLI", archetype="The Companion")
        g = soul._memory._graph
        g.add_entity("Alice", "person")
        g.add_entity("Bob", "person")
        g.add_entity("Acme", "org")
        g.add_relationship("Alice", "Bob", "mentions", weight=0.8)
        g.add_relationship("Alice", "Acme", "owned_by")
        await soul.export(str(soul_path))

    asyncio.run(_build())
    return str(soul_path)


def test_graph_nodes_json(populated_soul):
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", "nodes", populated_soul, "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["count"] == 3
    ids = {n["id"] for n in data["nodes"]}
    assert ids == {"Alice", "Bob", "Acme"}


def test_graph_nodes_filter_by_type(populated_soul):
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", "nodes", populated_soul, "--type", "person", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert {n["id"] for n in data["nodes"]} == {"Alice", "Bob"}


def test_graph_edges_json(populated_soul):
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", "edges", populated_soul, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["count"] == 2


def test_graph_edges_filter_relation(populated_soul):
    runner = CliRunner()
    result = runner.invoke(
        cli, ["graph", "edges", populated_soul, "--relation", "mentions", "--json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["count"] == 1
    assert data["edges"][0]["target"] == "Bob"


def test_graph_neighbors_json(populated_soul):
    runner = CliRunner()
    result = runner.invoke(
        cli, ["graph", "neighbors", populated_soul, "Alice", "--depth", "1", "--json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    ids = {n["id"] for n in data["nodes"]}
    assert ids == {"Alice", "Bob", "Acme"}


def test_graph_path_json(populated_soul):
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", "path", populated_soul, "Alice", "Acme", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["found"] is True
    assert len(data["edges"]) == 1


def test_graph_path_no_route(populated_soul):
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", "path", populated_soul, "Alice", "Ghost", "--json"])
    # Exit 0 even when the path doesn't exist; the JSON ``found`` flag tells
    # the caller.
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["found"] is False
    assert data["edges"] == []


def test_graph_mermaid_emits_lr_block(populated_soul):
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", "mermaid", populated_soul])
    assert result.exit_code == 0
    assert "graph LR" in result.output
    # Each node renders with its label
    assert "Alice" in result.output
    assert "Bob" in result.output
    assert "Acme" in result.output


def test_graph_neighbors_with_type_filter(populated_soul):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "graph",
            "neighbors",
            populated_soul,
            "Alice",
            "--depth",
            "2",
            "--types",
            "org",
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    ids = {n["id"] for n in data["nodes"]}
    # Source always included; only org-typed neighbors otherwise
    assert "Alice" in ids
    assert "Acme" in ids
    assert "Bob" not in ids


def test_graph_nodes_empty(tmp_path):
    soul_path = tmp_path / "empty.soul"

    async def _build():
        soul = await Soul.birth(name="Empty", archetype="The Companion")
        await soul.export(str(soul_path))

    asyncio.run(_build())
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", "nodes", str(soul_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["count"] == 0
