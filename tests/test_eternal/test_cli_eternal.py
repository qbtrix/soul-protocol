# test_eternal/test_cli_eternal.py — CLI tests for eternal storage commands.
# Created: 2026-03-06 — Tests archive, recover, and eternal-status commands.

from __future__ import annotations

from click.testing import CliRunner

from soul_protocol.cli.main import cli


def test_archive_command(tmp_path):
    """archive command shows archived tiers for a .soul file."""
    runner = CliRunner()
    soul_path = str(tmp_path / "archive-test.soul")

    # Birth a soul first
    result = runner.invoke(cli, ["birth", "ArchiveBot", "-o", soul_path])
    assert result.exit_code == 0

    # Archive it
    result = runner.invoke(cli, ["archive", soul_path])
    assert result.exit_code == 0
    assert "ipfs" in result.output.lower()
    assert "arweave" in result.output.lower()
    assert "blockchain" in result.output.lower()
    assert "ArchiveBot" in result.output


def test_archive_specific_tier(tmp_path):
    """archive with --tiers flag archives only to specified tiers."""
    runner = CliRunner()
    soul_path = str(tmp_path / "tier-test.soul")

    runner.invoke(cli, ["birth", "TierBot", "-o", soul_path])
    result = runner.invoke(cli, ["archive", soul_path, "-t", "ipfs"])

    assert result.exit_code == 0
    assert "ipfs" in result.output.lower()


def test_eternal_status_command(tmp_path):
    """eternal-status shows tier status for a soul."""
    runner = CliRunner()
    soul_path = str(tmp_path / "status-test.soul")

    runner.invoke(cli, ["birth", "StatusBot", "-o", soul_path])
    result = runner.invoke(cli, ["eternal-status", soul_path])

    assert result.exit_code == 0
    assert "IPFS" in result.output
    assert "Arweave" in result.output
    assert "Blockchain" in result.output


def test_recover_missing_reference(tmp_path):
    """recover with a bad reference shows failure message."""
    runner = CliRunner()
    output_path = str(tmp_path / "recovered.soul")

    result = runner.invoke(cli, ["recover", "nonexistent-ref", "-t", "ipfs", "-o", output_path])

    assert result.exit_code == 0
    assert "failed" in result.output.lower() or "Recovery failed" in result.output
