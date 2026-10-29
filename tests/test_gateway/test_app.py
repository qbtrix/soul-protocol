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


# ---- #318 review: CSRF-safe bodies and input validation ----


@pytest.mark.parametrize(
    "path", ["/remember", "/recall", "/observe", "/turn", "/v1/chat/completions"]
)
def test_post_rejects_non_json_content_type(client, path):
    """A cross-site text/plain POST skips CORS preflight, so it must be refused."""
    r = client.post(
        path,
        content='{"content": "injected", "query": "x", "user_input": "x"}',
        headers={"Content-Type": "text/plain", "Origin": "https://evil.example"},
    )
    assert r.status_code == 415


def test_text_plain_remember_does_not_store(client):
    client.post(
        "/remember",
        content='{"content": "planted memory"}',
        headers={"Content-Type": "text/plain"},
    )
    r = client.post("/recall", json={"query": "planted memory"})
    assert r.json()["count"] == 0


def test_remember_bad_importance_is_400(client):
    r = client.post("/remember", json={"content": "x", "importance": "abc"})
    assert r.status_code == 400
    assert "importance" in r.json()["error"]


def test_recall_bad_limit_is_400(client):
    r = client.post("/recall", json={"query": "x", "limit": "abc"})
    assert r.status_code == 400
    assert "limit" in r.json()["error"]


def test_recall_limit_is_capped(client):
    for i in range(3):
        client.post("/remember", json={"content": f"Python fact {i}"})
    r = client.post("/recall", json={"query": "Python", "limit": 100000})
    assert r.status_code == 200
    assert r.json()["count"] <= 200


def test_api_memories_bad_limit_is_400(client):
    r = client.get("/api/memories", params={"limit": "abc"})
    assert r.status_code == 400
