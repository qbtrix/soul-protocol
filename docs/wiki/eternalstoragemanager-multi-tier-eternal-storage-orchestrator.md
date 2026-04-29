---
{
  "title": "EternalStorageManager: Multi-Tier Eternal Storage Orchestrator",
  "summary": "The `EternalStorageManager` coordinates multiple eternal storage backends (Arweave, IPFS, etc.) for archiving and recovering soul data. It registers providers by tier name, fans out archive operations across requested tiers, and attempts ordered recovery from tracked sources — failing gracefully if individual tiers are unavailable.",
  "concepts": [
    "EternalStorageManager",
    "multi-tier storage",
    "IPFS",
    "Arweave",
    "soul archiving",
    "recovery",
    "RecoverySource",
    "ArchiveResult",
    "with_mocks",
    "verify_all",
    "ordered fallback"
  ],
  "categories": [
    "eternal storage",
    "soul portability",
    "resilience"
  ],
  "source_docs": [
    "c5c93555cf8d1111"
  ],
  "backlinks": null,
  "word_count": 501,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Souls need to outlive any single platform. The `EternalStorageManager` implements a multi-tier persistence strategy: archive a soul to multiple permanent storage backends simultaneously, so recovery can succeed even if some backends are unavailable.

This is analogous to RAID for soul data: redundancy across independent storage systems (IPFS content-addressed storage + Arweave permanent blockchain storage) provides durability no single provider can guarantee alone.

## Registration Model

```python
mgr = EternalStorageManager()
mgr.register(IPFSProvider())      # tier_name = "ipfs"
mgr.register(ArweaveProvider())   # tier_name = "arweave"
```

Providers self-declare their tier name. The manager stores them in a dict keyed by tier name, allowing targeted operations (`archive(tiers=["ipfs"])`) or fan-out to all (`archive()` with no `tiers` arg).

### with_mocks() Factory

```python
mgr = EternalStorageManager.with_mocks()
```

Provides a fully-wired manager with mock IPFS and Arweave providers for testing. Mock providers are registered via lazy imports from `providers/mock_ipfs` and `providers/mock_arweave`, keeping the core manager free of optional dependencies.

## Archive: Fan-Out to Multiple Tiers

```python
async def archive(self, soul_data: bytes, soul_id: str,
                  tiers: list[str] | None = None, **kwargs) -> list[ArchiveResult]:
    target_tiers = tiers or list(self._providers.keys())
    results = []
    for tier in target_tiers:
        provider = self._providers.get(tier)
        if provider is None:
            raise ValueError(f"No provider registered for tier '{tier}'. ...")
        result = await provider.archive(soul_data, soul_id, **kwargs)
        results.append(result)
        # Track reference for later recovery
        source = RecoverySource(tier=tier, reference=result.reference, available=True)
        self._archives.setdefault(soul_id, []).append(source)
    return results
```

Archive results are tracked internally as `RecoverySource` objects indexed by `soul_id`. This means `get_recovery_sources()` can reconstruct the list of all known locations without requiring the caller to track them.

## Recovery: Ordered Fallback

```python
async def recover(self, sources: list[RecoverySource]) -> bytes:
    errors = []
    for source in sources:
        provider = self._providers.get(source.tier)
        if provider is None:
            errors.append(f"{source.tier}: no provider registered")
            continue
        if not source.available:
            errors.append(f"{source.tier}: source marked unavailable")
            continue
        try:
            data = await provider.retrieve(source.reference)
            return data  # success — stop trying
        except Exception as exc:
            errors.append(f"{source.tier}: {exc}")
            continue
    raise RuntimeError(f"Failed to recover from any source. Errors: {'; '.join(errors)}")
```

Sources are tried in the order provided. The caller controls priority by ordering the `sources` list. If all sources fail, a descriptive `RuntimeError` aggregates all individual error messages, making debugging much easier than a generic "recovery failed" message.

The `source.available` flag allows previously-verified unavailable sources to be skipped without making a network call.

## Verification

`verify_all()` checks each tracked archive against its provider's `verify()` method and updates the `available` flag on each `RecoverySource`. This keeps the manager's internal state synchronized with reality — a source that was available at archive time may have become unavailable (e.g., IPFS unpinning).

## Known Gaps

- Archive operations are executed **sequentially** across tiers in a `for` loop. For true redundancy with many tiers, concurrent archiving (via `asyncio.gather`) would be more efficient and would allow partial success if one tier is slow.
- The `_archives` dict is in-memory only — it is not persisted. If the manager is recreated, `get_recovery_sources()` returns empty results even if prior archives exist on IPFS/Arweave. Recovery in a fresh process requires the caller to supply `RecoverySource` objects from external storage.