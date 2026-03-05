# test_cli.py — Tests for the CLI interface using click.testing.CliRunner.
# Updated: v0.2.2 — Version test now checks package version dynamically.
# Created: 2026-02-22 — Covers --version, birth, inspect, and status commands.

from __future__ import annotations

import os

from click.testing import CliRunner

from soul_protocol.cli.main import cli


def test_version():
    """--version flag prints the version string."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    from soul_protocol import __version__

    assert __version__ in result.output


def test_birth_command(tmp_path):
    """birth command creates a .soul file with expected output."""
    runner = CliRunner()
    output_path = str(tmp_path / "test-soul.soul")

    result = runner.invoke(cli, ["birth", "TestBot", "-o", output_path])

    assert result.exit_code == 0
    assert "Birthed" in result.output
    assert "TestBot" in result.output
    assert os.path.exists(output_path)


def test_inspect_command(tmp_path):
    """inspect command displays soul details from a .soul file."""
    runner = CliRunner()
    soul_path = str(tmp_path / "inspect-test.soul")

    # First birth a soul to get a file
    runner.invoke(cli, ["birth", "Inspector", "-o", soul_path])

    result = runner.invoke(cli, ["inspect", soul_path])

    assert result.exit_code == 0
    assert "Inspector" in result.output
    assert "did:soul:" in result.output


def test_status_command(tmp_path):
    """status command shows the soul's current mood and energy."""
    runner = CliRunner()
    soul_path = str(tmp_path / "status-test.soul")

    # First birth a soul
    runner.invoke(cli, ["birth", "StatusBot", "-o", soul_path])

    result = runner.invoke(cli, ["status", soul_path])

    assert result.exit_code == 0
    assert "StatusBot" in result.output
    assert "neutral" in result.output.lower() or "Soul Status" in result.output
