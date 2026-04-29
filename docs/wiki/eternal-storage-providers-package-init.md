---
{
  "title": "Eternal Storage Providers Package Init",
  "summary": "The `eternal/providers/` package init collects all four storage provider implementations — `LocalStorageProvider`, `MockIPFSProvider`, `MockArweaveProvider`, and `MockBlockchainProvider` — and exposes them through a single import point. This makes provider selection ergonomic for callers who want to pick a backend without navigating nested modules.",
  "concepts": [
    "LocalStorageProvider",
    "MockIPFSProvider",
    "MockArweaveProvider",
    "MockBlockchainProvider",
    "eternal storage providers",
    "package init",
    "tiered storage",
    "storage backends",
    "soul archive"
  ],
  "categories": [
    "eternal-storage",
    "providers",
    "package-structure"
  ],
  "source_docs": [
    "cd5689ac37d797ce"
  ],
  "backlinks": null,
  "word_count": 275,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`eternal/providers/__init__.py` is the public surface of the eternal storage provider ecosystem. It aggregates all concrete backend implementations so consumers can write:

```python
from soul_protocol.runtime.eternal.providers import MockArweaveProvider, LocalStorageProvider
```

...instead of importing from individual submodules. This is a standard Python packaging pattern for subpackages that contain multiple peer implementations.

## Providers Exposed

| Class | Tier | Use Case |
|---|---|---|
| `LocalStorageProvider` | `local` | Development, offline backups, fast writes |
| `MockIPFSProvider` | `ipfs` | Testing IPFS content-addressed semantics without a node |
| `MockArweaveProvider` | `arweave` | Testing Arweave permanent-storage semantics without a gateway |
| `MockBlockchainProvider` | `blockchain` | Testing on-chain soul registry without a wallet or chain |

## Why Four Providers?

Soul Protocol's architecture supports a tiered storage strategy — the same soul can be archived to multiple backends simultaneously. Local provides fast, always-available fallback. IPFS provides content-addressable redundancy. Arweave provides permanent immutable history. Blockchain provides on-chain proof of identity ownership.

The mock providers exist specifically to let the test suite and development environment exercise the full soul lifecycle — pack, archive, retrieve, verify — without requiring real infrastructure. This is critical: requiring live IPFS or Arweave nodes for unit tests would make the test suite slow, flaky, and environment-dependent.

## Data Flow

Callers reference this `__init__` → individual provider classes are imported from their respective modules (`local.py`, `mock_arweave.py`, `mock_blockchain.py`, `mock_ipfs.py`) → each provider implements the `EternalStorageProvider` protocol from `eternal/protocol.py`.

## Known Gaps

The naming convention `Mock*` implies these are test-only. A production `IPFSProvider`, `ArweaveProvider`, and `BlockchainProvider` backed by real SDKs are not yet present in this package. As the project matures, real providers will be added here.