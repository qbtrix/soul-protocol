# tests/test_trust_chain/test_cli_prune_chain.py — soul prune-chain CLI (#203).
# Created: 2026-04-29 — Dry-run preview shows expected count/seq range without
# touching the chain. --apply persists the prune. Mismatched configs (no
# --keep, no biorhythm cap) exit non-zero with a JSON error payload.

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction


def _build_soul_with_chain(tmp_path: Path, n: int = 30) -> Path:
    """Build a soul directory whose chain has many entries."""

    async def _go() -> Path:
        soul = await Soul.birth("PruneTest")
        # Each observe appends a couple of memory.write entries to the chain.
        for i in range(n):
            await soul.observe(Interaction(user_input=f"q{i}", agent_output=f"a{i}"))
        soul_dir = tmp_path / "prune-soul"
        await soul.save_local(soul_dir)
        return soul_dir

    return asyncio.new_event_loop().run_until_complete(_go())


def test_prune_chain_dry_run_shows_summary(tmp_path):
    soul_dir = _build_soul_with_chain(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["prune-chain", str(soul_dir), "--keep", "5", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] is False
    assert payload["summary"]["count"] >= 1
    assert payload["keep"] == 5


def test_prune_chain_apply_mutates_chain(tmp_path):
    soul_dir = _build_soul_with_chain(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["prune-chain", str(soul_dir), "--keep", "5", "--apply", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] is True
    assert payload["summary"]["count"] >= 1
    # After apply, a re-awakened soul should still verify.
    chain_file = soul_dir / "trust_chain" / "chain.json"
    data = json.loads(chain_file.read_text())
    # Chain must include the chain.pruned marker
    actions = [e["action"] for e in data["entries"]]
    assert "chain.pruned" in actions


def test_prune_chain_errors_when_no_cap(tmp_path):
    """Without --keep AND without a biorhythm cap, the command exits 2."""
    soul_dir = _build_soul_with_chain(tmp_path, n=5)
    runner = CliRunner()
    result = runner.invoke(cli, ["prune-chain", str(soul_dir)])
    assert result.exit_code == 2


def test_prune_chain_below_threshold_is_no_op(tmp_path):
    """When the chain length is already at/below --keep, nothing happens."""
    soul_dir = _build_soul_with_chain(tmp_path, n=2)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["prune-chain", str(soul_dir), "--keep", "1000", "--apply", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # Even though --apply was passed, count==0 → applied must be False
    # (no marker to write). This matches the dry_run summary shape.
    assert payload["applied"] is False
    assert payload["summary"]["count"] == 0


def test_prune_chain_post_apply_chain_still_verifies(tmp_path):
    """After --apply, the chain must still pass `soul verify`."""
    soul_dir = _build_soul_with_chain(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["prune-chain", str(soul_dir), "--keep", "5", "--apply"],
    )
    assert result.exit_code == 0, result.output
    verify_result = runner.invoke(cli, ["verify", str(soul_dir)])
    assert verify_result.exit_code == 0, verify_result.output
    assert "Chain verified" in verify_result.output
