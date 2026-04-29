---
{
  "title": "Test Suite for Soul Export and Pack/Unpack Operations",
  "summary": "Tests for the `.soul` zip archive format, covering the full pack/unpack roundtrip, required file inventory inside the archive, and memory tier data inclusion. Ensures that `SoulConfig` and memory content survive serialisation to bytes and back without loss.",
  "concepts": [
    "pack_soul",
    "unpack_soul",
    "soul file",
    "zip archive",
    "SoulConfig",
    "Identity",
    "DID",
    "memory tiers",
    "manifest.json",
    "soul.json",
    "dna.md",
    "roundtrip",
    "serialisation",
    "export"
  ],
  "categories": [
    "testing",
    "export",
    "file-format",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "80c88e9bb5751c02"
  ],
  "backlinks": null,
  "word_count": 314,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

A `.soul` file is a zip archive that bundles a soul's identity, DNA, state, and memory into a single portable artefact. `test_export.py` validates `pack_soul` and `unpack_soul` — the two functions that serialise and deserialise this format.

## Test Fixture

```python
@pytest.fixture
def config() -> SoulConfig:
    return SoulConfig(
        identity=Identity(
            name="Aria",
            did="did:soul:aria-abc123",
            archetype="The Compassionate Creator",
            core_values=["empathy", "creativity"],
        ),
    )
```

The fixture uses realistic values (a DID, an archetype, core values) rather than placeholder strings, making assertion failures immediately interpretable.

## Core Roundtrip Test

`test_pack_and_unpack_roundtrip` is the primary invariant: `pack_soul(config)` produces bytes, and `unpack_soul(bytes)` reconstructs the original `SoulConfig` exactly — name, DID, archetype, values, and version all match. The test also confirms that `memory_data` always contains a `"core"` key even when no explicit memory was supplied.

## Archive Inventory Test

`test_pack_contains_expected_files` opens the raw zip bytes and checks that these files are present:

```
manifest.json   — format version, soul ID
soul.json       — identity and config
dna.md          — personality traits in readable markdown
state.json      — runtime state
memory/core.json — core memory tier
```

This test exists because format changes could silently drop files, breaking consumers that depend on specific archive members.

## Memory Tier Tests

`test_pack_with_memory_data` passes an explicit `memory_data` dict containing entries for `core`, `episodic`, `semantic`, and `procedural` tiers, then verifies the archive contains the corresponding files. Without memory tier coverage, a bug that discards non-core tiers would go undetected.

`test_pack_unpack_roundtrip_with_memory` extends the basic roundtrip to full memory content, ensuring the entire five-tier memory architecture survives a serialisation cycle intact.

## Data Flow

```
SoulConfig + optional memory_data
    ↓  pack_soul()
bytes (zip archive)
    ↓  unpack_soul()
(SoulConfig, dict[tier -> data])
```

## Known Gaps

- No tests for corrupted or truncated archives (e.g. missing `manifest.json`).
- No tests for backwards compatibility — loading a `.soul` file produced by an older version of the library.
- Large memory payloads are not stress-tested; compression ratios are unchecked.