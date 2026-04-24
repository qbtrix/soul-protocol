---
{
  "title": "Soul Manifest — Archive Metadata Header for .soul Files",
  "summary": "The `Manifest` model defines the `manifest.json` file stored at the root of every `.soul` zip archive. It captures format version, soul identity, creation timestamp, an integrity checksum placeholder, and an open `stats` dict for runtime-specific metadata like memory counts and layer names.",
  "concepts": [
    "Manifest",
    "format_version",
    "soul_id",
    "soul_name",
    "checksum",
    "stats",
    "soul archive",
    ".soul file",
    "manifest.json",
    "zip archive",
    "integrity"
  ],
  "categories": [
    "soul format",
    "spec layer",
    "archival",
    "manifest"
  ],
  "source_docs": [
    "14ef472717648e2c"
  ],
  "backlinks": null,
  "word_count": 391,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

When a `.soul` file is passed between platforms or stored in eternal storage, the receiving system needs to verify its contents before unpacking. The manifest provides a machine-readable header — analogous to a zip file's central directory — that answers three questions without reading the full archive:

1. **Is this a valid `.soul` file?** (`format_version` check)
2. **Whose soul is this?** (`soul_id`, `soul_name`)
3. **What does it contain?** (`stats` with memory counts and layer names)

## Model Definition

```python
class Manifest(BaseModel):
    format_version: str = "1.0.0"
    soul_id: str = ""
    soul_name: str = ""
    created: datetime
    checksum: str = ""
    stats: dict[str, Any] = Field(default_factory=dict)
```

### `format_version`
Defaults to `"1.0.0"`. Future breaking changes to the `.soul` archive layout bump this. Receiving platforms check this field before attempting to parse the archive — an incompatible version surfaces a clear error rather than a cryptic deserialization failure.

### `soul_id` and `soul_name`
Duplicated here from `identity.json` so the manifest is self-contained. A system processing batches of soul archives can route or display them using only the manifest without reading the full identity file.

### `checksum`
Currently a placeholder (defaults to empty string). The field exists so the schema includes a checksum slot from v1.0.0, preventing a later addition from being a breaking change. Once integrity verification is implemented, this will hold a SHA-256 hash of the archive contents.

### `stats`
An open dict for runtime-specific metadata. The `pack_soul()` function populates it with:

```python
stats = {
    "total_memories": <count>,
    "layers": ["episodic", "semantic", ...]
}
```

Runtimes can add additional keys (export tool version, archival timestamp, custom counters) without schema changes. The spec treats `stats` as opaque.

## How It Fits in the Archive

```
mysoul.soul (zip)
├── manifest.json     ← Manifest model (this file)
├── identity.json     ← Identity model
└── memory/
    ├── episodic.json
    ├── semantic.json
    └── procedural.json
```

`manifest.json` is always at the archive root. `pack_soul()` writes it first so it appears at the beginning of the zip's central directory, making it easy to read without seeking.

## Data Flow

```
pack_soul(identity, memory_store)
  └─ Manifest(soul_id=identity.id, stats={"total_memories": n})
       └─ manifest.model_dump_json() -> "manifest.json" in zip
            └─ EternalStorageProvider.archive(zip_bytes)
                 └─ manifest.json read first on unpack to validate
```

## Known Gaps

- `checksum` is an empty string placeholder. Integrity verification is not yet implemented — archives can be corrupted or tampered with without detection at the spec layer.