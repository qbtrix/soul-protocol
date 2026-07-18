# test_diff_cmd.py — Tests for `soul diff <left> <right>` (#191).
# Created: feat/soul-diff-cli — Covers identical souls, identity rename, new
#   memories, supersession (hidden by default + visible with --include-superseded),
#   bond strength changes, schema mismatch, --json round-trip, --markdown
#   output, --section narrowing, and --summary-only.

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.runtime.diff import SchemaMismatchError, diff_souls
from soul_protocol.runtime.soul import Soul

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_souls(tmp_path: Path) -> tuple[Path, Path]:
    """Birth one Aria soul, export it, then export it a second time as the
    'right' side. Identical content — diff should be empty by default."""

    async def _setup() -> tuple[Path, Path]:
        soul = await Soul.birth("Aria", archetype="The Compassionate Creator")
        left = tmp_path / "aria-left.soul"
        right = tmp_path / "aria-right.soul"
        await soul.export(str(left), include_keys=True)
        await soul.export(str(right), include_keys=True)
        return left, right

    return asyncio.run(_setup())


# ---------------------------------------------------------------------------
# Identical-souls path
# ---------------------------------------------------------------------------


def test_identical_souls_empty_diff(two_souls: tuple[Path, Path]) -> None:
    """Diffing a file against itself yields an empty diff (text mode says so)."""
    left, right = two_souls
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right)])
    assert result.exit_code == 0, result.output
    assert "no changes detected" in result.output.lower()


def test_identical_souls_json_has_empty_sections(two_souls: tuple[Path, Path]) -> None:
    """--json on identical souls emits a SoulDiff with empty sections."""
    left, right = two_souls
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["left_name"] == "Aria"
    assert payload["right_name"] == "Aria"
    assert payload["identity"]["changes"] == []
    assert payload["memory"]["added"] == []
    assert payload["memory"]["removed"] == []
    assert payload["memory"]["modified"] == []
    assert payload["skills"]["added"] == []


# ---------------------------------------------------------------------------
# Identity changes
# ---------------------------------------------------------------------------


def test_identity_rename_surfaces_in_identity_section(tmp_path: Path) -> None:
    """Renaming the soul shows up under the identity section."""

    async def _setup() -> tuple[Path, Path]:
        original = await Soul.birth("Aria", archetype="The Companion")
        left = tmp_path / "left.soul"
        await original.export(str(left), include_keys=True)

        renamed = await Soul.awaken(str(left))
        # The runtime exposes name via _identity; mutate then re-export.
        renamed._identity.name = "Sage"
        right = tmp_path / "right.soul"
        await renamed.export(str(right), include_keys=True)
        return left, right

    left, right = asyncio.run(_setup())
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    name_changes = [c for c in payload["identity"]["changes"] if c["field"] == "name"]
    assert len(name_changes) == 1
    assert name_changes[0]["before"] == "Aria"
    assert name_changes[0]["after"] == "Sage"


# ---------------------------------------------------------------------------
# Memory changes
# ---------------------------------------------------------------------------


def test_new_memory_appears_in_added_section(tmp_path: Path) -> None:
    """A memory present only on the right surfaces in memory.added."""

    async def _setup() -> tuple[Path, Path]:
        soul_a = await Soul.birth("Aria")
        left = tmp_path / "left.soul"
        await soul_a.export(str(left), include_keys=True)

        soul_b = await Soul.awaken(str(left))
        await soul_b.remember("I prefer Python over JavaScript", importance=7)
        right = tmp_path / "right.soul"
        await soul_b.export(str(right), include_keys=True)
        return left, right

    left, right = asyncio.run(_setup())
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["memory"]["added"]) == 1
    added = payload["memory"]["added"][0]
    assert "Python" in added["content"]
    assert added["importance"] == 7
    assert payload["memory"]["removed"] == []


def test_text_output_lists_added_memory_with_marker(tmp_path: Path) -> None:
    """The Rich text output prefixes added memories with `+`."""

    async def _setup() -> tuple[Path, Path]:
        soul_a = await Soul.birth("Aria")
        left = tmp_path / "left.soul"
        await soul_a.export(str(left), include_keys=True)

        soul_b = await Soul.awaken(str(left))
        await soul_b.remember("Distinctive memory text alpha", importance=5)
        right = tmp_path / "right.soul"
        await soul_b.export(str(right), include_keys=True)
        return left, right

    left, right = asyncio.run(_setup())
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right)])
    assert result.exit_code == 0, result.output
    assert "Distinctive memory text alpha" in result.output
    assert "+" in result.output  # added marker


def test_supersession_hidden_by_default(tmp_path: Path) -> None:
    """A memory marked superseded between left and right is hidden by default."""

    async def _setup() -> tuple[Path, Path]:
        soul = await Soul.birth("Aria")
        old_id = await soul.remember("Original fact about apples", importance=6)
        left = tmp_path / "left.soul"
        await soul.export(str(left), include_keys=True)

        # Supersede the old memory on the right side
        soul_b = await Soul.awaken(str(left))
        await soul_b.supersede(old_id, "Updated fact about apples", reason="clarification")
        right = tmp_path / "right.soul"
        await soul_b.export(str(right), include_keys=True)
        return left, right

    left, right = asyncio.run(_setup())
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # Default: superseded list is empty
    assert payload["memory"]["superseded"] == []


def test_supersession_visible_with_include_flag(tmp_path: Path) -> None:
    """--include-superseded surfaces the supersession chain explicitly."""

    async def _setup() -> tuple[Path, Path]:
        soul = await Soul.birth("Aria")
        old_id = await soul.remember("Original fact about apples", importance=6)
        left = tmp_path / "left.soul"
        await soul.export(str(left), include_keys=True)

        soul_b = await Soul.awaken(str(left))
        await soul_b.supersede(old_id, "Updated fact about apples", reason="clarification")
        right = tmp_path / "right.soul"
        await soul_b.export(str(right), include_keys=True)
        return left, right

    left, right = asyncio.run(_setup())
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right), "--include-superseded", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # Modified should include the superseded_by field change for old_id
    modified_old = [
        m
        for m in payload["memory"]["modified"]
        if any(c["field"] == "superseded_by" for c in m["field_changes"])
    ]
    assert modified_old, "expected at least one modified entry with superseded_by change"


# ---------------------------------------------------------------------------
# Bond changes
# ---------------------------------------------------------------------------


def test_bond_strength_change_appears_in_bond_section(tmp_path: Path) -> None:
    """A bond strength tweak shows up in the bond.changes list."""

    async def _setup() -> tuple[Path, Path]:
        soul_a = await Soul.birth("Aria")
        left = tmp_path / "left.soul"
        await soul_a.export(str(left), include_keys=True)

        soul_b = await Soul.awaken(str(left))
        soul_b.bond.strengthen(amount=10.0)
        right = tmp_path / "right.soul"
        await soul_b.export(str(right), include_keys=True)
        return left, right

    left, right = asyncio.run(_setup())
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["bond"]["changes"]) == 1
    change = payload["bond"]["changes"][0]
    assert change["strength_after"] > change["strength_before"]
    assert change["interaction_count_after"] > change["interaction_count_before"]


# ---------------------------------------------------------------------------
# Schema mismatch
# ---------------------------------------------------------------------------


def test_schema_mismatch_raises_clean_error(tmp_path: Path) -> None:
    """Different schema versions on the two souls error out with a clean message."""

    async def _setup() -> tuple[Path, Path]:
        soul_a = await Soul.birth("Aria")
        soul_b = await Soul.birth("Aria")
        left = tmp_path / "left.soul"
        right = tmp_path / "right.soul"
        await soul_a.export(str(left), include_keys=True)
        # Forcibly bump the right side's version on disk by re-exporting after
        # changing the in-memory config version. Using a temp path works
        # because Soul.export uses serialize() which respects _config.version
        # only as a fallback — actual version comes from serialize() default.
        # Easier path: monkey-patch serialize.
        await soul_b.export(str(right), include_keys=True)
        return left, right

    left, right = asyncio.run(_setup())

    # Use the diff_souls API directly to test the version path; the CLI
    # already exits non-zero on the same error.
    async def _verify_mismatch() -> None:
        soul_a = await Soul.awaken(str(left))
        soul_b = await Soul.awaken(str(right))
        # Force a version mismatch on the in-memory config object that
        # serialize() reads — this is the guard the diff exercises.
        soul_b._config.version = "9.9.9"
        with pytest.raises(SchemaMismatchError) as excinfo:
            diff_souls(soul_a, soul_b)
        assert "Schema version mismatch" in str(excinfo.value)
        assert "9.9.9" in str(excinfo.value)

    asyncio.run(_verify_mismatch())


# ---------------------------------------------------------------------------
# Format flags
# ---------------------------------------------------------------------------


def test_json_output_round_trips_through_json_loads(two_souls: tuple[Path, Path]) -> None:
    """--json output is parseable; --json shortcut equals --format json."""
    left, right = two_souls
    runner = CliRunner()

    r1 = runner.invoke(cli, ["diff", str(left), str(right), "--json"])
    r2 = runner.invoke(cli, ["diff", str(left), str(right), "--format", "json"])
    assert r1.exit_code == 0
    assert r2.exit_code == 0
    p1 = json.loads(r1.output)
    p2 = json.loads(r2.output)
    assert p1 == p2


def test_markdown_output_starts_with_h2_header(two_souls: tuple[Path, Path]) -> None:
    """--format markdown emits a paste-ready block with an h2 header."""
    left, right = two_souls
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right), "--format", "markdown"])
    assert result.exit_code == 0
    assert result.output.startswith("## Soul diff:")


def test_section_filter_narrows_text_output(tmp_path: Path) -> None:
    """--section memory only renders the memory section in text mode."""

    async def _setup() -> tuple[Path, Path]:
        soul_a = await Soul.birth("Aria", archetype="X")
        left = tmp_path / "left.soul"
        await soul_a.export(str(left), include_keys=True)

        soul_b = await Soul.awaken(str(left))
        soul_b._identity.archetype = "Y"  # identity change
        await soul_b.remember("Memory A", importance=5)  # memory change
        soul_b.bond.strengthen(amount=10.0)  # bond change
        right = tmp_path / "right.soul"
        await soul_b.export(str(right), include_keys=True)
        return left, right

    left, right = asyncio.run(_setup())
    runner = CliRunner()
    full = runner.invoke(cli, ["diff", str(left), str(right)])
    memory_only = runner.invoke(cli, ["diff", str(left), str(right), "--section", "memory"])

    assert full.exit_code == 0
    assert memory_only.exit_code == 0
    assert "Memory A" in memory_only.output
    # Identity and Bond sections should be present in full output but absent
    # from the memory-only output.
    assert "Identity" in full.output
    assert "Identity" not in memory_only.output


def test_section_filter_alias_dna_for_ocean(two_souls: tuple[Path, Path]) -> None:
    """--section dna and --section ocean both target the OCEAN section."""
    left, right = two_souls
    runner = CliRunner()
    result_dna = runner.invoke(cli, ["diff", str(left), str(right), "--section", "dna"])
    result_ocean = runner.invoke(cli, ["diff", str(left), str(right), "--section", "ocean"])
    assert result_dna.exit_code == 0
    assert result_ocean.exit_code == 0


def test_unknown_section_errors(two_souls: tuple[Path, Path]) -> None:
    """An unknown section name fails fast with an explanation."""
    left, right = two_souls
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right), "--section", "bogus"])
    assert result.exit_code != 0
    assert "unknown section" in result.output.lower()


def test_summary_only_emits_counts(tmp_path: Path) -> None:
    """--summary-only renders per-section counts, not the full diff."""

    async def _setup() -> tuple[Path, Path]:
        soul_a = await Soul.birth("Aria")
        left = tmp_path / "left.soul"
        await soul_a.export(str(left), include_keys=True)

        soul_b = await Soul.awaken(str(left))
        await soul_b.remember("Mem 1", importance=5)
        await soul_b.remember("Mem 2", importance=5)
        right = tmp_path / "right.soul"
        await soul_b.export(str(right), include_keys=True)
        return left, right

    left, right = asyncio.run(_setup())
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", str(left), str(right), "--summary-only", "--json"])
    assert result.exit_code == 0, result.output
    counts = json.loads(result.output)
    assert counts["memories_added"] == 2


# ---------------------------------------------------------------------------
# diff_souls direct (Python API surface)
# ---------------------------------------------------------------------------


def test_diff_souls_returns_pydantic_model(tmp_path: Path) -> None:
    """The runtime entry point returns a SoulDiff that's roundtripable."""

    async def _setup() -> object:
        soul_a = await Soul.birth("Aria")
        left = tmp_path / "left.soul"
        await soul_a.export(str(left), include_keys=True)
        soul_b = await Soul.awaken(str(left))
        await soul_b.remember("Test fact", importance=5)
        right = tmp_path / "right.soul"
        await soul_b.export(str(right), include_keys=True)
        return await Soul.awaken(str(left)), await Soul.awaken(str(right))

    left_soul, right_soul = asyncio.run(_setup())
    diff = diff_souls(left_soul, right_soul)
    assert diff.left_name == "Aria"
    assert len(diff.memory.added) == 1
    summary = diff.summary()
    assert summary["memories_added"] == 1
    # round-trip through model_dump
    re_loaded = type(diff).model_validate(diff.model_dump(mode="json"))
    assert len(re_loaded.memory.added) == 1
