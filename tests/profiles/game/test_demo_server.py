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
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel, BD-2) — Six more,
#   all deterministic (templated engine, no network, no LLM):
#     * test_export_soul_returns_zip_download — /export_soul streams real
#       .soul bytes (zip magic PK) with a Content-Disposition attachment.
#     * test_import_soul_round_trip_reverts_grudge — wrong Bjorn, export,
#       wrong him more, import the EARLIER file: grudge level, bond, and the
#       remembered grievance revert to the exported snapshot.
#     * test_reputation_gut_punch — /reputation: clean record -> UNKNOWN and
#       warm; after wronging Bjorn via /line (player_soul wired by
#       world.beat, so deeds accrue on Ragnar), Astrid — never herself
#       wronged — goes NOTORIOUS and cites the hearsay deeds.
#     * test_classify_kind_unit — the keyword classifier's four kinds.
#     * test_line_without_kind_auto_classifies — POST /line with no "kind":
#       theft phrasing lands as a real theft beat (grudge SLIGHTED).
#     * test_cost_endpoint_templated_zeros — /cost is all zeros / null model
#       on the templated engine, and /snapshot reports engine=templated.
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


def _post_for_bytes(url: str, payload: dict) -> tuple[bytes, dict]:
    """POST JSON, return (raw response bytes, headers) — for the .soul downloads."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as resp:
        return resp.read(), dict(resp.headers)


def _post_octets(url: str, data: bytes):
    """POST raw bytes (the /import_soul body) and parse the JSON reply."""
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as resp:
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


# ---------------------------------------------------------------------------
# BD-2 — the 90-second demo endpoints (templated engine, fully deterministic)
# ---------------------------------------------------------------------------


def test_export_soul_returns_zip_download(base_url: str) -> None:
    data, headers = _post_for_bytes(f"{base_url}/export_soul", {"npc": "Bjorn"})
    assert data[:2] == b"PK", "a .soul is a zip archive — bytes must start with the PK magic"
    assert headers.get("Content-Type") == "application/octet-stream"
    assert 'attachment; filename="bjorn.soul"' in headers.get("Content-Disposition", "")

    # The player.soul download works the same way.
    pdata, pheaders = _post_for_bytes(f"{base_url}/export_player", {"player": "Ragnar"})
    assert pdata[:2] == b"PK"
    assert 'filename="ragnar.player.soul"' in pheaders.get("Content-Disposition", "")


def test_import_soul_round_trip_reverts_grudge(base_url: str) -> None:
    ragnar_did = _get(f"{base_url}/snapshot")["players"][0]["did"]

    # Wrong Bjorn once -> SLIGHTED, then export him: the file IS his memory.
    slighted = _post(
        f"{base_url}/line",
        {"player": "Ragnar", "text": "Your meat is maggoty.", "kind": "insult", "npc": "Bjorn"},
    )
    assert slighted["grudge_level"] == "SLIGHTED"
    exported_bond = slighted["bond"]
    soul_bytes, _ = _post_for_bytes(f"{base_url}/export_soul", {"npc": "Bjorn"})

    # Wrong him more AFTER the export -> GRUDGING in the live world.
    worse = _post(
        f"{base_url}/line",
        {"player": "Ragnar", "text": "And I stole your ham.", "kind": "theft", "npc": "Bjorn"},
    )
    assert worse["grudge_level"] == "GRUDGING"
    assert worse["bond"] < exported_bond

    # Import the EARLIER file: Bjorn reverts to the exported snapshot —
    # SLIGHTED, the pre-theft bond, and only the insult remembered.
    result = _post_octets(f"{base_url}/import_soul", soul_bytes)
    assert result["replaced"] == "Bjorn"
    snap = _get(f"{base_url}/snapshot")
    bjorn = next(npc for npc in snap["npcs"] if npc["name"] == "Bjorn")
    assert bjorn["players"][ragnar_did]["grudge"] == "SLIGHTED"
    assert bjorn["players"][ragnar_did]["bond"] == pytest.approx(exported_bond)
    assert bjorn["players"][ragnar_did]["last_grievance"] == "Your meat is maggoty."


def test_reputation_gut_punch(base_url: str) -> None:
    # Clean record: Astrid has heard nothing — warm welcome, UNKNOWN.
    clean = _get(f"{base_url}/reputation?npc=Astrid&player=Ragnar")
    assert clean["npc"] == "Astrid"
    assert clean["notoriety"] == "UNKNOWN"
    assert "Astrid" in clean["line"]

    # Wrong BJORN twice; world.beat wires player_soul=Ragnar, so the deeds
    # accrue on Ragnar's own player.soul (his portable reputation).
    for kind, text in [
        ("theft", "I pocketed a string of sausages."),
        ("betrayal", "I told the guard your scales are rigged."),
    ]:
        _post(
            f"{base_url}/line",
            {"player": "Ragnar", "text": text, "kind": kind, "npc": "Bjorn"},
        )

    # THE gut-punch: Astrid was never wronged, but word travels.
    punch = _get(f"{base_url}/reputation?npc=Astrid&player=Ragnar")
    assert punch["notoriety"] == "NOTORIOUS"
    assert "Word travels" in punch["line"]
    assert "betrayed someone who trusted you" in punch["line"]  # worst deed cited


def test_classify_kind_unit() -> None:
    cases = {
        "While you argued with the guard, I pocketed a string of sausages.": "theft",
        "I stole your best ham, old man.": "theft",
        "I told the town guard you water down your salt pork.": "betrayal",
        "I lied to everyone about you.": "betrayal",
        "You worthless maggot of a butcher.": "insult",
        "You are a fool and a coward.": "insult",
        "Good morning! Fine sausages you have today.": "neutral",
        "": "neutral",
    }
    for text, expected in cases.items():
        assert server_mod.classify_kind(text) == expected, text


def test_line_without_kind_auto_classifies(base_url: str) -> None:
    summary = _post(
        f"{base_url}/line",
        {"player": "Ragnar", "text": "I pocketed a string of sausages.", "npc": "Bjorn"},
    )
    assert summary["kind"] == "theft"  # the classifier heard the theft
    assert summary["grudge_level"] == "SLIGHTED"  # and it landed as a real beat


def test_cost_endpoint_templated_zeros(base_url: str) -> None:
    assert _get(f"{base_url}/snapshot")["engine"] == "templated"
    cost = _get(f"{base_url}/cost")
    assert cost["engine"] == "templated"
    assert cost["model"] is None
    assert cost["calls"] == 0 and cost["cached_calls"] == 0
    assert cost["tokens_in"] == 0 and cost["tokens_out"] == 0
    assert cost["total_cost"] == 0.0
    assert cost["projected_deepseek"] == 0.0
    assert cost["cost_per_player_hour"] == 0.0
