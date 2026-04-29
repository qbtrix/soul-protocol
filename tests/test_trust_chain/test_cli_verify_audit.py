# tests/test_trust_chain/test_cli_verify_audit.py — soul verify / soul audit (#42).
# Created: 2026-04-29 — Clean chain returns exit 0; tampered chain returns exit 1
# with a reason. soul audit --filter memory. shows only matching rows.
# Tests use sync CLI invocation (CliRunner) — the CLI commands themselves
# call asyncio.run() internally, so the test functions must NOT be async.

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction


def _build_signed_soul_dir(tmp_path: Path) -> Path:
    """Synchronous helper: builds a soul directory with chain entries."""

    async def _go() -> Path:
        soul = await Soul.birth("CliTest")
        await soul.observe(Interaction(user_input="hi", agent_output="hello"))
        await soul.observe(Interaction(user_input="more", agent_output="ok"))
        soul_dir = tmp_path / "test-soul"
        await soul.save_local(soul_dir)
        return soul_dir

    return asyncio.new_event_loop().run_until_complete(_go())


def test_soul_verify_clean_chain_returns_zero(tmp_path):
    soul_dir = _build_signed_soul_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["verify", str(soul_dir)])
    assert result.exit_code == 0, result.output
    assert "Chain verified" in result.output


def test_soul_verify_json_output(tmp_path):
    soul_dir = _build_signed_soul_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["verify", str(soul_dir), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["length"] >= 1
    assert isinstance(payload["signers"], list)


def test_soul_verify_tampered_chain_returns_one(tmp_path):
    """Edit chain.json to break the signature, run verify, expect exit 1."""
    soul_dir = _build_signed_soul_dir(tmp_path)

    chain_file = soul_dir / "trust_chain" / "chain.json"
    data = json.loads(chain_file.read_text())
    if len(data["entries"]) >= 2:
        sig = data["entries"][1]["signature"]
        data["entries"][1]["signature"] = "AAAA" + sig[4:]
        chain_file.write_text(json.dumps(data, indent=2))

    runner = CliRunner()
    result = runner.invoke(cli, ["verify", str(soul_dir)])
    assert result.exit_code == 1
    assert "failed" in result.output.lower() or "✗" in result.output


def test_soul_audit_filter_memory_returns_memory_only(tmp_path):
    soul_dir = _build_signed_soul_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["audit", str(soul_dir), "--filter", "memory.", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["entries"]
    for row in payload["entries"]:
        assert row["action"].startswith("memory.")


def test_soul_audit_limit_takes_tail(tmp_path):
    soul_dir = _build_signed_soul_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["audit", str(soul_dir), "--limit", "1", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["entries"]) == 1


def test_soul_audit_default_human_table(tmp_path):
    soul_dir = _build_signed_soul_dir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["audit", str(soul_dir)])
    assert result.exit_code == 0, result.output
    assert "Seq" in result.output
    assert "Action" in result.output
