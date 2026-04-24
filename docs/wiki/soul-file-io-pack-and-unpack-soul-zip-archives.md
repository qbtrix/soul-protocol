---
{
  "title": "Soul File I/O — Pack and Unpack .soul Zip Archives",
  "summary": "This module provides `pack_soul`, `unpack_soul`, and `unpack_to_container` — the three functions that serialize and deserialize a soul's identity and memories to and from the `.soul` zip archive format. It depends only on stdlib (`zipfile`, `json`, `io`) and the spec-layer models, keeping the archival format fully portable.",
  "concepts": [
    "pack_soul",
    "unpack_soul",
    "unpack_to_container",
    ".soul file",
    "zip archive",
    "soul portability",
    "memory serialization",
    "DictMemoryStore",
    "manifest.json",
    "identity.json",
    "layer"
  ],
  "categories": [
    "soul format",
    "spec layer",
    "archival",
    "serialization"
  ],
  "source_docs": [
    "4241582ec82bbaa9"
  ],
  "backlinks": null,
  "word_count": 449,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

A soul must be portable. The `.soul` file format is the transport container — a zip archive that any platform can produce or consume without framework-specific dependencies. `soul_file.py` is the canonical implementation of pack/unpack at the spec layer.

## Archive Layout

```
mysoul.soul (zip, DEFLATE compressed)
├── manifest.json     # format_version, soul_id, stats
├── identity.json     # name, traits, bonds
└── memory/
    ├── episodic.json
    ├── semantic.json
    └── procedural.json
```

One JSON file per memory layer. There is no fixed set of layer names — whatever layers exist in the `MemoryStore` at pack time are serialized.

## `pack_soul`

```python
def pack_soul(
    identity: Identity,
    memory_store: MemoryStore,
    *,
    manifest: dict[str, Any] | None = None,
) -> bytes:
```

Builds the zip in memory (`io.BytesIO`) and returns raw bytes. Key design choices:

- **No file I/O**: returns bytes, not a file path. Callers decide where to write — disk, eternal storage, HTTP response. This keeps the function testable without tmp files.
- **`manifest` override dict**: extra fields in the manifest override dict are applied to known `Manifest` fields if they match, or merged into `stats` if they don't. This lets the calling runtime inject export tool version, custom tags, etc. without schema changes.
- **`limit=999_999` on recall**: fetches all memories from each layer. The large limit is a practical "give me everything" sentinel rather than a true max — production backends with millions of entries would need pagination here.

## `unpack_soul`

```python
def unpack_soul(data: bytes) -> tuple[Identity, dict[str, list[dict[str, Any]]]]:
```

Returns a raw tuple of `(Identity, layers_dict)`. Raises `ValueError` if `identity.json` is missing — identity is the minimum viable soul. `manifest.json` is not checked here (it is advisory metadata, not required for functional unpack).

Layer files are found by prefix scan (`name.startswith("memory/") and name.endswith(".json")`). Empty layer names are skipped. This tolerates future additions to the archive layout (new top-level files, subdirectories) without breaking.

## `unpack_to_container`

```python
def unpack_to_container(data: bytes) -> tuple[Identity, DictMemoryStore]:
```

Convenience wrapper that hydrates raw layer dicts into a populated `DictMemoryStore`. Callers that want a working in-memory soul immediately after unpack use this; callers that want to populate a custom backend call `unpack_soul` and iterate the layers themselves.

## Data Flow

```
MemoryStore + Identity
  └─ pack_soul() -> bytes
       └─ EternalStorageProvider.archive(bytes)
            └─ ... time passes ...
                 └─ EternalStorageProvider.retrieve(reference) -> bytes
                      └─ unpack_to_container(bytes) -> (Identity, DictMemoryStore)
                           └─ soul is live again
```

## Known Gaps

- `limit=999_999` in `pack_soul` is a workaround. For production souls with large episodic stores, this could load millions of records into memory before writing the zip. A paginated streaming approach would be needed at scale.
- `checksum` in the manifest is not populated during pack — the integrity field exists but is left empty.