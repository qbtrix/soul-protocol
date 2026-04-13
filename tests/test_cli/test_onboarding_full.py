# test_onboarding_full.py — Tests for the extended `soul org init` wizard,
# `soul org status`, `soul org destroy`, and the layered root-undeletability
# guard (Soul.delete + soul delete CLI + EventEntry validator helper).
# Updated: feat/onboarding-full — command invocations updated from `paw os`
#   to the flat `org` group; invite hint assertion updated to `soul user invite`.
# Created: feat/onboarding-full — Workstream B of the Org Architecture RFC (#164).

from __future__ import annotations

import asyncio
import json
import tarfile
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.engine.journal import open_journal
from soul_protocol.spec.journal import (
    Actor,
    EventEntry,
    RootProtectedError,
    check_root_undeletable,
)


# --- Helpers ----------------------------------------------------------------


def _full_init(runner: CliRunner, data_dir: Path, users_dir: Path, **overrides) -> object:
    args = [
        "org", "init",
        "--org-name", overrides.get("org_name", "Acme Ventures"),
        "--purpose", overrides.get("purpose", "AI tooling"),
        "--values", overrides.get("values", "audit,velocity,kindness"),
        "--founder-name", overrides.get("founder_name", "Pat"),
        "--founder-email", overrides.get("founder_email", "pat@acme.com"),
        "--scopes", overrides.get("scopes", "org:sales,org:ops,org:me"),
        "--fleet", overrides.get("fleet", "sales"),
        "--data-dir", str(data_dir),
        "--users-dir", str(users_dir),
        "--non-interactive",
    ]
    return runner.invoke(cli, args, catch_exceptions=False)


# --- Wizard ----------------------------------------------------------------


def test_full_wizard_creates_user_scopes_and_fleet(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    users_dir = tmp_path / "users"

    result = _full_init(runner, data_dir, users_dir)
    assert result.exit_code == 0, result.output

    # Founder soul exists
    assert (users_dir / "Pat.soul").exists()

    # Journal events: org.created, scope.created(org:*), org.values_set,
    # user.joined, user.admin_granted, scope.created x3, agent.spawned
    journal = open_journal(data_dir / "journal.db")
    try:
        events = journal.query(limit=100)
    finally:
        journal.close()

    actions = [e.action for e in events]
    assert actions.count("org.created") == 1
    assert actions.count("org.values_set") == 1
    assert actions.count("user.joined") == 1
    assert actions.count("user.admin_granted") == 1
    assert actions.count("scope.created") == 4  # org:* + 3 first-level
    assert actions.count("agent.spawned") == 1

    values_event = next(e for e in events if e.action == "org.values_set")
    assert values_event.payload["values"] == ["audit", "velocity", "kindness"]

    fleet_event = next(e for e in events if e.action == "agent.spawned")
    assert fleet_event.payload["fleet"] == "sales"
    assert fleet_event.payload["placeholder"] is True

    summary = result.output
    assert "Pat" in summary
    assert "sales" in summary
    assert "soul user invite" in summary


def test_skip_fleet_and_minimal_init(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    users_dir = tmp_path / "users"
    result = runner.invoke(
        cli,
        [
            "org", "init",
            "--org-name", "Solo Co",
            "--data-dir", str(data_dir),
            "--users-dir", str(users_dir),
            "--fleet", "skip",
            "--non-interactive",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    journal = open_journal(data_dir / "journal.db")
    try:
        events = journal.query(limit=100)
    finally:
        journal.close()
    actions = [e.action for e in events]
    assert "agent.spawned" not in actions
    assert "user.joined" not in actions


# --- status ---------------------------------------------------------------


def test_status_reports_init_state(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    users_dir = tmp_path / "users"
    _full_init(runner, data_dir, users_dir)

    result = runner.invoke(
        cli, ["org", "status", "--data-dir", str(data_dir), "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    snap = json.loads(result.output)

    assert snap["org_name"] == "Acme Ventures"
    assert snap["values"] == ["audit", "velocity", "kindness"]
    assert snap["user_count"] == 1
    assert snap["agent_count"] == 1
    assert snap["event_count"] == 9  # see test above
    assert "org:*" in snap["scopes"]
    assert "org:sales" in snap["scopes"]
    assert snap["root_did"].startswith("did:soul:")


def test_status_human_readable(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    users_dir = tmp_path / "users"
    _full_init(runner, data_dir, users_dir)
    result = runner.invoke(
        cli, ["org", "status", "--data-dir", str(data_dir)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "Acme Ventures" in result.output
    assert "Events" in result.output


def test_status_missing_dir_errors(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli, ["org", "status", "--data-dir", str(tmp_path / "nope")],
        catch_exceptions=False,
    )
    assert result.exit_code != 0


# --- destroy --------------------------------------------------------------


def test_destroy_without_both_flags_refuses(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    users_dir = tmp_path / "users"
    _full_init(runner, data_dir, users_dir)

    result = runner.invoke(
        cli, ["org", "destroy", "--data-dir", str(data_dir), "--confirm"],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert data_dir.exists()


def test_destroy_archives_then_wipes(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    users_dir = tmp_path / "users"
    archives_dir = tmp_path / "archives"
    _full_init(runner, data_dir, users_dir)

    result = runner.invoke(
        cli,
        [
            "org", "destroy",
            "--data-dir", str(data_dir),
            "--archives-dir", str(archives_dir),
            "--confirm", "--i-mean-it", "--non-interactive",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert not data_dir.exists()

    archives = list(archives_dir.glob("org-destroyed-*.tar.gz"))
    assert len(archives) == 1
    # Verify the tarball actually contains the journal
    with tarfile.open(archives[0]) as tf:
        names = tf.getnames()
    assert any(n.endswith("journal.db") for n in names)


# --- soul delete CLI guard -----------------------------------------------


def test_soul_delete_refuses_root(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    users_dir = tmp_path / "users"
    _full_init(runner, data_dir, users_dir)

    root_path = data_dir / "root.soul"
    result = runner.invoke(
        cli, ["delete", str(root_path), "--yes"], catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert root_path.exists()
    assert "protected" in result.output.lower() or "role" in result.output.lower()


def test_soul_delete_succeeds_for_non_root(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "org"
    users_dir = tmp_path / "users"
    _full_init(runner, data_dir, users_dir)

    founder_path = users_dir / "Pat.soul"
    assert founder_path.exists()
    result = runner.invoke(
        cli, ["delete", str(founder_path), "--yes"], catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert not founder_path.exists()


def test_soul_delete_python_api_raises(tmp_path: Path) -> None:
    from soul_protocol.runtime.exceptions import SoulProtectedError
    from soul_protocol.runtime.soul import Soul

    runner = CliRunner()
    data_dir = tmp_path / "org"
    users_dir = tmp_path / "users"
    _full_init(runner, data_dir, users_dir)

    with pytest.raises(SoulProtectedError):
        Soul.delete(data_dir / "root.soul")


# --- Layer 2: journal validator -----------------------------------------


def _event(action: str, actor_id: str, payload: dict | None = None) -> EventEntry:
    return EventEntry(
        id=uuid4(),
        ts=datetime.now(timezone.utc),
        actor=Actor(kind="agent", id=actor_id, scope_context=["org:*"]),
        action=action,
        scope=["org:*"],
        payload=payload or {},
    )


def test_validator_rejects_root_retire_via_actor() -> None:
    root_did = "did:soul:root-xyz"
    ev = _event("agent.retired", actor_id=root_did)
    with pytest.raises(RootProtectedError):
        check_root_undeletable(ev, root_did)


def test_validator_rejects_root_retire_via_payload() -> None:
    root_did = "did:soul:root-xyz"
    ev = _event(
        "agent.retired",
        actor_id="did:soul:admin-1",
        payload={"target_did": root_did},
    )
    with pytest.raises(RootProtectedError):
        check_root_undeletable(ev, root_did)


def test_validator_rejects_soul_deleted_for_root() -> None:
    root_did = "did:soul:root-xyz"
    ev = _event("soul.deleted", actor_id="did:soul:admin-1", payload={"soul_id": root_did})
    with pytest.raises(RootProtectedError):
        check_root_undeletable(ev, root_did)


def test_validator_passes_for_unrelated_events() -> None:
    root_did = "did:soul:root-xyz"
    # Different action
    check_root_undeletable(_event("agent.spawned", actor_id="did:soul:other"), root_did)
    # Same action but different target
    check_root_undeletable(
        _event("agent.retired", actor_id="did:soul:other", payload={"target_did": "did:soul:other"}),
        root_did,
    )
    # Empty root_did is a no-op
    check_root_undeletable(_event("agent.retired", actor_id="anything"), "")
