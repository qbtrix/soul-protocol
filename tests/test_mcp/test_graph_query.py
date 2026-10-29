# test_mcp/test_graph_query.py — MCP soul_graph_query tool tests.
# Created: 2026-04-29 (#108, #190) — Smokes the discriminated graph query
# tool over its six kinds: nodes, edges, neighbors, path, subgraph, mermaid,
# stats. Uses FastMCP's in-memory Client.

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastmcp", reason="fastmcp required for MCP server tests")

from fastmcp import Client  # noqa: E402

import soul_protocol.mcp.server as server_module  # noqa: E402
from soul_protocol.mcp.server import mcp  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_registry(tmp_path, monkeypatch):
    """Reset soul registry and isolate from real .soul/ directories."""
    server_module._registry.clear()
    monkeypatch.delenv("SOUL_DIR", raising=False)
    monkeypatch.delenv("SOUL_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)


async def _birth_with_graph(client: Client) -> None:
    """Birth a soul and seed a tiny graph through MCP."""
    await client.call_tool(
        "soul_birth",
        {"name": "GraphMCP", "archetype": "The Companion"},
    )
    # Use the underlying registry to grab the soul and seed graph
    soul = server_module._registry.get("GraphMCP")
    g = soul._memory._graph
    g.add_entity("Alice", "person")
    g.add_entity("Bob", "person")
    g.add_entity("Acme", "org")
    g.add_relationship("Alice", "Bob", "mentions", weight=0.8)
    g.add_relationship("Alice", "Acme", "owned_by")


@pytest.mark.asyncio
async def test_graph_query_nodes():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool("soul_graph_query", {"kind": "nodes"})
        data = json.loads(result.data)
        assert data["count"] == 3
        ids = {n["id"] for n in data["nodes"]}
        assert ids == {"Alice", "Bob", "Acme"}


@pytest.mark.asyncio
async def test_graph_query_nodes_filter():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool("soul_graph_query", {"kind": "nodes", "type": "person"})
        data = json.loads(result.data)
        assert data["count"] == 2


@pytest.mark.asyncio
async def test_graph_query_edges():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool("soul_graph_query", {"kind": "edges"})
        data = json.loads(result.data)
        assert data["count"] == 2


@pytest.mark.asyncio
async def test_graph_query_neighbors():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool(
            "soul_graph_query",
            {"kind": "neighbors", "node_id": "Alice", "depth": 1},
        )
        data = json.loads(result.data)
        ids = {n["id"] for n in data["nodes"]}
        assert ids == {"Alice", "Bob", "Acme"}


@pytest.mark.asyncio
async def test_graph_query_neighbors_missing_id():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool("soul_graph_query", {"kind": "neighbors"})
        data = json.loads(result.data)
        assert "error" in data


@pytest.mark.asyncio
async def test_graph_query_path():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool(
            "soul_graph_query",
            {"kind": "path", "source_id": "Alice", "target_id": "Acme"},
        )
        data = json.loads(result.data)
        assert data["found"] is True
        assert len(data["edges"]) == 1


@pytest.mark.asyncio
async def test_graph_query_subgraph():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool(
            "soul_graph_query",
            {"kind": "subgraph", "node_ids": ["Alice", "Bob"]},
        )
        data = json.loads(result.data)
        assert {n["id"] for n in data["nodes"]} == {"Alice", "Bob"}
        # Only the edge between Alice and Bob survives
        assert len(data["edges"]) == 1


@pytest.mark.asyncio
async def test_graph_query_mermaid():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool("soul_graph_query", {"kind": "mermaid"})
        data = json.loads(result.data)
        assert "graph LR" in data["mermaid"]


@pytest.mark.asyncio
async def test_graph_query_stats():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool("soul_graph_query", {"kind": "stats"})
        data = json.loads(result.data)
        assert data["node_count"] == 3
        assert data["edge_count"] == 2
        assert data["types"]["person"] == 2


@pytest.mark.asyncio
async def test_graph_query_unknown_kind():
    async with Client(mcp) as client:
        await _birth_with_graph(client)
        result = await client.call_tool("soul_graph_query", {"kind": "bogus"})
        data = json.loads(result.data)
        assert "error" in data
