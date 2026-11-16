# tests/test_consent/test_consent_surfaces.py — Consent passes over MCP, CLI and the gateway.
# Created: 2026-11-14 — soul_consent_* MCP tools and consent_token on
#   soul_recall / soul_remember; `soul consent grant|list|revoke|log`; gateway
#   X-Consent-Token on /recall + /remember, GET /api/consents, POST
#   /api/consents/revoke, and that the dashboard ships the Consents section.

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.runtime.soul import Soul


async def _make_soul(path: Path, *, archive: bool = False) -> Path:
    soul = await Soul.birth("Gate")
    await soul.remember("User has a knee injury", domain="health")
    await soul.remember("User salary is 80000 rupees", domain="finance")
    if archive:
        await soul.export(path, include_keys=True)
    else:
        await soul.save_local(path)
    return path


def _build(path: Path, *, archive: bool = False) -> Path:
    return asyncio.new_event_loop().run_until_complete(_make_soul(path, archive=archive))


# ---------- MCP ----------


@pytest.fixture
def mcp_env(tmp_path, monkeypatch):
    pytest.importorskip("fastmcp")
    import soul_protocol.mcp.server as server_module

    server_module._registry.clear()
    monkeypatch.delenv("SOUL_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    soul_dir = tmp_path / "gate"
    monkeypatch.setenv("SOUL_PATH", str(soul_dir))
    yield soul_dir
    server_module._registry.clear()


async def test_mcp_grant_recall_revoke_flow(mcp_env):
    from fastmcp import Client

    from soul_protocol.mcp.server import mcp

    await _make_soul(mcp_env)
    async with Client(mcp) as client:
        granted = json.loads(
            (
                await client.call_tool(
                    "soul_consent_grant",
                    {"app_id": "fitness-app", "domains": ["health"], "duration": "1d"},
                )
            ).data
        )
        token, pass_id = granted["token"], granted["pass"]["id"]
        assert granted["saved_to"] == str(mcp_env)
        assert granted["pass"]["status"] == "active"

        # Saved to disk right away, without waiting for shutdown.
        on_disk = await Soul.awaken(str(mcp_env))
        assert on_disk.consent.get(pass_id) is not None

        recalled = json.loads(
            (
                await client.call_tool(
                    "soul_recall",
                    {"query": "knee injury salary", "limit": 10, "consent_token": token},
                )
            ).data
        )
        assert recalled["count"] >= 1
        assert {m["domain"] for m in recalled["memories"]} == {"health"}

        with pytest.raises(Exception, match="domain_not_allowed"):
            await client.call_tool(
                "soul_recall", {"query": "salary", "domain": "finance", "consent_token": token}
            )
        with pytest.raises(Exception, match="cannot be combined"):
            await client.call_tool(
                "soul_recall", {"query": "x", "layer": "semantic", "consent_token": token}
            )
        with pytest.raises(Exception, match="write_not_allowed"):
            await client.call_tool("soul_remember", {"content": "x", "consent_token": token})

        listed = json.loads((await client.call_tool("soul_consent_list", {})).data)
        assert [p["id"] for p in listed["passes"]] == [pass_id]
        assert "token" not in json.dumps(listed["passes"])

        revoked = json.loads(
            (await client.call_tool("soul_consent_revoke", {"pass_id": pass_id})).data
        )
        assert revoked["pass"]["status"] == "revoked"
        with pytest.raises(Exception, match="revoked"):
            await client.call_tool("soul_recall", {"query": "knee", "consent_token": token})

        log = json.loads(
            (await client.call_tool("soul_consent_log", {"limit": 10, "verify": True})).data
        )
        kinds = [e["kind"] for e in log["events"]]
        assert kinds[:2] == ["denied", "revoke"]
        assert "read" in kinds and "grant" in kinds
        assert log["verification"]["chain_valid"] is True
        assert log["verification"]["unverified"] == 0

        with pytest.raises(Exception, match="No consent pass"):
            await client.call_tool("soul_consent_revoke", {"pass_id": "cp_missing"})


async def test_mcp_consented_write_goes_to_pass_domain(mcp_env):
    from fastmcp import Client

    from soul_protocol.mcp.server import mcp

    await _make_soul(mcp_env)
    async with Client(mcp) as client:
        granted = json.loads(
            (
                await client.call_tool(
                    "soul_consent_grant",
                    {"app_id": "coach", "domains": ["health"], "access": "read_write"},
                )
            ).data
        )
        stored = json.loads(
            (
                await client.call_tool(
                    "soul_remember",
                    {"content": "Ran 5km today", "consent_token": granted["token"]},
                )
            ).data
        )
        assert stored["domain"] == "health"

        with pytest.raises(Exception, match="Invalid duration"):
            await client.call_tool(
                "soul_consent_grant", {"app_id": "a", "domains": ["x"], "duration": "forever"}
            )


# ---------- CLI ----------


def test_cli_grant_list_revoke_log(tmp_path):
    soul_path = _build(tmp_path / "cli.soul", archive=True)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["consent", "grant", str(soul_path), "--app", "fit", "--domain", "health", "--json"],
    )
    assert result.exit_code == 0, result.output
    granted = json.loads(result.output)
    token, pass_id = granted["token"], granted["pass"]["id"]
    assert granted["pass"]["expires_at"]

    # The grant was saved with the private key, so a reloaded soul can still sign reads.
    async def _read():
        soul = await Soul.awaken(str(soul_path))
        assert soul.can_sign
        await soul.consent_session(token).recall("knee")
        await soul.export(soul_path, include_keys=True)

    asyncio.new_event_loop().run_until_complete(_read())

    result = runner.invoke(cli, ["consent", "list", str(soul_path), "--json"])
    assert result.exit_code == 0, result.output
    assert [p["id"] for p in json.loads(result.output)["passes"]] == [pass_id]
    assert token not in result.output

    result = runner.invoke(cli, ["consent", "revoke", str(soul_path), pass_id, "--reason", "done"])
    assert result.exit_code == 0, result.output
    assert "Revoked" in result.output

    result = runner.invoke(cli, ["consent", "list", str(soul_path), "--json"])
    assert json.loads(result.output)["passes"] == []
    result = runner.invoke(cli, ["consent", "list", str(soul_path), "--all"])
    assert "revoked" in result.output

    result = runner.invoke(cli, ["consent", "log", str(soul_path), "--verify", "--json"])
    assert result.exit_code == 0, result.output
    log = json.loads(result.output)
    assert [e["kind"] for e in log["events"]] == ["revoke", "read", "grant"]
    assert log["verification"]["unverified"] == 0


def test_cli_errors_exit_nonzero(tmp_path):
    soul_path = _build(tmp_path / "cli-dir")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["consent", "grant", str(soul_path), "--app", "fit", "--domain", "health", "--for", "9y"],
    )
    assert result.exit_code == 1
    assert "Invalid duration" in result.output
    result = runner.invoke(cli, ["consent", "revoke", str(soul_path), "cp_missing"])
    assert result.exit_code == 1


def test_cli_log_verify_fails_on_tampered_log(tmp_path):
    soul_dir = _build(tmp_path / "tamper")
    runner = CliRunner()
    runner.invoke(cli, ["consent", "grant", str(soul_dir), "--app", "fit", "--domain", "health"])

    consent_file = soul_dir / "consent" / "consent.json"
    data = json.loads(consent_file.read_text(encoding="utf-8"))
    data["events"][0]["domains"] = ["finance"]
    consent_file.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(cli, ["consent", "log", str(soul_dir), "--verify"])
    assert result.exit_code == 1
    assert "0 of 1" in result.output


# ---------- Gateway + dashboard ----------


@pytest.fixture
def gateway(tmp_path):
    pytest.importorskip("starlette")
    pytest.importorskip("httpx")
    from starlette.testclient import TestClient

    from soul_protocol.gateway import create_app

    soul_dir = _build(tmp_path / "gw")
    soul = asyncio.new_event_loop().run_until_complete(Soul.awaken(str(soul_dir)))
    _, token = soul.grant_consent("fitness-app", ["health"], duration="1d")
    with TestClient(create_app(soul, soul_path=str(soul_dir))) as client:
        yield client, soul, token, soul_dir


def test_gateway_recall_with_consent_token(gateway):
    client, soul, token, soul_dir = gateway
    r = client.post(
        "/recall",
        json={"query": "knee injury salary", "limit": 10},
        headers={"X-Consent-Token": token},
    )
    assert r.status_code == 200, r.text
    assert {m["domain"] for m in r.json()["memories"]} == {"health"}

    r = client.post(
        "/recall",
        json={"query": "salary", "domain": "finance"},
        headers={"X-Consent-Token": token},
    )
    assert r.status_code == 403
    assert r.json()["reason"] == "domain_not_allowed"

    r = client.post("/recall", json={"query": "x"}, headers={"X-Consent-Token": "scp_nope"})
    assert (r.status_code, r.json()["reason"]) == (403, "unknown_token")

    r = client.post(
        "/recall", json={"query": "x", "user_id": "u"}, headers={"X-Consent-Token": token}
    )
    assert r.status_code == 400

    # Reads and real denials were saved to disk. The unknown token was only
    # counted in memory and did not trigger a save.
    on_disk = asyncio.new_event_loop().run_until_complete(Soul.awaken(str(soul_dir)))
    assert [e.kind for e in on_disk.consent_events()] == ["denied", "read", "grant"]
    assert soul.consent.unknown_token_denials == 1


def test_gateway_remember_with_consent_token(gateway):
    client, soul, token, _ = gateway
    r = client.post("/remember", json={"content": "Ran 5km"}, headers={"X-Consent-Token": token})
    assert (r.status_code, r.json()["reason"]) == (403, "write_not_allowed")

    _, rw_token = soul.grant_consent("coach", ["health"], duration="1h", access="read_write")
    r = client.post("/remember", json={"content": "Ran 5km"}, headers={"X-Consent-Token": rw_token})
    assert r.status_code == 200, r.text
    assert soul.consent_events(limit=1)[0].kind == "write"


def test_gateway_api_consents_and_revoke(gateway):
    client, soul, token, soul_dir = gateway
    data = client.get("/api/consents").json()
    assert data["persisted"] is True
    assert [p["app_id"] for p in data["passes"]] == ["fitness-app"]
    assert data["verification"]["chain_valid"] is True
    pass_id = data["passes"][0]["id"]

    r = client.post("/api/consents/revoke", content=json.dumps({"pass_id": pass_id}))
    assert r.status_code == 415  # JSON content type required (CSRF guard)

    r = client.post("/api/consents/revoke", json={"pass_id": pass_id})
    assert r.status_code == 200, r.text
    assert r.json()["pass"]["status"] == "revoked"
    r = client.post("/recall", json={"query": "knee"}, headers={"X-Consent-Token": token})
    assert (r.status_code, r.json()["reason"]) == (403, "revoked")

    on_disk = asyncio.new_event_loop().run_until_complete(Soul.awaken(str(soul_dir)))
    assert on_disk.consent.get(pass_id).status() == "revoked"

    assert client.post("/api/consents/revoke", json={"pass_id": "cp_x"}).status_code == 404
    assert client.post("/api/consents/revoke", json={}).status_code == 400


def test_gateway_without_soul_path_does_not_write(tmp_path):
    pytest.importorskip("starlette")
    from starlette.testclient import TestClient

    from soul_protocol.gateway import create_app

    soul = asyncio.new_event_loop().run_until_complete(Soul.birth("Mem"))
    _, token = soul.grant_consent("a", ["default"], duration="1h")
    before = set(os.listdir(tmp_path))
    with TestClient(create_app(soul)) as client:
        assert client.get("/api/consents").json()["persisted"] is False
        r = client.post("/recall", json={"query": "x"}, headers={"X-Consent-Token": token})
        assert r.status_code == 200
    assert set(os.listdir(tmp_path)) == before


def test_dashboard_has_consents_section(gateway):
    client, *_ = gateway
    html = client.get("/dashboard").text
    assert 'data-tab="consents"' in html
    assert 'id="v-consents"' in html
    assert "/api/consents/revoke" in html
