---
{
  "title": "CLI Test Suite: Org Initialization (`soul org init`)",
  "summary": "Test suite for `soul org init`, which bootstraps an organization by creating a root soul, a journal, and cryptographic keys. Covers happy-path artifact creation, idempotency guards, force-overwrite behavior, key file permissions, journal privacy, and round-trip loadability.",
  "concepts": [
    "org init",
    "root soul",
    "journal",
    "genesis events",
    "private key",
    "key permissions",
    "0600",
    "idempotency",
    "--force",
    "--non-interactive",
    "Soul.awaken",
    "journal privacy",
    "audit trail"
  ],
  "categories": [
    "testing",
    "CLI",
    "org initialization",
    "security",
    "test"
  ],
  "source_docs": [
    "bf431965c3639095"
  ],
  "backlinks": null,
  "word_count": 408,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_org_init.py` validates the org initialization command -- the entry point for deploying Soul Protocol in a multi-user context. A successful `org init` run produces a root soul file, an append-only journal database, and a private key file. Each of these artifacts has correctness and security requirements that the test suite enforces.

## Happy Path

`test_fresh_init_creates_all_artifacts` is the baseline test. It invokes `org init` with `--non-interactive` and asserts:

```python
assert (data_dir / "root.soul").exists()
assert (data_dir / "journal.db").exists()
assert result.exit_code == 0
```

This single test catches regressions where the command exits 0 but fails to write one of the required files -- a class of bug that output-only assertions miss.

## Journal Genesis Events

`test_init_writes_two_genesis_events` opens the journal directly and counts event entries. Two events are expected: one for org creation and one for the root soul birth. Missing genesis events would break downstream queries that depend on the full history being present from the start.

## Idempotency and Force Override

```python
def test_rerun_without_force_refuses(tmp_path):
    _invoke_init(runner, data_dir)
    result = _invoke_init(runner, data_dir)  # second run
    assert result.exit_code != 0
    assert "already initialized" in result.output.lower()
```

Re-running `org init` without `--force` must refuse. This prevents accidental overwrites in production deployments where init scripts might run more than once.

```python
def test_rerun_with_force_overwrites(tmp_path):
    _invoke_init(runner, data_dir)
    result = _invoke_init(runner, data_dir, "--force")
    assert result.exit_code == 0
```

`--force` is the explicit escape hatch for intentional reinitializations.

## Non-Interactive Guard

`test_non_interactive_without_org_name_fails` ensures that `--non-interactive` without `--org-name` fails immediately. This prevents CI scripts from hanging on a prompt they cannot answer.

## Key File Permissions

```python
def test_private_key_has_0600_permissions(tmp_path):
    _invoke_init(runner, data_dir)
    mode = stat.S_IMODE(os.stat(key_path).st_mode)
    assert mode == 0o600
```

Private keys must be owner-readable only. The 0600 check is a security requirement: world-readable key files compromise the entire identity system.

## Round-Trip Loadability

`test_root_soul_is_loadable_by_awaken` confirms that the root soul produced by `org init` can be loaded by `Soul.awaken()`. This is a cross-layer integration check -- it verifies that the CLI output format is compatible with the Python runtime parser.

## Private Key Isolation from Journal

```python
def test_private_key_not_in_journal_payloads(tmp_path):
    # Read all journal events and assert no payload contains the key material
```

The private key must never appear in the append-only journal. Since the journal cannot be retroactively edited, any key leakage would be permanent.

## Known Gaps

No TODOs flagged. This file was renamed from `test_paw_os_init.py` as part of the Org Architecture RFC (#164) and command paths were updated from `paw os init` to `org init`.