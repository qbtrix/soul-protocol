# test_did_cli.py — Tests for the `soul did` CLI commands.
# Created: 2026-06-27 — Phase 1 of the DID CLI feature.
#   Tests for `soul did show` and `soul did verify` subcommands.

from __future__ import annotations

import asyncio
import json
import zipfile

import pytest
from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.runtime.soul import Soul


@pytest.fixture
def runner():
    """Provide a Click CliRunner for CLI tests."""
    return CliRunner()


@pytest.fixture
def soul_file(tmp_path):
    """Create a test .soul file and return its path."""

    async def _create():
        soul = await Soul.birth(name="TestDID", personality="A test soul")
        await soul.remember("User likes Python", importance=8)
        path = tmp_path / "test.soul"
        await soul.export(str(path), include_keys=True)
        return str(path)

    return asyncio.run(_create())


@pytest.fixture
def soul_file_no_keys(tmp_path):
    """Create a test .soul file without private keys."""

    async def _create():
        soul = await Soul.birth(name="VerifyOnly")
        path = tmp_path / "verify_only.soul"
        await soul.export(str(path), include_keys=False)
        return str(path)

    return asyncio.run(_create())


@pytest.fixture
def soul_file_with_chain(tmp_path):
    """Create a test .soul file with trust chain entries via observe()."""
    from soul_protocol.runtime.types import Interaction

    async def _create():
        soul = await Soul.birth(name="ChainTest", personality="A soul with history")
        # Use observe() to generate trust chain entries
        await soul.observe(
            Interaction(
                user_input="Hello there",
                agent_output="Hi! How can I help?",
                channel="test",
            )
        )
        await soul.observe(
            Interaction(
                user_input="Tell me about Python",
                agent_output="Python is great!",
                channel="test",
            )
        )
        path = tmp_path / "chain_test.soul"
        await soul.export(str(path), include_keys=True)
        return str(path)

    return asyncio.run(_create())


@pytest.fixture
def tampered_soul_file(tmp_path):
    """Create a .soul file with a tampered trust chain."""
    from soul_protocol.runtime.types import Interaction

    async def _create():
        soul = await Soul.birth(name="Tampered", personality="Will be tampered")
        await soul.observe(
            Interaction(
                user_input="First message",
                agent_output="First reply",
                channel="test",
            )
        )
        path = tmp_path / "tampered.soul"
        await soul.export(str(path), include_keys=True)

        # Tamper: modify a trust chain entry inside the zip
        tampered_path = tmp_path / "tampered_mod.soul"
        with zipfile.ZipFile(str(path), "r") as zin:
            with zipfile.ZipFile(str(tampered_path), "w") as zout:
                for item in zin.namelist():
                    data = zin.read(item)
                    if "trust" in item and item.endswith(".json"):
                        # Corrupt the trust chain data
                        chain_data = json.loads(data.decode("utf-8"))
                        if isinstance(chain_data, dict) and "entries" in chain_data:
                            for entry in chain_data["entries"]:
                                entry["payload_hash"] = "0" * 64  # corrupt
                            data = json.dumps(chain_data).encode("utf-8")
                        elif isinstance(chain_data, list) and len(chain_data) > 0:
                            chain_data[0]["payload_hash"] = "0" * 64
                            data = json.dumps(chain_data).encode("utf-8")
                    zout.writestr(item, data)

        return str(tampered_path)

    return asyncio.run(_create())


# ============ soul did show ============


class TestDidShow:
    """Tests for the `soul did show` command."""

    def test_show_displays_name(self, runner, soul_file):
        """show command displays the soul name."""
        result = runner.invoke(cli, ["did", "show", soul_file])
        assert result.exit_code == 0
        assert "TestDID" in result.output

    def test_show_displays_did(self, runner, soul_file):
        """show command displays the DID."""
        result = runner.invoke(cli, ["did", "show", soul_file])
        assert result.exit_code == 0
        assert "did:soul:testdid" in result.output

    def test_show_displays_algorithm(self, runner, soul_file):
        """show command displays Ed25519 algorithm."""
        result = runner.invoke(cli, ["did", "show", soul_file])
        assert result.exit_code == 0
        assert "Ed25519" in result.output

    def test_show_displays_public_key(self, runner, soul_file):
        """show command displays the public key."""
        result = runner.invoke(cli, ["did", "show", soul_file])
        assert result.exit_code == 0
        assert "Public Key" in result.output

    def test_show_private_key_present(self, runner, soul_file):
        """show command indicates private key is present."""
        result = runner.invoke(cli, ["did", "show", soul_file])
        assert result.exit_code == 0
        assert "present" in result.output

    def test_show_private_key_absent(self, runner, soul_file_no_keys):
        """show command indicates private key is absent."""
        result = runner.invoke(cli, ["did", "show", soul_file_no_keys])
        assert result.exit_code == 0
        assert "absent" in result.output

    def test_show_nonexistent_file(self, runner):
        """show command fails gracefully with nonexistent file."""
        result = runner.invoke(cli, ["did", "show", "nonexistent.soul"])
        assert result.exit_code != 0


# ============ soul did verify ============


class TestDidVerify:
    """Tests for the `soul did verify` command."""

    def test_verify_passes_valid_soul(self, runner, soul_file):
        """verify command passes for a valid soul file."""
        result = runner.invoke(cli, ["did", "verify", soul_file])
        assert result.exit_code == 0
        assert "DID format valid" in result.output
        assert "All checks passed" in result.output

    def test_verify_shows_public_key_status(self, runner, soul_file):
        """verify command shows public key is present."""
        result = runner.invoke(cli, ["did", "verify", soul_file])
        assert result.exit_code == 0
        assert "Public key present" in result.output

    def test_verify_no_keys_still_passes(self, runner, soul_file_no_keys):
        """verify command passes for soul without private keys."""
        result = runner.invoke(cli, ["did", "verify", soul_file_no_keys])
        assert result.exit_code == 0
        assert "DID format valid" in result.output

    def test_verify_verbose_flag(self, runner, soul_file):
        """verify --verbose doesn't crash."""
        result = runner.invoke(cli, ["did", "verify", soul_file, "--verbose"])
        assert result.exit_code == 0

    def test_verify_nonexistent_file(self, runner):
        """verify command fails gracefully with nonexistent file."""
        result = runner.invoke(cli, ["did", "verify", "nonexistent.soul"])
        assert result.exit_code != 0

    def test_verify_with_chain_passes(self, runner, soul_file_with_chain):
        """verify passes for a soul with trust chain entries."""
        result = runner.invoke(cli, ["did", "verify", soul_file_with_chain])
        assert result.exit_code == 0
        assert "All checks passed" in result.output

    def test_verify_verbose_with_chain(self, runner, soul_file_with_chain):
        """verify --verbose shows chain table for soul with entries."""
        result = runner.invoke(cli, ["did", "verify", soul_file_with_chain, "--verbose"])
        assert result.exit_code == 0
        # Should show the Trust Chain Entries table
        assert "Trust Chain" in result.output

    def test_verify_tampered_exits_nonzero(self, runner, tampered_soul_file):
        """verify exits 1 for a soul with a tampered trust chain."""
        result = runner.invoke(cli, ["did", "verify", tampered_soul_file])
        assert result.exit_code != 0
        assert "Verification failed" in result.output or "INVALID" in result.output


# ============ soul did (group) ============


class TestDidGroup:
    """Tests for the `soul did` command group."""

    def test_help(self, runner):
        """did --help shows usage info."""
        result = runner.invoke(cli, ["did", "--help"])
        assert result.exit_code == 0
        assert "show" in result.output
        assert "verify" in result.output
        assert "Decentralized Identifiers" in result.output

    def test_show_help(self, runner):
        """did show --help shows command help."""
        result = runner.invoke(cli, ["did", "show", "--help"])
        assert result.exit_code == 0
        assert "DID" in result.output

    def test_verify_help(self, runner):
        """did verify --help shows command help."""
        result = runner.invoke(cli, ["did", "verify", "--help"])
        assert result.exit_code == 0
        assert "trust chain" in result.output.lower()
