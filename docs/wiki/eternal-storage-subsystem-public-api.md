---
{
  "title": "Eternal Storage Subsystem Public API",
  "summary": "The `eternal` subpackage `__init__.py` re-exports the four public symbols from the eternal storage subsystem: `EternalStorageProvider`, `EternalStorageManager`, `ArchiveResult`, and `RecoverySource`. This clean facade hides the internal module layout and provides a single import target for callers persisting soul data to permanent storage.",
  "concepts": [
    "eternal storage",
    "EternalStorageManager",
    "EternalStorageProvider",
    "ArchiveResult",
    "RecoverySource",
    "IPFS",
    "Arweave",
    "soul portability",
    "permanent storage",
    "content addressing"
  ],
  "categories": [
    "eternal storage",
    "soul portability",
    "package structure"
  ],
  "source_docs": [
    "e1d96b183ab61ea4"
  ],
  "backlinks": null,
  "word_count": 284,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

"Eternal storage" in Soul Protocol refers to permanent, content-addressed storage backends — specifically Arweave and IPFS — where soul data can be archived for long-term preservation and cross-platform portability. This `__init__.py` is the front door to that subsystem.

## Exported Symbols

```python
from .manager import EternalStorageManager
from .protocol import ArchiveResult, EternalStorageProvider, RecoverySource

__all__ = [
    "ArchiveResult",
    "EternalStorageProvider",
    "EternalStorageManager",
    "RecoverySource",
]
```

### EternalStorageProvider
The protocol (interface) that storage backends implement. Any backend (IPFS, Arweave, S3, mock) satisfying this interface can be registered with the manager.

### EternalStorageManager
Orchestrates multiple providers — registers them by tier name, fans out archive operations across tiers, and tries providers in order during recovery. This is the main class callers instantiate.

### ArchiveResult
Returned by `archive()` operations. Contains the permanent reference (content hash / URL) and success status for a single tier's archive attempt.

### RecoverySource
A descriptor for a stored soul — tier name, permanent reference, and availability flag. Used as input to `recover()` to try retrieving soul data from a specific location.

## Subpackage Structure

The eternal storage subsystem consists of:
- `protocol.py` — Protocol and data model definitions
- `manager.py` — `EternalStorageManager` implementation
- `providers/` — Concrete backend implementations (mock IPFS, mock Arweave, and real implementations in progress)

This `__init__.py` surfaces only what external callers need; the `providers/` subpackage is imported internally.

## Usage Pattern

```python
from soul_protocol.runtime.eternal import EternalStorageManager

mgr = EternalStorageManager.with_mocks()  # for testing
results = await mgr.archive(soul_bytes, soul_id="did:soul:abc123")
sources = await mgr.get_recovery_sources("did:soul:abc123")
recovered = await mgr.recover(sources)
```

## Known Gaps

No TODOs or FIXMEs in this file. The real IPFS and Arweave provider implementations are in the `providers/` subdirectory; the module was created with mock providers that exercise the full interface.