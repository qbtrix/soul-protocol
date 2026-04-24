---
{
  "title": "CLI Test Suite: Full Onboarding, Multi-User Lifecycle, and Destroy Workflow",
  "summary": "End-to-end test suite for the `soul init` onboarding wizard covering user scope creation, fleet provisioning, status reporting, soul deletion, and the destroy command that archives then wipes all data. Also validates journal append-only privacy constraints and users-dir precedence rules.",
  "concepts": [
    "soul init",
    "onboarding wizard",
    "fleet provisioning",
    "soul destroy",
    "archive tarball",
    "journal append-only",
    "right to erasure",
    "root soul guard",
    "users-dir precedence",
    "SOUL_USERS_DIR",
    "multi-user",
    "soul delete",
    "journal validator"
  ],
  "categories": [
    "testing",
    "CLI",
    "onboarding",
    "data lifecycle",
    "test"
  ],
  "source_docs": [
    "7400306f2071f322"
  ],
  "backlinks": null,
  "word_count": 444,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_onboarding_full.py` is the highest-level integration test in the CLI suite. It exercises the complete org/user lifecycle from initial wizard setup through data destruction, including edge cases around directory placement, privacy guarantees, and configuration precedence.

## Full Wizard Initialization

`test_full_wizard_creates_user_scopes_and_fleet` runs the complete interactive setup path, verifying that:

- User soul files are created under the expected scope directory
- A fleet of souls is provisioned when requested
- All output paths are within the configured data directory

`test_skip_fleet_and_minimal_init` verifies the minimal path -- users who skip fleet provisioning get a working setup with no orphaned artifacts.

## Status Reporting

Two status tests ensure the `soul status` command works at the org level:

- `test_status_reports_init_state`: machine-readable state is accurate
- `test_status_human_readable`: human-readable output is correctly formatted
- `test_status_missing_dir_errors`: missing data dir produces a clear error, not a stack trace

## Destroy Command

The destroy workflow archives all data to a tarball before wiping the data directory. Several edge cases are tested:

```python
def test_destroy_with_default_archives_survives(tmp_path, monkeypatch):
    """The default archives dir is a SIBLING of the data dir, not nested."""
```

This test exists because an early bug caused the archive directory to be placed inside the data directory, which meant it would be wiped along with the data it was supposed to preserve. The sibling placement is now a tested contract.

```python
def test_destroy_with_archives_inside_data_dir_completes_cleanly(tmp_path):
    """If a user explicitly puts archives_dir inside data_dir, the tarfile still completes."""
```

When users explicitly choose a nested archive path, the tarfile creation must still succeed.

## Privacy: Right-to-Erasure and Journal Append-Only

```python
def test_user_joined_payload_does_not_leak_email(tmp_path):
    # Journal is append-only -- email stored in payloads cannot be erased retroactively
```

This test exists not to assert a positive capability but to document a known architectural constraint: because the journal is append-only, email addresses stored in event payloads cannot be erased. The test ensures email is NOT written to the journal at join time.

## Soul Deletion Guards

- `test_soul_delete_refuses_root`: the root soul cannot be deleted via CLI
- `test_soul_delete_succeeds_for_non_root`: non-root souls can be deleted normally
- `test_soul_delete_python_api_raises`: the Python API also enforces the root deletion guard

Journal validators are tested independently to confirm they reject root soul retirement from both actor and payload paths.

## Users Directory Precedence

Three tests establish a clear priority order for user soul storage location:

1. `--users-dir` CLI flag wins over everything
2. `SOUL_USERS_DIR` env var is honored when no flag is passed
3. Default falls under `data_dir/users/` when neither is set

This precedence is critical for deployments that configure Soul Protocol via environment variables.

## Known Gaps

No TODOs flagged. The `_full_init` helper is reused across tests to reduce boilerplate and keep setup consistent.