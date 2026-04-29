---
{
  "title": "CLI Test Suite: Health, Cleanup, and Repair Commands",
  "summary": "Test suite for three soul maintenance CLI commands: `soul health` (diagnostic reporting), `soul cleanup` (duplicate/low-importance memory removal), and `soul repair` (energy reset). Covers dry-run safety guards, auto-mode mutations, and persistence verification.",
  "concepts": [
    "soul health",
    "soul cleanup",
    "soul repair",
    "dry-run",
    "auto cleanup",
    "duplicate removal",
    "importance pruning",
    "energy reset",
    "memory tier counts",
    "soul maintenance",
    "mtime guard",
    "persistence verification"
  ],
  "categories": [
    "testing",
    "CLI",
    "soul maintenance",
    "memory management",
    "test"
  ],
  "source_docs": [
    "7d0171a110786c20"
  ],
  "backlinks": null,
  "word_count": 436,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_health_cleanup_repair.py` guards the maintenance layer of the Soul Protocol CLI. These three commands exist to keep souls in a healthy, non-bloated state over long lifetimes. The tests ensure that both read-only diagnostic paths and destructive mutation paths behave correctly -- and that the dry-run boundary is never violated.

## Health Command (`soul health`)

The `TestHealthCommand` class verifies that `soul health <path>` produces a complete diagnostic report:

- Soul name is displayed
- Memory tier counts are shown (episodic, semantic, procedural)
- A total memory count is reported
- Bond and skills/evals sections appear
- Fresh souls report no issues
- After a `remember` call, episodic count increments to non-zero

The final assertion is particularly important: it confirms that the health command reads live data rather than a snapshot, so users see current state.

## Cleanup -- Dry Run (`soul cleanup --dry-run`)

`TestCleanupDryRun` exists to enforce a critical safety contract: **dry-run must never modify the soul file**. Tests verify:

```python
def test_cleanup_dry_run_does_not_modify_soul(tmp_path):
    mtime_before = soul_path.stat().st_mtime
    runner.invoke(cli, ["cleanup", "--dry-run", str(soul_path)])
    assert soul_path.stat().st_mtime == mtime_before
```

The `mtime` check prevents a class of bugs where a command labeled dry-run silently writes. The output must also mention dry-run explicitly so users understand no changes were made.

## Cleanup -- Auto Mode (`soul cleanup --auto`)

`TestCleanupAuto` covers actual mutation:

- **Duplicate removal**: Two identical memories are stored; after `--auto`, only one remains. This prevents memory bloat from repeated `remember` calls with the same content.
- **Low-importance pruning**: When a minimum importance threshold is specified, sub-threshold memories are removed.
- **File persistence**: After cleanup, the soul file is reloaded and the memory count is verified. This confirms that cleanup writes back to disk, not just to the in-memory representation.

## Repair -- Reset Energy (`soul repair --reset-energy`)

`TestRepairResetEnergy` covers the energy reset operation:

- Exit code 0 on success
- Output mentions 100% confirming the reset value
- Soul name appears in output
- The new energy level persists to the file (verified by reloading)
- Calling `repair` without any flag warns the user and exits cleanly -- this prevents silent no-ops

## Helper Utilities

Two helpers power the test setup:

```python
def _birth_soul_at(path, name) -> None:
    # Synchronously birth a soul via CLI birth command

async def _birth_and_export(tmp_path, name) -> str:
    # Birth in-memory and export to tmp_path, returns .soul file path
```

The dual helpers exist because some tests need the CLI path (to test CLI-specific behavior) while others need the Python API path (to test the underlying engine).

## Known Gaps

No TODOs or FIXMEs flagged. Suite was created 2026-03-26 as part of the health/cleanup/repair feature addition.