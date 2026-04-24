---
{
  "title": "Test Suite for Eternal Storage Providers",
  "summary": "Per-provider tests for the four eternal storage backends: MockIPFSProvider, MockArweaveProvider, MockBlockchainProvider, and LocalStorageProvider. Each provider is tested for archive, retrieve, verify, content addressing, unique identifiers, and error behavior on missing references.",
  "concepts": [
    "MockIPFSProvider",
    "MockArweaveProvider",
    "MockBlockchainProvider",
    "LocalStorageProvider",
    "content addressing",
    "CID",
    "Arweave transaction",
    "permanent storage",
    "archive",
    "retrieve",
    "verify",
    "unique identifiers"
  ],
  "categories": [
    "testing",
    "eternal storage",
    "providers",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "50aaa63af17373a2"
  ],
  "backlinks": null,
  "word_count": 517,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_providers.py` tests each eternal storage provider in isolation. While `test_manager.py` tests how the manager orchestrates providers, this suite focuses on the providers themselves — their internal behavior, the shape of their outputs, and their handling of missing or invalid references. Each provider has its own test class with a dedicated fixture.

## MockIPFSProvider

IPFS uses **content addressing**: the same data always produces the same CID (Content Identifier), regardless of which soul or when.

```python
async def test_content_addressed(self, provider):
    """Same data should produce the same CID."""
    r1 = await provider.archive(SAMPLE_DATA, "soul-1")
    r2 = await provider.archive(SAMPLE_DATA, "soul-2")
    assert r1.reference == r2.reference  # CID is data-derived, not soul-derived
```

This is a fundamental IPFS property that the mock must replicate. If the mock used random IDs, tests that rely on deduplication or cross-soul sharing would not be valid simulations.

`test_different_data_different_cid` is the complement: different data must produce different CIDs, confirming the mock's hashing is not trivially constant.

Archive results must include:
- `reference` starting with `"bafybeig"` (the IPFS CIDv1 prefix)
- `url` containing `"ipfs.io"` (the public gateway format)
- `metadata["cid"]` equal to the reference (CID duplication in metadata for convenience)
- `metadata["size_bytes"]` equal to the length of the archived data

`test_retrieve_missing_raises` — retrieving a non-existent CID must raise `KeyError` with the word `"not found"` in the message, not return `None`. Returning `None` would allow silent data loss scenarios to pass undetected.

## MockArweaveProvider

Arweave is a **permanent** storage network with per-upload transaction costs.

```python
async def test_archive_has_cost(self, provider):
    result = await provider.archive(SAMPLE_DATA, SOUL_ID)
    assert result.cost.startswith("$")
    cost_val = float(result.cost.replace("$", ""))
    assert cost_val > 0
```

The cost assertion confirms that the mock simulates the economic reality of Arweave — uploads are not free. Callers that inspect cost before deciding to archive need a non-zero value to make meaningful decisions.

`result.permanent is True` — Arweave's design guarantee is permanence. The mock must reflect this so that callers relying on `permanent=True` for long-term archival decisions get correct signals.

Transaction IDs are 43 characters (`len(result.reference) == 43`), matching Arweave's actual TX ID format. Length-checking catches implementations that use shorter random strings.

`test_unique_tx_ids` — each archive call must produce a unique transaction ID, even for identical data. Unlike IPFS, Arweave is not content-addressed by design — each upload is a separate transaction.

## MockBlockchainProvider

Similar structure to Arweave: unique token IDs, non-zero costs, and permanent archival. `test_unique_token_ids` verifies that NFT-style token identifiers do not collide.

## LocalStorageProvider

The local provider writes to the filesystem (within `tmp_path`). Unlike mock providers that store in memory, it tests real I/O:

```python
@pytest.fixture
def provider(self, tmp_path):
    return LocalStorageProvider(base_dir=tmp_path / "local")
```

The `base_dir` parameter is used to isolate test data. File-based tests confirm that archive, retrieve, and verify work correctly when data persists to disk rather than memory — this is important for the local fallback that backs up soul files locally before pushing to decentralized networks.

## Known Gaps

No TODO markers. The mock providers simulate network latency as zero — real provider tests would need configurable delays to test timeout handling. Real network integration (actual IPFS/Arweave API calls) is out of scope for this suite.
