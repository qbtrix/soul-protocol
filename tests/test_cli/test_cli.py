# test_cli.py — Tests for the CLI interface using click.testing.CliRunner.
# Updated: 2026-03-13 — Added --format option tests for soul init (TDD: dir, zip, default).

from __future__ import annotations

import json
import os
import zipfile

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


def test_remember_command(tmp_path):
    """remember command stores a memory and confirms it."""
    runner = CliRunner()
    soul_path = str(tmp_path / "remember-test.soul")

    # Birth a soul first
    runner.invoke(cli, ["birth", "MemBot", "-o", soul_path])

    result = runner.invoke(
        cli, ["remember", soul_path, "User prefers dark mode", "-i", "7"]
    )

    assert result.exit_code == 0
    assert "Memory Stored" in result.output
    assert "User prefers dark mode" in result.output
    assert "7/10" in result.output


def test_remember_with_emotion(tmp_path):
    """remember command accepts an emotion tag."""
    runner = CliRunner()
    soul_path = str(tmp_path / "emotion-test.soul")

    runner.invoke(cli, ["birth", "EmoBot", "-o", soul_path])

    result = runner.invoke(
        cli, ["remember", soul_path, "Had a great conversation", "-e", "happy"]
    )

    assert result.exit_code == 0
    assert "happy" in result.output


def test_recall_with_query(tmp_path):
    """recall command searches memories by query."""
    runner = CliRunner()
    soul_path = str(tmp_path / "recall-test.soul")

    # Birth and store a memory
    runner.invoke(cli, ["birth", "RecallBot", "-o", soul_path])
    runner.invoke(cli, ["remember", soul_path, "User likes Python programming"])

    result = runner.invoke(cli, ["recall", soul_path, "Python"])

    assert result.exit_code == 0
    assert "Python" in result.output


def test_recall_recent(tmp_path):
    """recall --recent N shows the most recent memories."""
    runner = CliRunner()
    soul_path = str(tmp_path / "recent-test.soul")

    runner.invoke(cli, ["birth", "RecentBot", "-o", soul_path])
    runner.invoke(cli, ["remember", soul_path, "First memory"])
    runner.invoke(cli, ["remember", soul_path, "Second memory"])

    result = runner.invoke(cli, ["recall", soul_path, "--recent", "5"])

    # Should not error; may or may not find episodic memories
    # (remember stores semantic by default, --recent reads episodic)
    assert result.exit_code == 0


def test_recall_no_query_no_recent(tmp_path):
    """recall without query or --recent prints an error."""
    runner = CliRunner()
    soul_path = str(tmp_path / "noquery-test.soul")

    runner.invoke(cli, ["birth", "NoQueryBot", "-o", soul_path])

    result = runner.invoke(cli, ["recall", soul_path])

    assert result.exit_code != 0


def test_recall_empty_results(tmp_path):
    """recall on a fresh soul with no matches shows 'no memories' message."""
    runner = CliRunner()
    soul_path = str(tmp_path / "empty-test.soul")

    runner.invoke(cli, ["birth", "EmptyBot", "-o", soul_path])

    result = runner.invoke(cli, ["recall", soul_path, "xyznonexistent"])

    assert result.exit_code == 0
    assert "No memories found" in result.output


def test_init_setup_preserves_existing_soul(tmp_path, monkeypatch):
    """soul init --setup with existing soul loads it instead of overwriting."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    soul_dir = str(tmp_path / ".soul" / "testbot")
    soul_json_path = tmp_path / ".soul" / "testbot" / "soul.json"

    # First, create a soul via init
    result = runner.invoke(cli, ["init", "TestBot", "-d", soul_dir])
    assert result.exit_code == 0
    assert soul_json_path.exists()

    # Capture the DID before re-running
    before = json.loads(soul_json_path.read_text())

    # Now run init --setup on the same dir — should NOT overwrite
    result2 = runner.invoke(
        cli, ["init", "-d", soul_dir, "--setup", "claude-code"]
    )
    assert result2.exit_code == 0
    assert "Found" in result2.output and "TestBot" in result2.output

    # Verify soul identity was preserved (same DID, same name)
    after = json.loads(soul_json_path.read_text())
    assert before["identity"]["did"] == after["identity"]["did"]
    assert before["identity"]["name"] == after["identity"]["name"]

    # Verify .mcp.json was created (setup worked)
    assert (tmp_path / ".mcp.json").exists()


def test_init_format_dir(tmp_path):
    """soul init --format dir creates a directory with soul.json inside."""
    runner = CliRunner()
    soul_dir = str(tmp_path / ".soul" / "testbot")

    result = runner.invoke(cli, ["init", "TestBot", "--format", "dir", "-d", soul_dir])

    assert result.exit_code == 0, result.output
    soul_json = tmp_path / ".soul" / "testbot" / "soul.json"
    assert soul_json.exists(), f"soul.json not found at {soul_json}"
    assert (tmp_path / ".soul" / "testbot").is_dir()


def test_init_format_zip(tmp_path):
    """soul init --format zip creates a .soul ZIP file at <dir>.soul."""
    runner = CliRunner()
    soul_dir = str(tmp_path / ".soul" / "testbot")

    result = runner.invoke(cli, ["init", "TestBot", "--format", "zip", "-d", soul_dir])

    assert result.exit_code == 0, result.output
    # ZIP file should be at <soul_dir>.soul (appends .soul extension)
    zip_path = tmp_path / ".soul" / "testbot.soul"
    assert zip_path.exists(), f".soul zip not found at {zip_path}"
    assert zipfile.is_zipfile(zip_path), f"{zip_path} is not a valid ZIP archive"


def test_init_format_default_is_dir(tmp_path):
    """soul init without --format defaults to directory format (soul.json in dir)."""
    runner = CliRunner()
    soul_dir = str(tmp_path / ".soul" / "defaultbot")

    result = runner.invoke(cli, ["init", "TestBot", "-d", soul_dir])

    assert result.exit_code == 0, result.output
    soul_json = tmp_path / ".soul" / "defaultbot" / "soul.json"
    assert soul_json.exists(), f"soul.json not found at {soul_json} (default format should be dir)"
    assert (tmp_path / ".soul" / "defaultbot").is_dir()
