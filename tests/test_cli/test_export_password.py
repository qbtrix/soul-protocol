# test_export_password.py — Tests for `soul export --password` (Phase 2).
# Verifies AES-256-GCM encryption is correctly wired through the CLI,
# and that passwords are securely prompted (not passed inline).

from __future__ import annotations

import json
import os
import zipfile

import pytest
from click.testing import CliRunner

from soul_protocol.cli.main import cli


def _birth(runner, tmp_path, name="EncryptTest"):
    """Create a soul and return the .soul path."""
    output_path = str(tmp_path / f"{name}.soul")
    result = runner.invoke(cli, ["birth", name, "-o", output_path])
    assert result.exit_code == 0, result.output
    assert os.path.exists(output_path)
    return output_path


class TestExportPassword:
    """Tests for the --password encryption option."""

    def test_encrypted_export_creates_enc_files(self, tmp_path):
        """Encrypted export should have .enc extension on files."""
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "encrypted.soul")
        result = runner.invoke(
            cli,
            ["export", soul_path, "-o", out_path, "--password"],
            input="testpass123\ntestpass123\n",
        )
        assert result.exit_code == 0

        with zipfile.ZipFile(out_path) as zf:
            names = zf.namelist()
            # soul.json should be encrypted as soul.json.enc
            assert any(n.endswith(".enc") for n in names), f"No encrypted files found: {names}"

    def test_encrypted_export_manifest_unencrypted(self, tmp_path):
        """Manifest should remain unencrypted and readable."""
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "encrypted.soul")
        result = runner.invoke(
            cli,
            ["export", soul_path, "-o", out_path, "--password"],
            input="testpass123\ntestpass123\n",
        )
        assert result.exit_code == 0

        with zipfile.ZipFile(out_path) as zf:
            names = zf.namelist()
            # manifest.json should NOT have .enc
            assert "manifest.json" in names, f"manifest.json missing: {names}"
            assert "manifest.json.enc" not in names

            # manifest should be valid JSON with encrypted=true
            manifest = json.loads(zf.read("manifest.json"))
            assert manifest["encrypted"] is True

    def test_encrypted_export_shows_notice(self, tmp_path):
        """Encrypted export should print encryption notice."""
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "encrypted.soul")
        result = runner.invoke(
            cli,
            ["export", soul_path, "-o", out_path, "--password"],
            input="testpass123\ntestpass123\n",
        )
        assert result.exit_code == 0
        assert "AES-256-GCM" in result.output

    def test_password_mismatched_confirmation(self, tmp_path):
        """Export should fail if password and confirmation do not match."""
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "encrypted.soul")
        result = runner.invoke(
            cli,
            ["export", soul_path, "-o", out_path, "--password"],
            input="testpass123\nwrongpass\n",
        )
        assert result.exit_code != 0
        assert "Error: The two entered values do not match." in result.output
        assert not os.path.exists(out_path)

    def test_unencrypted_export_no_enc_files(self, tmp_path):
        """Export without --password should not have .enc files."""
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "plain.soul")
        result = runner.invoke(cli, ["export", soul_path, "-o", out_path])
        assert result.exit_code == 0

        with zipfile.ZipFile(out_path) as zf:
            names = zf.namelist()
            assert not any(n.endswith(".enc") for n in names), (
                f"Found .enc files in unencrypted export: {names}"
            )

    def test_unencrypted_manifest_not_encrypted(self, tmp_path):
        """Unencrypted export manifest should have encrypted=false."""
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "plain.soul")
        result = runner.invoke(cli, ["export", soul_path, "-o", out_path])
        assert result.exit_code == 0

        with zipfile.ZipFile(out_path) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            assert manifest["encrypted"] is False

    def test_password_ignored_for_non_soul_format(self, tmp_path):
        """--password with --format json should show warning."""
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "output.json")
        result = runner.invoke(
            cli,
            ["export", soul_path, "-o", out_path, "-f", "json", "--password"],
            input="testpass123\ntestpass123\n",
        )
        assert result.exit_code == 0
        assert "Warning" in result.output


class TestExportPasswordRoundTrip:
    """Tests for encrypted export/awaken round-trip."""

    def test_awaken_with_correct_password(self, tmp_path):
        """Soul exported with password can be awakened with same password."""
        import asyncio

        from soul_protocol.runtime.soul import Soul

        async def _test():
            soul = await Soul.birth("RoundTrip")
            await soul.remember("Secret memory", importance=9)
            path = str(tmp_path / "encrypted.soul")
            await soul.export(path, password="mysecret")

            # Awaken with correct password
            restored = await Soul.awaken(path, password="mysecret")
            assert restored.name == "RoundTrip"

        asyncio.run(_test())

    def test_awaken_with_wrong_password_fails(self, tmp_path):
        """Soul exported with password fails with wrong password."""
        import asyncio

        from soul_protocol.runtime.exceptions import SoulDecryptionError
        from soul_protocol.runtime.soul import Soul

        async def _test():
            soul = await Soul.birth("WrongPass")
            path = str(tmp_path / "encrypted.soul")
            await soul.export(path, password="correct")

            with pytest.raises((SoulDecryptionError, ValueError)):
                await Soul.awaken(path, password="wrong")

        asyncio.run(_test())
