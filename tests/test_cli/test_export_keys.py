# test_export_keys.py — Tests for the include_keys security fix (#273).
# Asserts that the default export does NOT include the private signing key,
# and that --include-keys explicitly adds it back.

from __future__ import annotations

import os
import zipfile

from click.testing import CliRunner

from soul_protocol.cli.main import cli


def _birth(runner, tmp_path, name="ExportTest"):
    """Create a soul and return the .soul path."""
    output_path = str(tmp_path / f"{name}.soul")
    result = runner.invoke(cli, ["birth", name, "-o", output_path])
    assert result.exit_code == 0, result.output
    assert os.path.exists(output_path)
    return output_path


class TestExportKeysDefault:
    """Default export should contain public.key but NOT private.key."""

    def test_default_export_has_public_key(self, tmp_path):
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        # Export without --include-keys
        out_path = str(tmp_path / "exported.soul")
        result = runner.invoke(cli, ["export", soul_path, "-o", out_path])
        assert result.exit_code == 0

        with zipfile.ZipFile(out_path) as zf:
            names = zf.namelist()
            assert any("public" in n for n in names), f"public key missing from export: {names}"

    def test_default_export_excludes_private_key(self, tmp_path):
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "exported.soul")
        result = runner.invoke(cli, ["export", soul_path, "-o", out_path])
        assert result.exit_code == 0

        with zipfile.ZipFile(out_path) as zf:
            names = zf.namelist()
            assert not any("private" in n for n in names), (
                f"private key leaked in default export: {names}"
            )

    def test_default_export_shows_notice(self, tmp_path):
        """Default export prints a notice about missing private key."""
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "exported.soul")
        result = runner.invoke(cli, ["export", soul_path, "-o", out_path])
        assert result.exit_code == 0
        assert "--include-keys" in result.output


class TestExportKeysIncluded:
    """--include-keys flag should add private.key back to the export."""

    def test_include_keys_has_private_key(self, tmp_path):
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "exported_with_keys.soul")
        result = runner.invoke(cli, ["export", soul_path, "-o", out_path, "--include-keys"])
        assert result.exit_code == 0

        with zipfile.ZipFile(out_path) as zf:
            names = zf.namelist()
            assert any("private" in n for n in names), (
                f"private key missing when --include-keys used: {names}"
            )

    def test_include_keys_has_public_key(self, tmp_path):
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "exported_with_keys.soul")
        result = runner.invoke(cli, ["export", soul_path, "-o", out_path, "--include-keys"])
        assert result.exit_code == 0

        with zipfile.ZipFile(out_path) as zf:
            names = zf.namelist()
            assert any("public" in n for n in names), (
                f"public key missing when --include-keys used: {names}"
            )

    def test_include_keys_no_notice(self, tmp_path):
        """--include-keys should NOT show the 'private key not included' notice."""
        runner = CliRunner()
        soul_path = _birth(runner, tmp_path)

        out_path = str(tmp_path / "exported_with_keys.soul")
        result = runner.invoke(cli, ["export", soul_path, "-o", out_path, "--include-keys"])
        assert result.exit_code == 0
        assert "not included" not in result.output
