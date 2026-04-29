---
{
  "title": "CLI Test Suite: Core Commands (birth, inspect, status, remember, recall, init)",
  "summary": "Comprehensive test suite for the Soul Protocol CLI covering the full lifecycle of a soul: creation, inspection, memory storage across tiers, multi-format output, and init options. Tests use click.testing.CliRunner to invoke commands in isolation and assert on exit codes, output text, and ZIP archive contents.",
  "concepts": [
    "CLI",
    "soul birth",
    "soul inspect",
    "soul status",
    "soul remember",
    "soul recall",
    "soul init",
    "memory tiers",
    "episodic",
    "semantic",
    "procedural",
    "CliRunner",
    "ZIP archive",
    "output modes",
    "format selection"
  ],
  "categories": [
    "testing",
    "CLI",
    "soul lifecycle",
    "memory",
    "test"
  ],
  "source_docs": [
    "eb4f4860e988db92"
  ],
  "backlinks": null,
  "word_count": 470,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `test_cli.py` suite is the primary regression guard for Soul Protocol's command-line interface. Every user-facing command is exercised here using Click's `CliRunner`, which captures stdout/stderr without requiring a real terminal. This approach lets tests run in any CI environment without system-level side effects.

## Command Coverage

### birth
Creates a `.soul` file at a given output path. Tests assert that the file exists on disk, exit code is 0, and the soul's name appears in confirmation output. The `-o` flag is required -- the test pins this contract so regressions in path handling are caught immediately.

### inspect / status
Both commands read an existing `.soul` file. `inspect` displays identity fields including the DID (`did:soul:` prefix is asserted). `status` shows mood and energy level. Tests chain `birth` then `inspect`/`status` to confirm a round-trip: write a file, then read it back.

### remember -- Memory Tier Routing
The `remember` command has the most coverage because routing to the correct memory tier is a core correctness concern:

```python
result = runner.invoke(cli, ["remember", soul_path, "Shipped v0.3 today", "--type", "episodic", "-i", "8"])
```

After storing, tests open the ZIP archive directly and inspect `memory/episodic.json` vs `memory/semantic.json` to verify routing. This prevents silent mis-routing where a memory appears to save but lands in the wrong tier.

- `--type episodic` routes to `memory/episodic.json`, leaving semantic empty
- `--type procedural` routes to `memory/procedural.json`
- No `--type` defaults to semantic (backward compatibility contract)
- Invalid `--type` exits with code 1 and an error message

The emotion tag (`-e happy`) is also tested to ensure it passes through to the stored entry.

### recall -- Output Modes
`recall` supports three display modes, each tested independently:

| Mode | Flag | Assertion |
|------|------|-----------|
| Default table | none | Rich table rendered |
| Full content | `--full` | No truncation in output |
| JSON | `--json` | `json.loads()` succeeds, returns list |

Edge cases covered: `--recent N` pagination, empty results on a fresh soul, and the error path when neither query nor `--recent` is supplied.

### init -- Format Selection
`soul init` can create a soul in two formats:

```python
# Directory format (default)
runner.invoke(cli, ["init", "--format", "dir", str(tmp_path)])
# -> tmp_path/soul.json exists

# ZIP format
runner.invoke(cli, ["init", "--format", "zip", str(tmp_path)])
# -> tmp_path.soul ZIP file exists
```

The test for `--setup` with a pre-existing soul verifies idempotency: re-running init must not overwrite an existing soul. This prevents accidental data loss when users re-run setup scripts.

## Design Patterns

All tests follow a **birth-then-operate** pattern: each test creates a fresh soul in `tmp_path`, then exercises the command under test. Using `tmp_path` (pytest's per-test temporary directory) ensures complete isolation -- no shared state between tests.

## Known Gaps

No known gaps flagged in source. The suite was last updated 2026-03-27 to add `--full` and `--json` coverage.