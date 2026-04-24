---
{
  "title": "Export Subpackage: Soul Archive I/O Interface",
  "summary": "The `export/__init__.py` init exposes `pack_soul` and `unpack_soul` as the sole public interface for `.soul` archive I/O, hiding the internal split between `pack.py` and `unpack.py`. All callers that need to serialize or deserialize a soul use this single import point.",
  "concepts": [
    "pack_soul",
    "unpack_soul",
    "soul archive",
    "export subpackage",
    "import boundary",
    "ZIP archive",
    "soul I/O",
    "SoulConfig"
  ],
  "categories": [
    "export",
    "package-structure",
    "soul-lifecycle"
  ],
  "source_docs": [
    "b6d9b6107b4a9177"
  ],
  "backlinks": null,
  "word_count": 200,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`export/__init__.py` is the public boundary of the export subsystem. It exists so callers write:

```python
from soul_protocol.runtime.export import pack_soul, unpack_soul
```

...rather than importing from the underlying modules directly. This creates a stable API surface — the internal split between `pack.py` and `unpack.py` is an implementation detail that could be reorganized without affecting any consumer.

## What Gets Exposed

```python
from soul_protocol.runtime.export.pack import pack_soul
from soul_protocol.runtime.export.unpack import unpack_soul

__all__ = ["pack_soul", "unpack_soul"]
```

- **`pack_soul(config, memory_data, *, password)`** — Serialize a `SoulConfig` plus optional memory tiers into a `.soul` ZIP archive. Supports optional AES-256-GCM encryption.
- **`unpack_soul(data, *, password)`** — Deserialize a `.soul` ZIP archive back into a `(SoulConfig, memory_data)` tuple. Handles both encrypted and unencrypted archives.

These two functions are the core I/O primitives of the entire Soul Protocol runtime. Every `awaken()`, `export()`, `retire()`, and migration operation passes through one of them.

## Design Rationale

The pack/unpack split was intentional: packing and unpacking have different error modes, different dependencies, and different test scenarios. Keeping them in separate files makes each easier to test and reason about in isolation. The init then stitches them into a coherent `export` API.

## Known Gaps

None. This module is intentionally minimal.