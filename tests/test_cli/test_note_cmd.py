# tests/test_cli/test_note_cmd.py
# Created: 2026-05-06 (#231) — End-to-end CLI coverage for the new
# `soul note` command. Each test runs Click via CliRunner against a freshly
# birthed soul on disk, verifies exit codes + output panels, and reloads the
# soul programmatically to confirm the SKIP / MERGE / CREATE decision was
# persisted to disk. The smoke test at the bottom (test_smoke_no_duplicates_
# from_repeated_notes) is the captain's actual problem from #231 — running
# `soul note` twice with identical text must leave exactly one semantic
# memory in the store.
#
# CLI command lives at src/soul_protocol/cli/main.py (registered as
# "note" — not "observe", which is the cognitive pipeline command).

from __future__ import annotations

import asyncio

import pytest
from click.testing import CliRunner

from soul_protocol.cli.main import cli


def _birth_soul_at(path: str, name: str = "Aria") -> None:
    """Birth a soul at PATH using the CLI."""
    runner = CliRunner()
    result = runner.invoke(cli, ["birth", name, "-o", path])
    assert result.exit_code == 0, result.output


# --- Smoke registration check ------------------------------------------------


def test_note_command_is_registered_under_the_name_note():
    """The new command is registered as `soul note`, not `soul observe`."""
    assert "note" in cli.commands, (
        "Expected `soul note` to be registered. The implementation was "
        "renamed from `observe` because the existing cognitive pipeline "
        "command owns that name (#231)."
    )


# --- E2E CREATE / SKIP / MERGE -----------------------------------------------


def test_e2e_create_first_note_panel_shows_created(tmp_path):
    """First invocation against a fresh soul: exit 0, panel says CREATED."""
    soul_path = tmp_path / "create.soul"
    _birth_soul_at(str(soul_path))

    runner = CliRunner()
    result = runner.invoke(cli, ["note", str(soul_path), "user prefers dark mode"])

    assert result.exit_code == 0, result.output
    out = result.output.lower()
    assert "create" in out, result.output


def test_e2e_skip_second_invocation_with_same_text(tmp_path):
    """Second identical note: panel says SKIPPED and shows similarity."""
    soul_path = tmp_path / "skip.soul"
    _birth_soul_at(str(soul_path))

    runner = CliRunner()
    first = runner.invoke(cli, ["note", str(soul_path), "user prefers dark mode"])
    assert first.exit_code == 0, first.output

    second = runner.invoke(cli, ["note", str(soul_path), "user prefers dark mode"])

    assert second.exit_code == 0, second.output
    out = second.output.lower()
    assert "skip" in out, second.output
    # Similarity line should be rendered (formatted to 2dp).
    assert "similarity" in out, second.output


def test_e2e_merge_overlapping_content(tmp_path):
    """Enriched superset content lands in MERGE band; panel shows MERGED + ID."""
    soul_path = tmp_path / "merge.soul"
    _birth_soul_at(str(soul_path))

    runner = CliRunner()
    first = runner.invoke(cli, ["note", str(soul_path), "Aria likes Python"])
    assert first.exit_code == 0, first.output

    second = runner.invoke(cli, ["note", str(soul_path), "Aria likes Python and async code"])

    assert second.exit_code == 0, second.output
    out = second.output.lower()
    assert "merge" in out, second.output
    # MERGE panel should reference the existing entry being superseded.
    assert "existing" in out, second.output


def test_e2e_no_dedup_writes_both(tmp_path):
    """--no-dedup bypasses the pipeline; both invocations report CREATED."""
    soul_path = tmp_path / "nodedup.soul"
    _birth_soul_at(str(soul_path))

    runner = CliRunner()
    first = runner.invoke(cli, ["note", str(soul_path), "always store this raw", "--no-dedup"])
    second = runner.invoke(cli, ["note", str(soul_path), "always store this raw", "--no-dedup"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "create" in first.output.lower(), first.output
    assert "create" in second.output.lower(), second.output

    # Reload the soul and confirm two semantic entries on disk.
    from soul_protocol.runtime.soul import Soul

    async def _count() -> int:
        soul = await Soul.awaken(str(soul_path))
        return len(soul._memory._semantic.facts())

    assert asyncio.run(_count()) == 2


# --- Smoke: the captain's actual problem -------------------------------------


def test_smoke_no_duplicates_from_repeated_notes(tmp_path):
    """Repeated `soul note <path> <text>` must not accumulate duplicates.

    This is the smoke test for #231 — `soul remember` did append a fresh
    entry on every call, which is why `soul-sync.sh` souls grew unbounded.
    The new `soul note` routes through the dedup pipeline; calling it
    twice with the same content collapses the second write into SKIP.
    """
    soul_path = tmp_path / "smoke.soul"
    _birth_soul_at(str(soul_path), "SmokeAria")

    runner = CliRunner()
    runner.invoke(cli, ["note", str(soul_path), "user prefers dark mode"])
    runner.invoke(cli, ["note", str(soul_path), "user prefers dark mode"])

    # Reload from disk and confirm the dedup persisted.
    from soul_protocol.runtime.soul import Soul

    async def _check() -> tuple[int, int]:
        soul = await Soul.awaken(str(soul_path))
        visible = soul._memory._semantic.facts()  # excludes superseded
        all_entries = soul._memory._semantic.facts(include_superseded=True)
        return len(visible), len(all_entries)

    visible_count, total_count = asyncio.run(_check())

    # The fix: exactly one *visible* (non-superseded) semantic memory.
    # Total may equal 1 (SKIP path — second write rejected outright)
    # or 2 if a future refactor moves identical-text dedup through MERGE
    # (which would supersede the first). Either is correct from the
    # caller's perspective — the recall surface should show one.
    assert visible_count == 1, (
        f"Expected exactly one visible semantic memory after two identical "
        f"`soul note` calls; got {visible_count} visible / {total_count} total."
    )


# --- Help text smoke ---------------------------------------------------------


def test_note_help_mentions_dedup_and_no_dedup_flag():
    """`soul note --help` should describe the dedup behaviour and the flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["note", "--help"])

    assert result.exit_code == 0, result.output
    assert "dedup" in result.output.lower()
    assert "--no-dedup" in result.output


@pytest.mark.parametrize(
    "memory_type",
    ["semantic", "episodic", "procedural", "social"],
)
def test_note_accepts_all_memory_tiers(tmp_path, memory_type):
    """All four tiers should be accepted by --type without error."""
    soul_path = tmp_path / f"tier-{memory_type}.soul"
    _birth_soul_at(str(soul_path), name=f"Tier{memory_type.title()}")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["note", str(soul_path), f"sample {memory_type} content", "--type", memory_type],
    )

    assert result.exit_code == 0, result.output
