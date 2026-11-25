# tests/test_consent/test_consent_cli.py — `soul consent grant|list|revoke|log`.
# Created: 2026-11-14 — CLI round trips, error exits, and `log --verify` on a
#   tampered log. (MCP and gateway consent tests ship with that follow-up PR.)

from __future__ import annotations

import asyncio
import json
from pathlib import Path

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
        await soul.consent.session(token).recall("knee")
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
