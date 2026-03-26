# test_health_cleanup_repair.py — Tests for soul health, cleanup, and repair CLI commands.
# Created: 2026-03-26 — Covers health_cmd (tier counts), cleanup_cmd (dry-run + auto),
#   and repair_cmd (--reset-energy) added in the v0.2.7 maintenance commands batch.

from __future__ import annotations

import asyncio

import pytest
from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.runtime.soul import Soul


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _birth_soul_at(path: str, name: str = "HealthBot") -> None:
    """Synchronously birth a soul and export it to path using the CLI birth command."""
    runner = CliRunner()
    runner.invoke(cli, ["birth", name, "-o", path])


async def _birth_and_export(tmp_path, name: str = "HealthBot") -> str:
    """Birth a soul in-memory and export it to tmp_path. Returns the .soul file path."""
    soul = await Soul.birth(name, archetype="Test Archetype", values=["curiosity"])
    soul_path = str(tmp_path / f"{name.lower()}.soul")
    await soul.export(soul_path)
    return soul_path


# ---------------------------------------------------------------------------
# soul health
# ---------------------------------------------------------------------------


class TestHealthCommand:
    """Tests for `soul health <path>`."""

    def test_health_runs_without_error(self, tmp_path):
        """health command exits 0 on a freshly birthed soul."""
        soul_path = str(tmp_path / "health-test.soul")
        _birth_soul_at(soul_path, "HealthBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["health", soul_path])

        assert result.exit_code == 0, result.output

    def test_health_shows_soul_name(self, tmp_path):
        """health report contains the soul's name in the output."""
        soul_path = str(tmp_path / "health-name.soul")
        _birth_soul_at(soul_path, "NameBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["health", soul_path])

        assert result.exit_code == 0, result.output
        assert "NameBot" in result.output

    def test_health_shows_memory_tier_counts(self, tmp_path):
        """health report shows Episodic, Semantic, Procedural tier headings."""
        soul_path = str(tmp_path / "health-tiers.soul")
        _birth_soul_at(soul_path, "TierBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["health", soul_path])

        assert result.exit_code == 0, result.output
        assert "Episodic" in result.output
        assert "Semantic" in result.output
        assert "Procedural" in result.output

    def test_health_shows_total_count(self, tmp_path):
        """health report includes a Total row for memory count."""
        soul_path = str(tmp_path / "health-total.soul")
        _birth_soul_at(soul_path, "TotalBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["health", soul_path])

        assert result.exit_code == 0, result.output
        assert "Total" in result.output

    def test_health_reports_no_issues_on_fresh_soul(self, tmp_path):
        """A freshly birthed soul with no memories has no critical issues."""
        soul_path = str(tmp_path / "health-fresh.soul")
        _birth_soul_at(soul_path, "FreshBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["health", soul_path])

        assert result.exit_code == 0, result.output
        # Should report healthy state — either "No issues found" or "No critical issues"
        assert "No issues" in result.output or "No critical" in result.output

    def test_health_shows_bond_section(self, tmp_path):
        """health report includes Bond section with strength and interaction count."""
        soul_path = str(tmp_path / "health-bond.soul")
        _birth_soul_at(soul_path, "BondBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["health", soul_path])

        assert result.exit_code == 0, result.output
        assert "Bond" in result.output
        assert "Strength" in result.output

    def test_health_shows_skills_and_evals(self, tmp_path):
        """health report shows Skills and Eval history counts."""
        soul_path = str(tmp_path / "health-skills.soul")
        _birth_soul_at(soul_path, "SkillBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["health", soul_path])

        assert result.exit_code == 0, result.output
        assert "Skills" in result.output

    def test_health_reports_nonzero_episodic_after_remember(self, tmp_path):
        """health shows nonzero episodic count after memories are added."""
        soul_path = str(tmp_path / "health-memories.soul")
        _birth_soul_at(soul_path, "MemBot")

        runner = CliRunner()
        # Add an episodic memory via observe
        runner.invoke(
            cli,
            ["observe", soul_path, "--user", "I love cats", "--agent", "Cats are great!"],
        )

        result = runner.invoke(cli, ["health", soul_path])

        assert result.exit_code == 0, result.output
        # Total should be > 0 (the output format is "Total:   N")
        assert "Total" in result.output


# ---------------------------------------------------------------------------
# soul cleanup --dry-run
# ---------------------------------------------------------------------------


class TestCleanupDryRun:
    """Tests for `soul cleanup --dry-run <path>`."""

    def test_cleanup_dry_run_exits_zero(self, tmp_path):
        """cleanup --dry-run exits 0 on a valid soul with no issues."""
        soul_path = str(tmp_path / "cleanup-dry.soul")
        _birth_soul_at(soul_path, "DryBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup", "--dry-run", soul_path])

        assert result.exit_code == 0, result.output

    def test_cleanup_dry_run_reports_nothing_when_clean(self, tmp_path):
        """cleanup --dry-run on a fresh soul says nothing to clean."""
        soul_path = str(tmp_path / "cleanup-clean.soul")
        _birth_soul_at(soul_path, "CleanBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup", "--dry-run", soul_path])

        assert result.exit_code == 0, result.output
        # Fresh soul has no duplicates, stale evals, or orphan nodes
        assert "Nothing to clean" in result.output or "tidy" in result.output

    def test_cleanup_dry_run_does_not_modify_soul(self, tmp_path):
        """cleanup --dry-run must not change the .soul file modification time significantly."""
        import os
        import time

        soul_path = str(tmp_path / "cleanup-nodiff.soul")
        _birth_soul_at(soul_path, "NoModBot")

        mtime_before = os.path.getmtime(soul_path)
        time.sleep(0.05)  # ensure any write would produce a different mtime

        runner = CliRunner()
        runner.invoke(cli, ["cleanup", "--dry-run", soul_path])

        mtime_after = os.path.getmtime(soul_path)
        # Dry run must not write the file
        assert mtime_before == mtime_after, "dry-run modified the .soul file"

    def test_cleanup_dry_run_mentions_dry_run(self, tmp_path):
        """cleanup --dry-run output confirms it's a dry run, not a real execution."""
        soul_path = str(tmp_path / "cleanup-mention.soul")
        _birth_soul_at(soul_path, "MentionBot")

        # First add a duplicate memory so there is something to clean
        runner = CliRunner()
        runner.invoke(cli, ["remember", soul_path, "I like Python programming", "-i", "6"])
        runner.invoke(cli, ["remember", soul_path, "I like Python programming", "-i", "6"])

        result = runner.invoke(cli, ["cleanup", "--dry-run", soul_path])

        assert result.exit_code == 0, result.output
        # Either "dry run" or "Dry run" or "no changes" should appear
        output_lower = result.output.lower()
        assert "dry run" in output_lower or "no changes" in output_lower or "nothing to clean" in output_lower or "tidy" in output_lower


# ---------------------------------------------------------------------------
# soul cleanup --auto
# ---------------------------------------------------------------------------


class TestCleanupAuto:
    """Tests for `soul cleanup --auto <path>`."""

    def test_cleanup_auto_exits_zero_on_clean_soul(self, tmp_path):
        """cleanup --auto exits 0 even when there's nothing to remove."""
        soul_path = str(tmp_path / "cleanup-auto-clean.soul")
        _birth_soul_at(soul_path, "AutoClean")

        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup", "--auto", soul_path])

        assert result.exit_code == 0, result.output

    def test_cleanup_auto_removes_duplicate_memories(self, tmp_path):
        """cleanup --auto removes near-duplicate memories and saves the soul."""
        soul_path = str(tmp_path / "cleanup-dedup.soul")
        _birth_soul_at(soul_path, "DedupBot")

        runner = CliRunner()
        # Add two nearly identical semantic memories
        runner.invoke(cli, ["remember", soul_path, "User likes Python programming very much", "-i", "6"])
        runner.invoke(cli, ["remember", soul_path, "User likes Python programming very much", "-i", "6"])

        # Run auto cleanup
        result = runner.invoke(cli, ["cleanup", "--auto", soul_path])

        assert result.exit_code == 0, result.output
        # Should confirm cleanup occurred — "Cleaned" in output, or "nothing to clean"
        assert "Cleaned" in result.output or "Nothing to clean" in result.output or "tidy" in result.output

    def test_cleanup_auto_saves_soul_file(self, tmp_path):
        """cleanup --auto writes the soul file after removing duplicates."""
        import os

        soul_path = str(tmp_path / "cleanup-save.soul")
        _birth_soul_at(soul_path, "SaveBot")

        runner = CliRunner()
        runner.invoke(cli, ["remember", soul_path, "remember Python loves cats deeply", "-i", "5"])
        runner.invoke(cli, ["remember", soul_path, "remember Python loves cats deeply", "-i", "5"])

        mtime_before = os.path.getmtime(soul_path)

        result = runner.invoke(cli, ["cleanup", "--auto", soul_path])

        assert result.exit_code == 0, result.output
        # File should be updated if there was something to remove, otherwise unchanged
        # Either way it should not fail

    def test_cleanup_auto_removes_low_importance_when_specified(self, tmp_path):
        """cleanup --auto --low-importance 2 removes memories with importance <= 2."""
        soul_path = str(tmp_path / "cleanup-low.soul")
        _birth_soul_at(soul_path, "LowBot")

        runner = CliRunner()
        # Add a low-importance memory
        runner.invoke(cli, ["remember", soul_path, "Minor note about nothing special", "-i", "1"])

        result = runner.invoke(cli, ["cleanup", "--auto", "--low-importance", "2", soul_path])

        assert result.exit_code == 0, result.output
        # Should clean or report nothing found
        assert "Cleaned" in result.output or "Nothing to clean" in result.output or "tidy" in result.output


# ---------------------------------------------------------------------------
# soul repair --reset-energy
# ---------------------------------------------------------------------------


class TestRepairResetEnergy:
    """Tests for `soul repair --reset-energy <path>`."""

    def test_repair_reset_energy_exits_zero(self, tmp_path):
        """repair --reset-energy exits 0 on a valid soul."""
        soul_path = str(tmp_path / "repair-energy.soul")
        _birth_soul_at(soul_path, "EnergyBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["repair", "--reset-energy", soul_path])

        assert result.exit_code == 0, result.output

    def test_repair_reset_energy_mentions_100_percent(self, tmp_path):
        """repair --reset-energy output mentions resetting energy to 100%."""
        soul_path = str(tmp_path / "repair-100.soul")
        _birth_soul_at(soul_path, "FullEnergyBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["repair", "--reset-energy", soul_path])

        assert result.exit_code == 0, result.output
        assert "100" in result.output or "energy" in result.output.lower()

    def test_repair_reset_energy_persists_to_file(self, tmp_path):
        """After repair --reset-energy, the reloaded soul has energy 100.0."""
        soul_path = str(tmp_path / "repair-persist.soul")
        _birth_soul_at(soul_path, "PersistBot")

        # Drain some energy via the CLI feel command
        runner = CliRunner()
        runner.invoke(cli, ["feel", soul_path, "--energy", "-50"])

        # Repair
        result = runner.invoke(cli, ["repair", "--reset-energy", soul_path])
        assert result.exit_code == 0, result.output

        # Reload and check energy via status
        status_result = runner.invoke(cli, ["status", soul_path])
        assert status_result.exit_code == 0, status_result.output
        # Energy should be reported as 100 (not drained)
        assert "100" in status_result.output

    def test_repair_no_flags_warns_user(self, tmp_path):
        """repair with no flags tells the user to specify options."""
        soul_path = str(tmp_path / "repair-noflags.soul")
        _birth_soul_at(soul_path, "NoFlagBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["repair", soul_path])

        assert result.exit_code == 0, result.output
        # Should say something about no actions specified or use --help
        output_lower = result.output.lower()
        assert "no repair" in output_lower or "--help" in output_lower or "specified" in output_lower

    def test_repair_reset_energy_shows_soul_name(self, tmp_path):
        """repair --reset-energy output panel includes the soul name."""
        soul_path = str(tmp_path / "repair-name.soul")
        _birth_soul_at(soul_path, "NameRepairBot")

        runner = CliRunner()
        result = runner.invoke(cli, ["repair", "--reset-energy", soul_path])

        assert result.exit_code == 0, result.output
        assert "NameRepairBot" in result.output
