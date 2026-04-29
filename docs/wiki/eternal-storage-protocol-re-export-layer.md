---
{
  "title": "Eternal Storage Protocol Re-Export Layer",
  "summary": "A thin compatibility shim that re-exports the three canonical eternal storage types — `EternalStorageProvider`, `ArchiveResult`, and `RecoverySource` — from the spec layer into the runtime package. It exists so callers already importing from `soul_protocol.runtime.eternal.protocol` continue to work after those definitions were moved to `soul_protocol.spec.eternal.protocol`.",
  "concepts": [
    "EternalStorageProvider",
    "ArchiveResult",
    "RecoverySource",
    "eternal storage",
    "protocol re-export",
    "backwards compatibility",
    "spec-runtime separation",
    "soul archive",
    "storage provider interface"
  ],
  "categories": [
    "eternal-storage",
    "architecture",
    "compatibility"
  ],
  "source_docs": [
    "bb8184085feba3e8"
  ],
  "backlinks": null,
  "word_count": 295,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`eternal/protocol.py` is a deliberate backwards-compatibility bridge. When the Soul Protocol codebase was restructured to separate spec (canonical type definitions) from runtime (execution logic), the eternal storage interfaces were moved from `soul_protocol.runtime` into `soul_protocol.spec.eternal.protocol`. Without this shim, every existing import would break.

Rather than grep-replace every callsite, the team placed re-exports at the old location. This is a common Python refactoring pattern — keep the old path alive while consolidating truth in one place.

## What Gets Re-Exported

```python
from soul_protocol.spec.eternal.protocol import (
    ArchiveResult,
    EternalStorageProvider,
    RecoverySource,
)

__all__ = ["EternalStorageProvider", "ArchiveResult", "RecoverySource"]
```

- **`EternalStorageProvider`** — the abstract base protocol all storage backends must implement. Defines `archive()`, `retrieve()`, and `verify()` async methods plus the `tier_name` property.
- **`ArchiveResult`** — a Pydantic model returned from `archive()`. Carries the storage reference (CID, tx ID, path), cost estimate, permanence flag, timestamp, and tier name.
- **`RecoverySource`** — a model used during soul recovery to track which storage tier a recovered copy came from and its confidence level.

## Data Flow

Callers import from `soul_protocol.runtime.eternal.protocol` → shim transparently delegates to `soul_protocol.spec.eternal.protocol` → actual type definitions are returned. Zero logic lives here.

## Why This Matters for Soul Architecture

The eternal storage layer is a core pillar of the Soul Protocol's durability guarantee. A soul that can only live on one machine is fragile — platform migration and recovery both depend on being able to archive and retrieve the soul from an external, persistent store. The protocol types here define the contract every storage backend (local, IPFS, Arweave, blockchain) must satisfy.

## Known Gaps

None. This module is intentionally minimal. The only risk would be if the spec location changes again — at that point this shim would need to be updated to point to the new canonical path.