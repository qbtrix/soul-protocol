---
{
  "title": "Soul Archive Packer: Building .soul ZIP Archives",
  "summary": "`pack_soul` serializes a `SoulConfig` and all its memory tiers into a portable `.soul` ZIP archive, with optional AES-256-GCM encryption for every file except the manifest. It is the primary serialization primitive — every export, backup, and migration operation ultimately calls this function.",
  "concepts": [
    "pack_soul",
    "soul archive",
    "ZIP format",
    "SoulManifest",
    "SoulConfig",
    "memory tiers",
    "encryption",
    "dna.md",
    "manifest.json",
    "soul.json",
    "AES-256-GCM",
    "portable soul"
  ],
  "categories": [
    "export",
    "soul-lifecycle",
    "serialization",
    "security"
  ],
  "source_docs": [
    "bf7cef4a7f812b10"
  ],
  "backlinks": null,
  "word_count": 377,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The `.soul` format is a ZIP archive that bundles a soul's identity, personality (DNA), current state, and all memory tiers into a single portable file. `pack.py` implements the write side of that format.

A soul that only exists in memory is ephemeral. `pack_soul` converts it to bytes that can be saved to disk, archived to IPFS/Arweave, sent across a network, or migrated to a new platform.

## Archive Structure

```
soul.soul (ZIP)
├── manifest.json        ← always unencrypted — metadata
├── soul.json            ← full SoulConfig
├── dna.md               ← human-readable personality blueprint
├── state.json           ← current SoulState
└── memory/
    ├── core.json        ← CoreMemory (always loaded on awaken)
    ├── episodic.json    ← event memories
    ├── semantic.json    ← fact memories
    ├── procedural.json  ← skill memories
    ├── graph.json       ← relationship graph
    ├── self_model.json  ← self-awareness model
    └── general_events.json ← non-domain events
```

When encryption is enabled, each file (except `manifest.json`) gets a `.enc` extension and its contents are replaced with AES-256-GCM ciphertext.

## Encryption Design

```python
def _write(zf, name, content):
    raw = content.encode() if isinstance(content, str) else content
    if encrypting:
        zf.writestr(f"{name}.enc", encrypt_fn(raw, password))
    else:
        zf.writestr(name, raw)
```

The `_write` inner function is a closure that captures the `encrypting` flag and `encrypt_fn`. Every file write goes through it, so encryption is transparent to the rest of the packing logic. The manifest is written last with `zf.writestr("manifest.json", ...)` directly — bypassing `_write` to ensure it is never encrypted.

## Memory Tier Handling

Memory tiers are written only when `memory_data` is provided. If the caller passes `None`, only `memory/core.json` is written (from `config.core_memory`). This allows lightweight exports that don't carry the full episodic history.

## Manifest as Metadata Header

The `SoulManifest` is serialized last and always unencrypted. It stores:
- Format version, creation date, export date
- Soul ID (DID) and name
- Encrypted flag — critical for `unpack_soul` to know what to expect
- Stats: version, lifecycle, role

By keeping the manifest readable, any tool can inspect a `.soul` file's basic metadata without needing the password.

## Known Gaps

- `checksum: ""` — the manifest includes a checksum field but it is not populated. This means archive integrity cannot be verified without attempting a full unpack.
- Memory tiers with empty lists (`[]`) are still written to the archive, adding size without value.