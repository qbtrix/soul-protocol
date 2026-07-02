# test_demo_server.py — Smoke tests for the "Butcher Remembers" demo server
#   (examples/butcher_remembers/server.py). No browser: a REAL server on an
#   ephemeral port, driven with urllib.
#
# Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — Three tests:
#     * test_snapshot_returns_zones_and_npcs — /snapshot carries the Butcher
#       world: Bjorn at the stall, Astrid at the tables, Ragnar at the door,
#       both NPC HUD entries, a director phase.
#     * test_post_line_advances_events — POST /line runs a real world.beat:
#       the summary carries the NPC's spoken reaction, and /events grows the
#       beat + speech pair; a bogus kind is a clean 400.
#     * test_events_since_filters — /events?since=N returns exactly the
#       events with t > N (an insult beat shows its grudge_change), and a
#       far-future cursor returns [].
#   The server module is imported straight from its file path (examples/ is
#   not a package); each test gets a fresh server + world via the fixture.
#
# Run:  uv run pytest tests/profiles/game/test_demo_server.py -v

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_SERVER_PY = Path(__file__).resolve().parents[3] / "examples" / "butcher_remembers" / "server.py"


def _load_server_module():
    spec = importlib.util.spec_from_file_location("butcher_remembers_server", _SERVER_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server_mod = _load_server_module()


@pytest.fixture()
def base_url():
    """A live demo server on an ephemeral port, torn down after the test."""
    httpd, state = server_mod.create_server(port=0)
    thread = threading.Thread(target=httpd.serve_forever, name="butcher-http", daemon=True)
    thread.start()
    port = httpd.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        state.close()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(url: str, payload: dict):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_snapshot_returns_zones_and_npcs(base_url: str) -> None:
    snap = _get(f"{base_url}/snapshot")
    assert snap["zones"] == {"Bjorn": "stall", "Astrid": "tables", "Ragnar": "door"}
    assert [npc["name"] for npc in snap["npcs"]] == ["Bjorn", "Astrid"]
    assert snap["phase"] == "BUILD_UP"
    ragnar = snap["players"][0]
    assert ragnar["name"] == "Ragnar"
    # Fresh world: both NPCs hold nothing against Ragnar yet.
    for npc in snap["npcs"]:
        assert npc["players"][ragnar["did"]]["grudge"] == "NONE"


def test_post_line_advances_events(base_url: str) -> None:
    before = _get(f"{base_url}/events?since=0")  # the three build-time move events
    assert {e["type"] for e in before} == {"move"}

    summary = _post(
        f"{base_url}/line",
        {"player": "Ragnar", "text": "Morning, butcher.", "kind": "neutral", "npc": "Bjorn"},
    )
    assert summary["npc"] == "Bjorn"
    assert summary["reaction"]  # the NPC actually spoke
    assert summary["grudge_level"] == "NONE"

    after = _get(f"{base_url}/events?since=0")
    assert len(after) > len(before)
    types = [e["type"] for e in after]
    assert "beat" in types and "speech" in types

    # A bogus kind is rejected cleanly, not a 500.
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(f"{base_url}/line", {"player": "Ragnar", "text": "x", "kind": "arson"})
    assert excinfo.value.code == 400


def test_events_since_filters(base_url: str) -> None:
    _post(f"{base_url}/line", {"player": "Ragnar", "text": "Hello there.", "kind": "neutral"})
    cursor = max(e["t"] for e in _get(f"{base_url}/events?since=0"))

    _post(
        f"{base_url}/line",
        {"player": "Ragnar", "text": "Your meat is maggoty.", "kind": "insult", "npc": "Bjorn"},
    )
    fresh = _get(f"{base_url}/events?since={cursor}")
    assert fresh, "the second beat must produce new events"
    assert all(e["t"] > cursor for e in fresh)
    types = [e["type"] for e in fresh]
    assert "beat" in types and "speech" in types
    assert "grudge_change" in types  # the insult tripped NONE -> SLIGHTED

    assert _get(f"{base_url}/events?since=1000000000") == []
