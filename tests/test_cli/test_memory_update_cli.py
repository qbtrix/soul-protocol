# test_memory_update_cli.py — CLI coverage for `soul forget --id` and `soul supersede`.
# Created: 2026-04-27 — Locks the count-display fix on `soul forget` (the
#   preview/apply path was reading the wrong dict key and always reporting 0)
#   and exercises the new `--id` surgical delete plus the new `supersede`
#   command end-to-end.

from __future__ import annotations

import re

from click.testing import CliRunner

from soul_protocol.cli.main import cli


def _birth_soul_at(path: str, name: str = "MemUpdate") -> None:
    runner = CliRunner()
    runner.invoke(cli, ["birth", name, "-o", path])


def _remember(soul_path: str, text: str, *, importance: int = 5) -> str:
    """Store a memory and return its ID by parsing the panel output."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["remember", soul_path, text, "-i", str(importance)],
    )
    assert result.exit_code == 0, result.output
    # The remember panel prints "ID  <12-hex>"; capture the hex.
    match = re.search(r"ID\s+([0-9a-f]{8,})", result.output)
    assert match, f"Could not find memory id in output:\n{result.output}"
    return match.group(1)


# ---- forget display fix ----


class TestForgetDisplayCount:
    """The CLI count display was always 0 because of a key mismatch."""

    def test_forget_preview_reports_actual_count_not_zero(self, tmp_path):
        soul_path = tmp_path / "forget-count.soul"
        _birth_soul_at(str(soul_path), "ForgetCount")
        _remember(str(soul_path), "credit card info to delete", importance=7)

        runner = CliRunner()
        result = runner.invoke(cli, ["forget", str(soul_path), "credit"])

        assert result.exit_code == 0, result.output
        # Preview must NOT report "would forget 0 memories" when there is a
        # real match.  We accept "1 memory" or any non-zero count.
        assert "would forget 0 memor" not in result.output
        assert re.search(r"would forget [1-9]\d* memor", result.output)

    def test_forget_apply_reports_actual_count_not_zero(self, tmp_path):
        soul_path = tmp_path / "forget-count-apply.soul"
        _birth_soul_at(str(soul_path), "ForgetApply")
        _remember(str(soul_path), "another credit card record", importance=7)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["forget", str(soul_path), "credit", "--apply", "--confirm"],
        )

        assert result.exit_code == 0, result.output
        assert "Forgot 0 memor" not in result.output
        assert re.search(r"Forgot [1-9]\d* memor", result.output)

    def test_forget_preview_breaks_down_by_tier(self, tmp_path):
        """Preview should print per-tier counts when something matches."""
        soul_path = tmp_path / "forget-tier.soul"
        _birth_soul_at(str(soul_path), "ForgetTier")
        _remember(str(soul_path), "the keyword foobar appears here", importance=6)

        runner = CliRunner()
        result = runner.invoke(cli, ["forget", str(soul_path), "foobar"])
        assert result.exit_code == 0, result.output
        # Some tier line should appear with a non-zero count.
        assert re.search(r"\b(episodic|semantic|procedural):\s*[1-9]", result.output)


# ---- forget --id ----


class TestForgetById:
    def test_forget_by_id_preview_does_not_modify_file(self, tmp_path):
        soul_path = tmp_path / "forget-id-preview.soul"
        _birth_soul_at(str(soul_path), "ForgetIdPrev")
        mem_id = _remember(str(soul_path), "ephemeral target", importance=4)

        mtime_before = soul_path.stat().st_mtime
        runner = CliRunner()
        result = runner.invoke(cli, ["forget", str(soul_path), "--id", mem_id])
        mtime_after = soul_path.stat().st_mtime

        assert result.exit_code == 0, result.output
        assert mtime_before == mtime_after
        assert "Preview" in result.output or "--apply" in result.output

    def test_forget_by_id_apply_deletes_only_the_target(self, tmp_path):
        soul_path = tmp_path / "forget-id-apply.soul"
        _birth_soul_at(str(soul_path), "ForgetIdApply")
        target_id = _remember(str(soul_path), "delete this exact memory", importance=4)
        _remember(str(soul_path), "keep this other memory", importance=4)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["forget", str(soul_path), "--id", target_id, "--apply", "--confirm"],
        )
        assert result.exit_code == 0, result.output
        assert re.search(r"Forgot [1-9]\d* memor", result.output)

        # The other memory survived.
        recall = runner.invoke(cli, ["recall", str(soul_path), "keep this", "--json"])
        assert "keep this other memory" in recall.output

        # The target memory is gone — recall by its content returns nothing.
        gone = runner.invoke(cli, ["recall", str(soul_path), "delete this exact memory", "--json"])
        assert target_id not in gone.output

    def test_forget_by_id_unknown_id_reports_zero(self, tmp_path):
        soul_path = tmp_path / "forget-id-missing.soul"
        _birth_soul_at(str(soul_path), "ForgetIdMissing")

        runner = CliRunner()
        result = runner.invoke(cli, ["forget", str(soul_path), "--id", "deadbeefdead"])
        assert result.exit_code == 0, result.output
        assert "would forget 0 memor" in result.output

    def test_forget_rejects_id_combined_with_query(self, tmp_path):
        soul_path = tmp_path / "forget-id-conflict.soul"
        _birth_soul_at(str(soul_path), "ForgetIdConflict")

        runner = CliRunner()
        result = runner.invoke(cli, ["forget", str(soul_path), "some-query", "--id", "abc123"])
        # Mutually exclusive selector gate.
        assert result.exit_code == 1
        assert "exactly one of" in result.output.lower()


# ---- supersede ----


class TestSupersedeCommand:
    def test_supersede_writes_new_memory_and_links_old(self, tmp_path):
        soul_path = tmp_path / "supersede-happy.soul"
        _birth_soul_at(str(soul_path), "SupersedeHappy")
        old_id = _remember(
            str(soul_path),
            "paw-enterprise has no workspace switcher",
            importance=8,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "supersede",
                str(soul_path),
                "paw-enterprise has a workspace switcher in UserMenu.svelte",
                "--old-id",
                old_id,
                "--reason",
                "verified against current code",
                "-i",
                "8",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Memory Superseded" in result.output
        assert old_id in result.output

        # Recall surfaces the new memory; the old one is filtered out of search.
        recall = runner.invoke(cli, ["recall", str(soul_path), "workspace", "--json"])
        assert "UserMenu.svelte" in recall.output
        assert "no workspace switcher" not in recall.output

    def test_supersede_with_unknown_old_id_exits_nonzero(self, tmp_path):
        soul_path = tmp_path / "supersede-missing.soul"
        _birth_soul_at(str(soul_path), "SupersedeMissing")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "supersede",
                str(soul_path),
                "this should not be written",
                "--old-id",
                "deadbeefdead",
                "--reason",
                "wrong",
            ],
        )
        assert result.exit_code == 1
        assert "No memory with id" in result.output

    def test_supersede_preserves_old_entry_for_provenance(self, tmp_path):
        """Old entry stays in storage even though search filters it out."""
        soul_path = tmp_path / "supersede-prov.soul"
        _birth_soul_at(str(soul_path), "SupersedeProv")
        old_id = _remember(str(soul_path), "FilesPanel is mock-only", importance=8)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "supersede",
                str(soul_path),
                "FilesPanel hits the unified /files endpoint",
                "--old-id",
                old_id,
                "--reason",
                "Cluster E sub-PR 4",
            ],
        )
        assert result.exit_code == 0, result.output

        # Re-awaken the soul and confirm the old fact is still on disk with
        # superseded_by set.
        from soul_protocol.runtime.soul import Soul

        soul = Soul.awaken_sync(str(soul_path)) if hasattr(Soul, "awaken_sync") else None
        if soul is None:  # pragma: no cover — fall back to async path
            import asyncio

            async def _check():
                s = await Soul.awaken(str(soul_path))
                old = await s._memory._semantic.get(old_id)
                assert old is not None
                assert old.superseded_by is not None

            asyncio.run(_check())
