# tests/test_gateway/test_app.py — Starlette REST API over a Soul.
# Created: 2026-05 — Verifies the gateway exposes the Soul runtime over
#   JSON-over-HTTP (health, state, remember, recall, observe, turn) using the
#   same auto-recall + auto-observe primitives as the MCP server.

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette", reason="starlette required for gateway tests")
pytest.importorskip("httpx", reason="httpx required for Starlette TestClient")

from starlette.testclient import TestClient  # noqa: E402

from soul_protocol.gateway import create_app  # noqa: E402
from soul_protocol.runtime.soul import Soul  # noqa: E402


@pytest.fixture
def client():
    soul = asyncio.run(Soul.birth(name="GW", archetype="gateway test"))
    app = create_app(soul)
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["soul"] == "GW"
    assert "did:" in data["did"]


def test_state(client):
    r = client.get("/state")
    assert r.status_code == 200
    data = r.json()
    assert data["soul"] == "GW"
    assert "mood" in data
    assert "energy" in data
    assert "lifecycle" in data


def test_remember_and_recall(client):
    r = client.post("/remember", json={"content": "User prefers Python", "importance": 8})
    assert r.status_code == 200
    assert r.json()["memory_id"]

    r = client.post("/recall", json={"query": "prefers Python"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    assert any("Python" in m["content"] for m in data["memories"])


def test_observe(client):
    r = client.post("/observe", json={"user_input": "I like testing", "agent_output": "Great"})
    assert r.status_code == 200
    assert r.json()["status"] == "observed"


def test_turn_recalls_and_observes(client):
    client.post(
        "/remember", json={"content": "User's favorite language is Python", "importance": 8}
    )
    r = client.post(
        "/turn",
        json={
            "user_input": "What's my favorite language?",
            "agent_output": "Python",
            "query": "favorite language",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "observed"
    assert data["recalled"] >= 1
    assert any("language" in m["content"].lower() for m in data["memories"])


def test_validation_errors(client):
    assert client.post("/recall", json={}).status_code == 400
    assert client.post("/observe", json={}).status_code == 400
    assert client.post("/turn", json={}).status_code == 400
