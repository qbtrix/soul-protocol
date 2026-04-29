---
{
  "title": "Storage Subpackage Public Interface",
  "summary": "The `storage/__init__.py` re-exports all public storage symbols — `StorageProtocol`, `FileStorage`, `InMemoryStorage`, and the persistence functions `save_soul`, `load_soul`, `save_soul_full`, and `load_soul_full` — from a single stable import path. A `save_soul_full` addition in 2026-02-22 corrected the earlier API's silent memory-tier data loss.",
  "concepts": [
    "StorageProtocol",
    "FileStorage",
    "InMemoryStorage",
    "save_soul_full",
    "load_soul_full",
    "storage backend",
    "persistence",
    "subpackage facade",
    "deprecation"
  ],
  "categories": [
    "runtime",
    "storage",
    "persistence"
  ],
  "source_docs": [
    "d23e268f04e2bdac"
  ],
  "backlinks": null,
  "word_count": 438,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The storage subpackage provides all persistence backends for the soul runtime. The `__init__.py` aggregates symbols from three internal modules into a single, stable import surface:

- `storage/protocol.py` — the `StorageProtocol` interface all backends must satisfy
- `storage/file.py` — `FileStorage` (filesystem backend) and full-persistence convenience functions
- `storage/memory_store.py` — `InMemoryStorage` (dict-backed, for tests and ephemeral use)

## Public Exports

```python
from soul_protocol.runtime.storage import (
    StorageProtocol,   # the interface all backends implement
    FileStorage,       # filesystem-backed backend
    InMemoryStorage,   # in-memory backend (testing)
    save_soul,         # deprecated: config only, no memory tiers
    load_soul,         # load from a specific directory path
    save_soul_full,    # save config + all 7 memory tiers atomically
    load_soul_full,    # load config + all 7 memory tiers
)
```

## API Evolution: The Memory Tier Gap

The module header documents two significant additions:

1. **Runtime restructure** — absolute import paths were corrected from a previous internal layout. The facade absorbed this change without touching any consumer code.
2. **Full memory persistence** — `save_soul_full` and `load_soul_full` were added when it became clear that the earlier `save_soul` was silently discarding all memory tier data. A soul saved with the old API would lose every episodic, semantic, and procedural memory on the next load — a silent, catastrophic data loss that was only visible when memories failed to appear after a restart.

The deprecated `save_soul()` now emits `DeprecationWarning` at `stacklevel=2` so the warning points to the caller rather than to the storage module.

## Choosing the Right Function

| Function | Use When |
|----------|----------|
| `save_soul_full` | Always — persists config + all 7 memory tiers atomically |
| `load_soul_full` | Always — loads config + memory dict |
| `save_soul` | Deprecated. Emits `DeprecationWarning`. Avoid for new code |
| `load_soul` | Reading a directory with only `soul.json` (legacy souls without memory tiers) |
| `FileStorage.save/load` | When you need fine-grained control over soul ID and base path |
| `InMemoryStorage` | Unit tests and short-lived ephemeral processes |

## Why a Flat Re-Export

The alternative — requiring callers to import from `soul_protocol.runtime.storage.file` directly — would couple external code to the internal module structure. If `FileStorage` were ever moved to a different internal module (e.g., during a backend plugin refactor), every caller would need updating. The facade at `__init__.py` prevents this.

## Relationship to the CLI

The `soul` CLI commands (`soul save`, `soul load`, `soul status`) all import from this facade. Because the facade is stable, the CLI is decoupled from internal storage implementation details.

## Known Gaps

No known gaps. The deprecation path for `save_soul` is in place and documented in both the source header and the `DeprecationWarning` message.