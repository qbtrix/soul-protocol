<!-- RFC-004-SOUL-FILE-FORMAT.md — Defines the .soul file format specification: ZIP archive -->
<!-- structure, manifest format, JSON schemas, pack/unpack operations, and versioning. -->

# RFC-004: Soul File Format

**Status:** Draft -- Open for feedback
**Author:** Soul Protocol Community
**Date:** 2026-03-08

## Summary

The `.soul` file format is a ZIP archive containing JSON files that represent a
complete, portable AI identity. Rename it to `.zip` and open it with any archive tool.
Move it between platforms. Back it up anywhere. Version it in git. The format is
designed for maximum interoperability -- any language that can read ZIP and JSON can
read a soul.

This RFC documents the archive layout, the manifest format, the JSON schemas for
cross-language validation, the pack/unpack API, and versioning strategy.

## Problem Statement

AI companion state is typically locked inside proprietary databases, platform-specific
formats, or opaque binary blobs. Users cannot:

1. Export their companion's complete state (memory, personality, bonds)
2. Import a companion into a different platform
3. Back up a companion to standard storage
4. Inspect what their companion knows (transparency)
5. Share a companion template with others

A portable, human-inspectable file format solves all five problems.

## Proposed Solution

### File Format: ZIP + JSON

A `.soul` file is a standard ZIP archive (deflated) containing JSON files. The format
is defined at two levels:

**Spec layer** (minimal): `manifest.json` + `identity.json` + `memory/{layer}.json`

**Runtime layer** (full): adds `soul.json`, `state.json`, `dna.md`, and additional
memory files for the five-tier architecture.

### Spec-Layer Archive Layout

The spec defines the minimal valid `.soul` archive:

```
soul.zip (ZIP_DEFLATED)
+-- manifest.json         # Format version, soul metadata, stats
+-- identity.json         # Soul identity (name, id, traits, created_at)
+-- memory/
    +-- {layer_name}.json # One file per memory layer (list of MemoryEntry)
```

This is implemented in `spec/soul_file.py`:

```python
def pack_soul(identity: Identity, memory_store: MemoryStore,
              *, manifest: dict[str, Any] | None = None) -> bytes:
    """Pack a soul into a .soul file (zip archive)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_model.model_dump_json(indent=2))
        zf.writestr("identity.json", identity.model_dump_json(indent=2))
        for layer_name, entries in layer_data.items():
            zf.writestr(f"memory/{layer_name}.json",
                        json.dumps(entries, indent=2, default=str))
    return buf.getvalue()
```

### Runtime Archive Layout (Full)

The runtime exports a richer archive structure:

```
name.soul (ZIP_DEFLATED)
+-- manifest.json              # SoulManifest: format version, dates, stats, eternal links
+-- soul.json                  # Full SoulConfig: identity, DNA, settings, evolution config
+-- dna.md                     # Human-readable personality blueprint (markdown)
+-- state.json                 # Current SoulState: mood, energy, focus, social battery
+-- memory/
    +-- core.json              # CoreMemory: persona text + bonded-entity profile
    +-- episodic.json          # List of MemoryEntry (episodic type, somatic markers)
    +-- semantic.json          # List of MemoryEntry (semantic facts, confidence scores)
    +-- procedural.json        # List of MemoryEntry (learned patterns)
    +-- graph.json             # KnowledgeGraph: entities + directed edges
    +-- self_model.json        # SelfModelManager: Klein domains + relationship notes
    +-- general_events.json    # List of GeneralEvent (Conway theme clusters)
```

### Manifest Format

The manifest provides metadata about the archive:

```python
class Manifest(BaseModel):
    format_version: str = "1.0.0"
    soul_id: str = ""
    soul_name: str = ""
    created: datetime = Field(default_factory=datetime.now)
    checksum: str = ""
    stats: dict[str, Any] = Field(default_factory=dict)
```

The runtime extends this with export timestamp, eternal storage links, and richer stats:

```json
{
  "format_version": "1.0.0",
  "soul_id": "did:soul:aria-7x8k2m",
  "soul_name": "Aria",
  "created": "2026-03-01T10:00:00",
  "exported": "2026-03-08T14:30:00",
  "checksum": "sha256:abcdef...",
  "stats": {
    "total_memories": 847,
    "layers": ["core", "episodic", "semantic", "procedural", "graph"],
    "interaction_count": 312
  },
  "eternal": {
    "ipfs": { "cid": "Qm...", "pinned_at": "2026-03-07T12:00:00" },
    "arweave": {},
    "blockchain": {}
  }
}
```

### Directory Format (.soul/ folder)

The same structure can exist as an unpacked directory on disk, created by `soul init`
or `soul.save_local()`:

```
.soul/
+-- soul.json
+-- dna.md
+-- state.json
+-- memory/
    +-- core.json
    +-- episodic.json
    +-- semantic.json
    +-- procedural.json
    +-- graph.json
    +-- self_model.json
    +-- general_events.json
```

### Pack/Unpack API

The spec provides three functions:

```python
def pack_soul(identity, memory_store, *, manifest=None) -> bytes:
    """Pack into a .soul ZIP archive. Returns raw bytes."""

def unpack_soul(data: bytes) -> tuple[Identity, dict[str, list[dict]]]:
    """Unpack into Identity + raw layer dicts."""

def unpack_to_container(data: bytes) -> tuple[Identity, DictMemoryStore]:
    """Unpack into Identity + populated DictMemoryStore."""
```

And the `SoulContainer` class provides a high-level API:

```python
soul = SoulContainer.create("Aria", traits={"role": "assistant"})
soul.memory.store("episodic", MemoryEntry(content="Hello!", layer="episodic"))
soul.save("aria.soul")

soul = SoulContainer.open("aria.soul")
memories = soul.memory.recall("episodic", limit=5)
```

### JSON Schemas for Cross-Language Validation

The `schemas/` directory contains JSON Schema files auto-generated from the Pydantic
models. These enable validation in any language:

- `soul-protocol.schema.json` -- root schema
- `SoulManifest.schema.json` -- manifest validation
- `Identity.schema.json` -- identity with Bond sub-schema
- `MemoryEntry.schema.json` -- memory entry validation
- `SoulConfig.schema.json` -- full config validation
- `SoulState.schema.json` -- state snapshot validation
- `Personality.schema.json`, `DNA.schema.json`, `CommunicationStyle.schema.json`
- `SomaticMarker.schema.json`, `SignificanceScore.schema.json`
- And 12 more for supporting types

A TypeScript, Rust, or Go implementation can validate `.soul` files against these
schemas without importing any Python code.

### Versioning

The `format_version` field in the manifest uses semver. The current version is `1.0.0`.

- **Patch** (1.0.x): additive changes to `stats` or `metadata` dicts
- **Minor** (1.x.0): new optional files in the archive (e.g., `memory/working.json`)
- **Major** (x.0.0): breaking changes to required file structure or field names

Readers should tolerate unknown files in the archive (forward compatibility).

## Implementation Notes

- Spec pack/unpack: `src/soul_protocol/spec/soul_file.py`
- Spec manifest: `src/soul_protocol/spec/manifest.py`
- Spec container: `src/soul_protocol/spec/container.py`
- Runtime export: `src/soul_protocol/runtime/export/pack.py`, `unpack.py`
- Runtime file storage: `src/soul_protocol/runtime/storage/file.py`
- JSON schemas: `schemas/*.schema.json` (22 files)
- CLI commands: `soul export`, `soul inspect`, `soul migrate`

## Alternatives Considered

**SQLite-based format.** SQLite is a great application file format (used by Apple's
Core Data, Android, and many others). However, it's less human-inspectable than
JSON-in-ZIP and requires SQLite bindings in every target language.

**Protocol Buffers / MessagePack.** Binary formats offer smaller file sizes and faster
parsing, but sacrifice human readability. The ability to rename `.soul` to `.zip` and
browse the contents is a significant UX advantage.

**Single JSON file.** Simpler, but doesn't scale for souls with thousands of memories.
The ZIP format allows individual memory files to be read/written independently.

**HDF5 or Parquet.** Overkill for the data sizes involved and adds heavy dependencies.

## Open Questions

1. **Compression.** The archive uses ZIP_DEFLATED. Should individual JSON files also
   be compressed (e.g., gzipped before adding to the archive)? For large episodic
   stores (10K+ entries), double compression could reduce file size significantly.

2. **Encryption.** Should the format support encrypted `.soul` files natively? The
   runtime already has `crypto/encrypt.py` with Fernet encryption. Should encrypted
   archives use a different extension (`.soul.enc`) or store encryption metadata in
   the manifest?

3. **Maximum file size.** Should the spec define a maximum `.soul` file size? A soul
   with 10,000 episodic memories, 1,000 semantic facts, and a knowledge graph could
   reach tens of megabytes. Is there a point where a different storage strategy
   (external database + reference) is more appropriate?

4. **Streaming reads.** For very large souls, should the format support reading
   individual files from the archive without loading the entire ZIP into memory?
   Python's zipfile module supports this, but the current API reads everything at once.

5. **Digital signatures.** Should the manifest include a cryptographic signature to
   verify the archive hasn't been tampered with? This would enable trust chains for
   soul migration between platforms.

## References

- [ZIP File Format Specification](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT)
- [JSON Schema Specification](https://json-schema.org/specification)
- [Semantic Versioning 2.0.0](https://semver.org/)
- `src/soul_protocol/spec/soul_file.py` -- pack/unpack implementation
- `src/soul_protocol/spec/container.py` -- SoulContainer high-level API
- `schemas/` -- 22 JSON Schema files for cross-language validation
