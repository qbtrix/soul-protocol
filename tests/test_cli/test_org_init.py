# test_org_init.py — Tests for `soul org init`.
# Renamed: feat/paw-os-init — was test_paw_os_init.py. Updated command
#   invocations from `paw os init` to `org init` and banner assertion from
#   "Paw OS ready" to "Org ready".
# Created: feat/paw-os-init — Workstream A slice 3 of the Org Architecture RFC (#164).
# Covers: happy path, idempotency, --force, --non-interactive guard, journal
# queryability, key file permissions, Soul.awaken round-trip, and the privacy
# sanity check that private keys never land in event payloads.

from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path

from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.engine.journal import open_journal


def _invoke_init(runner: CliRunner, data_dir: Path, *extra: str) -> object:
    return runner.invoke(
        cli,
        [
            "org", "init",
            "--org-name", "Acme Ventures",
            "--purpose", "A software company",
            "--data-dir", str(data_dir),
            "--non-interactive",
            *extra,
        ],
        catch_exceptions=False,
    )


def test_fresh_init_creates_all_artifacts(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"

    result = _invoke_init(runner, data_dir)

    assert result.exit_code == 0, result.output
    assert (data_dir / "root.soul").exists()
    assert (data_dir / "journal.db").exists()
    assert (data_dir / "keys" / "root.ed25519").exists()
    assert (data_dir / "keys" / "root.ed25519.pub").exists()
    assert (data_dir / "keys" / "root.did").exists()
    assert "Org ready" in result.output


def test_init_writes_two_genesis_events(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    _invoke_init(runner, data_dir)

    journal = open_journal(data_dir / "journal.db")
    try:
        events = journal.query(limit=100)
    finally:
        journal.close()

    assert len(events) == 2
    actions = [e.action for e in events]
    assert "org.created" in actions
    assert "scope.created" in actions

    created = next(e for e in events if e.action == "org.created")
    assert created.actor.kind == "root"
    assert created.actor.id.startswith("did:soul:")
    assert created.scope == ["org:*"]
    assert created.payload["org_name"] == "Acme Ventures"
    assert created.payload["purpose"] == "A software company"
    assert "created_by_user" in created.payload


def test_rerun_without_force_refuses(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    _invoke_init(runner, data_dir)

    second = _invoke_init(runner, data_dir)

    assert second.exit_code != 0
    assert "already exists" in (second.output + (second.stderr if hasattr(second, "stderr") else ""))


def test_rerun_with_force_overwrites(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    first = _invoke_init(runner, data_dir)
    assert first.exit_code == 0

    # Drop a marker file and confirm --force wipes it.
    marker = data_dir / "marker.txt"
    marker.write_text("stale")

    second = _invoke_init(runner, data_dir, "--force")

    assert second.exit_code == 0, second.output
    assert not marker.exists()
    assert (data_dir / "journal.db").exists()


def test_non_interactive_without_org_name_fails(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"

    result = runner.invoke(
        cli,
        ["org", "init", "--data-dir", str(data_dir), "--non-interactive"],
        catch_exceptions=False,
    )

    assert result.exit_code != 0
    assert not (data_dir / "journal.db").exists()


def test_private_key_has_0600_permissions(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    _invoke_init(runner, data_dir)

    key_path = data_dir / "keys" / "root.ed25519"
    mode = stat.S_IMODE(os.stat(key_path).st_mode)
    # Owner read+write only, no group/other bits.
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_root_soul_is_loadable_by_awaken(tmp_path: Path) -> None:
    from soul_protocol.runtime.soul import Soul

    runner = CliRunner()
    data_dir = tmp_path / "org"
    _invoke_init(runner, data_dir)

    soul = asyncio.run(Soul.awaken(str(data_dir / "root.soul")))
    assert soul.name == "Root"
    assert soul.did.startswith("did:soul:")


def test_private_key_not_in_journal_payloads(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    _invoke_init(runner, data_dir)

    key_bytes = (data_dir / "keys" / "root.ed25519").read_bytes()
    # Grab a distinctive slice — PKCS8 header / base64 body.
    needle = key_bytes[40:80] if len(key_bytes) >= 80 else key_bytes

    journal = open_journal(data_dir / "journal.db")
    try:
        events = journal.query(limit=100)
    finally:
        journal.close()

    for event in events:
        serialized = json.dumps(event.model_dump(mode="json"), default=str)
        assert needle.decode("latin-1") not in serialized
        assert "BEGIN PRIVATE KEY" not in serialized
