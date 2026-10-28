# test_memory_primitives_cli.py — CLI coverage for the v0.5.0 update verbs.
# Created: 2026-04-29 (#192) — exercises the new commands end-to-end:
# soul confirm, soul update, soul purge, soul reinstate, soul upgrade.
# Plus the v0.5.0 semantic shift on soul forget --id (weight-decay).

from __future__ import annotations

import re

from click.testing import CliRunner

from soul_protocol.cli.main import cli


def _birth_soul_at(path: str, name: str = "MemPrim") -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["birth", name, "-o", path])
    assert result.exit_code == 0, result.output


def _remember(soul_path: str, text: str, *, importance: int = 6) -> str:
    runner = CliRunner()
    result = runner.invoke(cli, ["remember", soul_path, text, "-i", str(importance)])
    assert result.exit_code == 0, result.output
    match = re.search(r"ID\s+([0-9a-f]{8,})", result.output)
    assert match, result.output
    return match.group(1)


class TestConfirmCmd:
    def test_confirm_happy_path(self, tmp_path):
        soul_path = tmp_path / "confirm.soul"
        _birth_soul_at(str(soul_path), "Confirmer")
        mid = _remember(str(soul_path), "fact to confirm")
        runner = CliRunner()
        result = runner.invoke(cli, ["confirm", str(soul_path), mid])
        assert result.exit_code == 0, result.output
        assert "Memory Confirmed" in result.output

    def test_confirm_unknown_id_exits_nonzero(self, tmp_path):
        soul_path = tmp_path / "confirm-missing.soul"
        _birth_soul_at(str(soul_path), "ConfirmMissing")
        runner = CliRunner()
        result = runner.invoke(cli, ["confirm", str(soul_path), "deadbeefdead"])
        assert result.exit_code == 1


class TestUpdateCmd:
    def test_update_happy_path(self, tmp_path):
        soul_path = tmp_path / "update.soul"
        _birth_soul_at(str(soul_path), "Updater")
        mid = _remember(str(soul_path), "Atlas ships in May")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "update",
                str(soul_path),
                mid,
                "--patch",
                "Atlas ships in July",
                "--prediction-error",
                "0.4",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Memory Updated" in result.output

    def test_update_out_of_band_exits_nonzero(self, tmp_path):
        soul_path = tmp_path / "update-band.soul"
        _birth_soul_at(str(soul_path), "UpdaterBand")
        mid = _remember(str(soul_path), "fact")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["update", str(soul_path), mid, "--patch", "p", "--prediction-error", "0.9"],
        )
        assert result.exit_code == 1


class TestPurgeCmd:
    def test_purge_preview(self, tmp_path):
        soul_path = tmp_path / "purge-prev.soul"
        _birth_soul_at(str(soul_path), "PurgePrev")
        mid = _remember(str(soul_path), "destroy this")
        mtime_before = soul_path.stat().st_mtime
        runner = CliRunner()
        result = runner.invoke(cli, ["purge", str(soul_path), "--id", mid])
        assert result.exit_code == 0, result.output
        assert "would purge" in result.output.lower()
        assert mtime_before == soul_path.stat().st_mtime  # unchanged

    def test_purge_apply_removes_entry(self, tmp_path):
        soul_path = tmp_path / "purge-apply.soul"
        _birth_soul_at(str(soul_path), "PurgeApply")
        mid = _remember(str(soul_path), "destroy this")
        runner = CliRunner()
        result = runner.invoke(cli, ["purge", str(soul_path), "--id", mid, "--apply", "--confirm"])
        assert result.exit_code == 0, result.output
        assert "Purged" in result.output


class TestReinstateCmd:
    def test_reinstate_after_forget(self, tmp_path):
        soul_path = tmp_path / "reinstate.soul"
        _birth_soul_at(str(soul_path), "ReinstateMe")
        mid = _remember(str(soul_path), "fact to forget")
        # Forget via the existing CLI flow (semantics is now weight-decay)
        runner = CliRunner()
        forget_result = runner.invoke(
            cli, ["forget", str(soul_path), "--id", mid, "--apply", "--confirm"]
        )
        assert forget_result.exit_code == 0, forget_result.output
        # Reinstate
        result = runner.invoke(cli, ["reinstate", str(soul_path), mid])
        assert result.exit_code == 0, result.output
        assert "Memory Reinstated" in result.output


class TestUpgradeCmd:
    def test_upgrade_dry_run(self, tmp_path):
        soul_path = tmp_path / "upgrade.soul"
        _birth_soul_at(str(soul_path), "UpgradeMe")
        _remember(str(soul_path), "fact one")
        _remember(str(soul_path), "fact two")
        runner = CliRunner()
        result = runner.invoke(cli, ["upgrade", str(soul_path), "--to", "0.5.0", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "Migration Plan" in result.output
        assert "Dry run" in result.output

    def test_upgrade_apply(self, tmp_path):
        soul_path = tmp_path / "upgrade-apply.soul"
        _birth_soul_at(str(soul_path), "UpgradeApply")
        _remember(str(soul_path), "fact")
        runner = CliRunner()
        result = runner.invoke(cli, ["upgrade", str(soul_path), "--to", "0.5.0"])
        assert result.exit_code == 0, result.output
        assert "Migration Applied" in result.output


class TestForgetSemanticShift:
    def test_forget_id_keeps_entry_on_disk(self, tmp_path):
        """v0.5.0 — forget --id is no longer a hard delete."""
        soul_path = tmp_path / "forget-shift.soul"
        _birth_soul_at(str(soul_path), "ForgetShift")
        mid = _remember(str(soul_path), "weight-decayed not deleted")
        runner = CliRunner()
        result = runner.invoke(cli, ["forget", str(soul_path), "--id", mid, "--apply", "--confirm"])
        assert result.exit_code == 0, result.output
        # The entry should still be on disk — reinstate restores it.
        reinstate_result = runner.invoke(cli, ["reinstate", str(soul_path), mid])
        assert reinstate_result.exit_code == 0, reinstate_result.output
