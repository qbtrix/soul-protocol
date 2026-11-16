# tests/test_gateway/test_dashboard.py — Web dashboard endpoints.
# Created: 2026-09 — Verifies the super-minimal dashboard (HTML) plus the three
#   read-only JSON endpoints it consumes: /api/personality, /api/memories,
#   /api/stats.

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
    soul = asyncio.run(Soul.birth(name="Dash", archetype="dashboard test"))
    app = create_app(soul)
    with TestClient(app) as c:
        yield c


def test_dashboard_serves_html(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "<html" in r.text
    assert "Soul Dashboard" in r.text


def test_personality_returns_ocean(client):
    r = client.get("/api/personality")
    assert r.status_code == 200
    data = r.json()
    assert data["soul"] == "Dash"
    ocean = data["ocean"]
    for trait in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
        assert trait in ocean
        assert 0.0 <= ocean[trait] <= 1.0


def test_memories_lists_and_searches(client):
    client.post("/remember", json={"content": "User prefers Python", "importance": 8})
    client.post("/remember", json={"content": "User lives in Mumbai", "importance": 7})

    r = client.get("/api/memories")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 2
    contents = [m["content"] for m in data["memories"]]
    assert any("Python" in c for c in contents)

    r = client.get("/api/memories", params={"q": "Mumbai"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    assert any("Mumbai" in m["content"] for m in data["memories"])


def test_memories_respects_limit(client):
    for i in range(5):
        client.post("/remember", json={"content": f"Fact number {i}", "importance": 5})
    r = client.get("/api/memories", params={"limit": 2})
    assert r.status_code == 200
    assert r.json()["count"] == 2


def test_stats_returns_counts_and_bond(client):
    client.post("/remember", json={"content": "A semantic fact", "importance": 5})
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    counts = data["memory_counts"]
    assert counts["total"] >= 1
    assert counts["semantic"] >= 1
    assert "interaction_count" in data
    assert "bond" in data
    assert "strength" in data["bond"]
    assert "label" in data["bond"]


# ---- v2 endpoint tests ----


def test_identity_returns_core_fields(client):
    r = client.get("/api/identity")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Dash"
    assert "did" in data
    assert "archetype" in data
    assert "core_values" in data
    assert "persona" in data
    assert "lifecycle" in data
    assert "incarnation" in data


def test_communication_returns_style_and_biorhythms(client):
    r = client.get("/api/communication")
    assert r.status_code == 200
    data = r.json()
    for key in ("warmth", "verbosity", "humor_style", "emoji_usage"):
        assert key in data
    assert "biorhythms" in data
    bio = data["biorhythms"]
    assert "chronotype" in bio
    assert "mood_inertia" in bio


def test_skills_returns_list(client):
    r = client.get("/api/skills")
    assert r.status_code == 200
    data = r.json()
    assert data["soul"] == "Dash"
    assert "skills" in data
    assert isinstance(data["skills"], list)


def test_evolution_returns_mode_and_pending(client):
    r = client.get("/api/evolution")
    assert r.status_code == 200
    data = r.json()
    assert "mode" in data
    assert "mutation_rate" in data
    assert "mutable_traits" in data
    assert "immutable_traits" in data
    assert "pending" in data


def test_evaluations_returns_list(client):
    r = client.get("/api/evaluations")
    assert r.status_code == 200
    data = r.json()
    assert data["soul"] == "Dash"
    assert "evaluations" in data
    assert isinstance(data["evaluations"], list)


def test_trust_chain_returns_entries(client):
    r = client.get("/api/trust-chain")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "entries" in data
    assert isinstance(data["entries"], list)


def test_self_model_returns_images(client):
    r = client.get("/api/self-model")
    assert r.status_code == 200
    data = r.json()
    assert data["soul"] == "Dash"
    assert "self_images" in data


def test_metadata_returns_config(client):
    r = client.get("/api/metadata")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "did" in data
    assert "lifecycle" in data
    assert "memory_config" in data
    mc = data["memory_config"]
    assert "episodic_max_entries" in mc
    assert "semantic_max_facts" in mc


def test_dashboard_links_favicon_and_legal_pages(client):
    html = client.get("/dashboard").text
    assert 'href="/favicon.svg"' in html
    assert 'href="/privacy"' in html
    assert 'href="/terms"' in html


@pytest.mark.parametrize("path", ["/favicon.svg", "/favicon.ico"])
def test_favicon_served_as_svg(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.startswith("<svg")


@pytest.mark.parametrize(
    ("path", "title"),
    [("/privacy", "Privacy Policy"), ("/terms", "Terms and Conditions")],
)
def test_legal_pages(client, path, title):
    r = client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert f"<h1>{title}</h1>" in r.text
    assert 'href="/dashboard"' in r.text
