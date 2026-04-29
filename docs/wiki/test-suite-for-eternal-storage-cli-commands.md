---
{
  "title": "Test Suite for Eternal Storage CLI Commands",
  "summary": "Tests the soul-protocol CLI commands for eternal storage operations: archive (with optional tier selection), eternal-status (tier health check), and recover (with failure path handling). Uses Click's CliRunner for isolated, in-process command invocation.",
  "concepts": [
    "CLI",
    "archive command",
    "recover command",
    "eternal-status",
    "CliRunner",
    "Click",
    "tier selection",
    "IPFS",
    "Arweave",
    "blockchain",
    "eternal storage"
  ],
  "categories": [
    "testing",
    "CLI",
    "eternal storage",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "aac07f82df9807f8"
  ],
  "backlinks": null,
  "word_count": 477,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_cli_eternal.py` tests the CLI surface of the eternal storage subsystem. The eternal storage commands let users archive, verify, and recover soul files from decentralized backends without writing any Python code. These tests validate the CLI contract: correct exit codes, correct output content, and graceful failure messages.

## Testing Approach: Click CliRunner

All tests use Click's `CliRunner` to invoke CLI commands in-process without spawning a subprocess:

```python
runner = CliRunner()
result = runner.invoke(cli, ["archive", soul_path])
assert result.exit_code == 0
```

This approach is faster than subprocess-based tests, captures stdout/stderr reliably, and runs in an isolated environment without side effects on the real filesystem beyond the `tmp_path` fixture scope.

## Test Coverage

### `test_archive_command`
The full archive flow:
1. `birth ArchiveBot -o <path>` — creates a fresh soul file.
2. `archive <path>` — archives it to all configured tiers.
3. Asserts exit code 0 and checks that the output names all three tiers (`ipfs`, `arweave`, `blockchain`) and the soul's name.

The tier name assertions are case-insensitive (`result.output.lower()`), which prevents brittle failures if the CLI changes capitalization in its output format.

### `test_archive_specific_tier`
Uses the `-t`/`--tiers` flag to archive to a single tier:

```python
result = runner.invoke(cli, ["archive", soul_path, "-t", "ipfs"])
assert result.exit_code == 0
assert "ipfs" in result.output.lower()
```

This tests selective archival, which is useful for incremental archiving strategies (e.g., archive to IPFS first for speed, then add Arweave later for permanence).

### `test_eternal_status_command`
The `eternal-status` command shows which tiers a soul has been archived to and whether each archive is verifiable:

```python
result = runner.invoke(cli, ["eternal-status", soul_path])
assert "IPFS" in result.output
assert "Arweave" in result.output
assert "Blockchain" in result.output
```

The uppercase assertions here reflect the actual display format of the status table (tier names are capitalized for display, unlike the internal tier identifiers which are lowercase).

### `test_recover_missing_reference`
Tests the failure path for `recover` when given a reference that does not exist in any provider:

```python
result = runner.invoke(cli, ["recover", "nonexistent-ref", "-t", "ipfs", "-o", output_path])
assert result.exit_code == 0  # CLI should not crash
assert "failed" in result.output.lower() or "Recovery failed" in result.output
```

The `exit_code == 0` assertion for a failure case is intentional: the CLI reports the failure in its output rather than using a non-zero exit code. This is a UX choice — the command "ran successfully" (it attempted recovery and clearly reported the outcome), rather than the recovery operation itself succeeding.

## Data Flow

```
user → CLI command
    → Click router
    → eternal subcommand handler
        → EternalStorageManager
            → MockIPFSProvider / MockArweaveProvider / MockBlockchainProvider
        → formatted output table
    → CLI exit
```

In tests, mock providers are used by default, so no real network calls are made.

## Known Gaps

No TODO markers. The test for `recover` tests only the failure path; a success-path recovery test is covered in `test_e2e_eternal.py` at the manager level, not repeated here to avoid duplication.
