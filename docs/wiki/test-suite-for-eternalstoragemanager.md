---
{
  "title": "Test Suite for EternalStorageManager",
  "summary": "Unit tests for EternalStorageManager — the orchestration layer that routes archive, recover, and verify operations across multiple storage providers. Covers provider registration/unregistration, selective tier archiving, fallback recovery chains, unavailable-provider skipping, and verification status.",
  "concepts": [
    "EternalStorageManager",
    "provider registration",
    "archive",
    "recover",
    "verify",
    "fallback chain",
    "tier selection",
    "RecoverySource",
    "ArchiveResult",
    "mock providers"
  ],
  "categories": [
    "testing",
    "eternal storage",
    "orchestration",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "dc73fceed7648f42"
  ],
  "backlinks": null,
  "word_count": 511,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_manager.py` tests `EternalStorageManager` in isolation, using mock providers to control behavior precisely. The manager is the central coordinator for all eternal storage operations — it tracks which providers are registered, routes archive calls to the right tiers, and chains recovery attempts in priority order. Testing it in isolation from the CLI and Soul layers allows precise assertion about its internal logic.

## Fixture Setup

```python
@pytest.fixture
def manager():
    mgr = EternalStorageManager()
    mgr.register(MockIPFSProvider())
    mgr.register(MockArweaveProvider())
    mgr.register(MockBlockchainProvider())
    return mgr
```

All tests use three mock providers by default. The `LocalStorageProvider` is omitted from most tests to keep assertions simpler.

## Registration Tests (`TestRegistration`)

- **`test_register_provider`** — confirms that after `mgr.register(MockIPFSProvider())`, `mgr.providers` contains the key `"ipfs"`. This validates that providers self-identify by tier name.
- **`test_unregister`** — confirms successful removal returns `True`. Unregistering a provider at runtime is needed when a tier becomes permanently unavailable (e.g., a private IPFS node is shut down).
- **`test_unregister_missing`** — returns `False` (not an exception) for a tier that was never registered. Safe no-op semantics prevent crashes in teardown code.

## Archive Tests (`TestArchive`)

- **`test_archive_all_tiers`** — calling `archive()` without a `tiers` argument routes to all registered providers and returns one result per provider.
- **`test_archive_specific_tiers`** — `tiers=["ipfs"]` routes to exactly one provider. The test confirms that only one `ArchiveResult` is returned and its `tier` is `"ipfs"`.
- **`test_archive_unknown_tier_raises`** — requesting an unregistered tier (`"s3"`) raises `ValueError` with a message matching `"No provider registered"`. Failing loudly on unknown tiers prevents silently skipping intended archival destinations.
- **`test_archive_tracks_sources`** — after archiving, `manager.get_recovery_sources(soul_id)` returns sources for each archived tier. This confirms the manager maintains internal state for recovery.
- **`test_archive_multiple_times`** — archiving to IPFS first, then to Arweave, accumulates two sources in the recovery list. This supports incremental archiving strategies.

## Recovery Tests (`TestRecover`)

- **`test_recover_from_ipfs`** / **`test_recover_from_arweave`** — single-tier recovery returns the exact bytes that were archived.
- **`test_recover_fallback`** — given a list of sources in priority order, the manager tries each in sequence and returns the first successful result. This is the core resilience mechanism.
- **`test_recover_skips_unavailable`** — sources marked `available=False` are skipped. The manager must not attempt a retrieve call on a known-unavailable source (which would waste time or produce misleading errors).
- **`test_recover_all_fail_raises`** — when all sources fail, the manager raises rather than returning `None`. Silent failures would leave the caller with no indication that recovery was unsuccessful.
- **`test_recover_no_provider_raises`** — calling `recover()` with an empty source list raises immediately.

## Verification Tests (`TestVerifyAll`)

- **`test_verify_all_after_archive`** — after successful archival to all tiers, `verify_all()` returns `{tier: True}` for each tier.
- **`test_verify_all_unknown_soul`** — verifying a soul ID that has never been archived returns an empty dict (not an error).
- **`test_verify_all_partial`** — if one provider is registered but the soul was only archived to some tiers, the dict contains only the tiers that were actually archived.

## Known Gaps

No TODO markers. Error propagation when an individual provider's `archive()` call raises (as opposed to returning a failed result) is not explicitly tested — the suite assumes providers handle their own errors and return `ArchiveResult` objects.
