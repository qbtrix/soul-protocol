---
{
  "title": "Eternal Storage Spec Package — Public Interface for Permanent Soul Archival",
  "summary": "The `spec/eternal` package exposes the three types that define Soul Protocol's permanent archival tier: `EternalStorageProvider` (the backend protocol), `ArchiveResult` (what an archive operation returns), and `RecoverySource` (what a soul can be restored from). All implementation details live in the engine layer.",
  "concepts": [
    "EternalStorageProvider",
    "ArchiveResult",
    "RecoverySource",
    "eternal storage",
    "IPFS",
    "Arweave",
    "soul archival",
    "content-addressed storage",
    "five-tier memory",
    "permanent storage"
  ],
  "categories": [
    "eternal storage",
    "spec layer",
    "soul archival",
    "decentralized storage"
  ],
  "source_docs": [
    "388f7ee13931eff7"
  ],
  "backlinks": null,
  "word_count": 331,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul Protocol's "eternal storage" tier is the outermost ring of its five-tier memory architecture. While the inner tiers (working, episodic, semantic, procedural) live on the host platform, eternal storage writes a soul's full state to a permanent, content-addressed store — IPFS, Arweave, or a blockchain — so the soul can survive platform shutdowns, migrations, or hardware failures.

The `spec/eternal/__init__.py` file is the package's public API surface. It re-exports the three types that third-party runtimes need to interact with eternal storage:

```python
from .protocol import ArchiveResult, EternalStorageProvider, RecoverySource

__all__ = [
    "EternalStorageProvider",
    "ArchiveResult",
    "RecoverySource",
]
```

## Why Separate from the Engine?

The spec layer contains no opinions about which decentralized storage network to use. `EternalStorageProvider` is a `Protocol` — concrete backends for IPFS, Arweave, and local-file-based archival (for testing) live in the engine layer. This separation means:

- A third-party runtime can implement its own eternal storage backend (e.g., S3-Glacier, Azure Immutable Blob) by satisfying the `EternalStorageProvider` protocol without depending on the reference IPFS/Arweave implementation.
- The spec can be versioned independently of backend availability or cost structure.

## The Three Exported Types

### `EternalStorageProvider`
The backend contract: `archive()`, `retrieve()`, and `verify()` async methods plus a `tier_name` property. See `spec/eternal/protocol.py` for the full definition.

### `ArchiveResult`
A Pydantic model capturing what happened after archiving: the storage tier used (`"ipfs"`, `"arweave"`), the content reference (CID, transaction ID), whether the storage is permanent, cost, and timestamp. Callers log this and store the `reference` for later recovery.

### `RecoverySource`
Describes one known location from which a soul can be recovered — tier name, reference string, availability flag, and last-verified timestamp. The soul's manifest can list multiple `RecoverySource` entries so recovery survives a single network going offline.

## Data Flow

```
Soul archive request
  └─ EternalStorageProvider.archive(soul_bytes, soul_id)
       └─ ArchiveResult (tier, reference, url, permanent)
            └─ stored in soul manifest as RecoverySource
                 └─ EternalStorageProvider.verify(reference) -> bool
```

## Known Gaps

None in this init. The spec deliberately keeps it minimal — three exports, no logic.