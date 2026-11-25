# tests/test_consent/test_consent_hardening.py — Regression tests from the consent review.
# Created: 2026-11-14 — Un-revoking by editing consent.json, deleting log lines,
#   unknown-token flooding, log trimming vs. verification, Rich markup in CLI
#   output, MCP zip saves keeping the private key, encrypted soul_path refusal,
#   CLI --password, and recall returning copies.

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.runtime.consent import ConsentRegistry
from soul_protocol.runtime.exceptions import ConsentDeniedError
from soul_protocol.runtime.soul import Soul


async def _soul() -> Soul:
    soul = await Soul.birth("Hard")
    await soul.remember("User has a knee injury", domain="health")
    await soul.remember("User salary is 80000 rupees", domain="finance")
    return soul


async def test_unrevoking_by_editing_the_file_is_refused_and_detected(tmp_path):
    soul = await _soul()
    consent_pass, token = soul.grant_consent("fit", ["health"], duration="1d")
    soul.revoke_consent(consent_pass.id)
    await soul.save_local(tmp_path / "s")

    consent_file = tmp_path / "s" / "consent" / "consent.json"
    data = json.loads(consent_file.read_text(encoding="utf-8"))
    data["passes"][0]["revoked_at"] = None
    consent_file.write_text(json.dumps(data), encoding="utf-8")

    reloaded = await Soul.awaken(str(tmp_path / "s"))
    with pytest.raises(ConsentDeniedError) as info:
        await reloaded.consent_session(token).recall("knee")
    assert info.value.reason == "revoked"

    # Deleting the revoke line too is caught by verification.
    data["events"] = [e for e in data["events"] if e["kind"] != "revoke"]
    consent_file.write_text(json.dumps(data), encoding="utf-8")
    reloaded = await Soul.awaken(str(tmp_path / "s"))
    report = reloaded.verify_consent_log()
    assert report["ok"] is False
    assert [m["action"] for m in report["missing_entries"]] == ["consent.revoke"]


async def test_deleted_log_line_is_reported_missing():
    soul = await _soul()
    _, token = soul.grant_consent("fit", ["health"], duration="1d")
    await soul.consent_session(token).recall("knee")
    assert soul.verify_consent_log()["ok"] is True

    soul.consent._events = [e for e in soul.consent._events if e.kind != "read"]

    report = soul.verify_consent_log()
    assert report["unverified"] == 0
    assert report["missing"] == 1
    assert report["missing_entries"][0]["action"] == "consent.read"
    assert report["ok"] is False


async def test_unknown_tokens_do_not_grow_chain_or_log():
    soul = await _soul()
    soul.grant_consent("fit", ["health"], duration="1d")
    chain_len, log_len = soul.trust_chain.length, len(soul.consent_events())

    for i in range(25):
        with pytest.raises(ConsentDeniedError):
            await soul.consent_session(f"scp_junk{i}").recall("x", domain="d" * 5000)

    assert soul.trust_chain.length == chain_len
    assert len(soul.consent_events()) == log_len
    assert soul.consent.unknown_token_denials == 25


async def test_denied_domains_are_capped():
    soul = await _soul()
    _, token = soul.grant_consent("fit", ["health"], duration="1d")
    with pytest.raises(ConsentDeniedError):
        await soul.consent_session(token).recall("x", domain="z" * 5000)
    assert len(soul.consent_events(limit=1)[0].domains[0]) == 100


async def test_trimmed_events_are_not_reported_missing(tmp_path):
    soul = await _soul()
    soul._consent = ConsentRegistry(max_events=3)
    _, token = soul.grant_consent("fit", ["health"], duration="1d")
    for _ in range(5):
        await soul.consent_session(token).recall("knee")

    report = soul.verify_consent_log()
    assert (report["total"], report["missing"], report["ok"]) == (3, 0, True)

    await soul.save_local(tmp_path / "s")
    reloaded = await Soul.awaken(str(tmp_path / "s"))
    assert reloaded.consent.trimmed_through_seq == soul.consent.trimmed_through_seq
    assert reloaded.verify_consent_log()["ok"] is True


async def test_recall_returns_copies():
    soul = await _soul()
    _, token = soul.grant_consent("fit", ["health"], duration="1d")
    [entry] = await soul.consent_session(token).recall("knee", limit=1)
    entry.content = "edited by app"
    stored = await soul.recall("knee injury", domain="health")
    assert stored[0].content == "User has a knee injury"


def test_cli_survives_markup_in_app_supplied_text(tmp_path):
    async def _build():
        soul = await _soul()
        _, token = soul.grant_consent("fit", ["health"], duration="1d", note="[/oops]")
        with pytest.raises(ConsentDeniedError):
            await soul.consent_session(token).recall("x", domain="[/bold]")
        await soul.save_local(tmp_path / "s")

    asyncio.new_event_loop().run_until_complete(_build())
    runner = CliRunner()
    result = runner.invoke(cli, ["consent", "log", str(tmp_path / "s")])
    assert result.exit_code == 0, result.output
    assert "[/bold]" in result.output
    result = runner.invoke(cli, ["consent", "list", str(tmp_path / "s")])
    assert result.exit_code == 0, result.output
    assert "[/oops]" in result.output


def test_cli_password_round_trip(tmp_path):
    path = tmp_path / "locked.soul"

    async def _build():
        soul = await _soul()
        await soul.export(path, password="pw", include_keys=True)

    asyncio.new_event_loop().run_until_complete(_build())
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["consent", "grant", str(path), "-p", "--app", "fit", "--domain", "health", "--json"],
        input="pw\n",
    )
    assert result.exit_code == 0, result.output

    async def _check():
        reloaded = await Soul.awaken(str(path), password="pw")
        assert reloaded.can_sign
        assert [p.app_id for p in reloaded.consent_passes()] == ["fit"]

    asyncio.new_event_loop().run_until_complete(_check())


async def test_mcp_zip_save_keeps_private_key(tmp_path, monkeypatch):
    pytest.importorskip("fastmcp")
    from fastmcp import Client

    import soul_protocol.mcp.server as server_module
    from soul_protocol.mcp.server import mcp

    path = tmp_path / "z.soul"
    soul = await _soul()
    await soul.export(path, include_keys=True)

    server_module._registry.clear()
    monkeypatch.delenv("SOUL_DIR", raising=False)
    monkeypatch.setenv("SOUL_PATH", str(path))
    monkeypatch.chdir(tmp_path)
    try:
        async with Client(mcp) as client:
            granted = json.loads(
                (
                    await client.call_tool(
                        "soul_consent_grant", {"app_id": "fit", "domains": ["health"]}
                    )
                ).data
            )
            await client.call_tool(
                "soul_recall", {"query": "knee", "consent_token": granted["token"]}
            )
        reloaded = await Soul.awaken(str(path))
        assert reloaded.can_sign
        # The consented read was saved right away, not only at shutdown.
        assert [e.kind for e in reloaded.consent_events()] == ["read", "grant"]
        assert reloaded.verify_consent_log()["ok"] is True
    finally:
        server_module._registry.clear()


def test_gateway_refuses_encrypted_soul_path(tmp_path):
    pytest.importorskip("starlette")
    from soul_protocol.gateway import create_app

    path = tmp_path / "locked.soul"

    async def _build():
        soul = await _soul()
        await soul.export(path, password="pw", include_keys=True)
        return soul

    soul = asyncio.new_event_loop().run_until_complete(_build())
    with pytest.raises(ValueError, match="encrypted"):
        create_app(soul, soul_path=str(path))
    create_app(soul, soul_path=str(Path(tmp_path / "plain")))  # non-archive path is fine
