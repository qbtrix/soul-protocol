---
{
  "title": "Test Suite for Soul File Pack, Unpack, and Container Helpers",
  "summary": "This test suite validates the `.soul` archive format's core serialization functions: `pack_soul()`, `unpack_soul()`, and the `unpack_to_container()` convenience helper. It verifies identity and memory fidelity across the binary zip roundtrip, multi-layer preservation, empty-store edge cases, and robust error handling for malformed or incomplete archives.",
  "concepts": [
    "pack_soul",
    "unpack_soul",
    "unpack_to_container",
    ".soul file",
    "zip archive",
    "identity preservation",
    "memory layers",
    "DictMemoryStore",
    "soul portability",
    "roundtrip fidelity"
  ],
  "categories": [
    "testing",
    "soul-format",
    "serialization",
    "spec",
    "test"
  ],
  "source_docs": [
    "cdb3b16420bfbd04"
  ],
  "backlinks": null,
  "word_count": 561,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `.soul` file is the portable binary format for transferring AI companion identity across platforms. It is a zip archive containing `identity.json`, `manifest.json`, and per-layer memory files. The pack/unpack functions are the boundary where in-memory Python objects become transportable bytes — every correctness failure here means data loss or a rejection on the receiving platform.

## Roundtrip Fidelity

### Identity Preservation

`test_pack_unpack_roundtrip` is the primary regression test. It packs an identity plus a single episodic memory, then unpacks and asserts all identity fields survive:

```python
data = pack_soul(identity, store)
restored_identity, layers = unpack_soul(data)
assert restored_identity.id == identity.id
assert restored_identity.name == identity.name
assert restored_identity.traits == identity.traits
```

The `id` field is explicitly tested because it is auto-generated at construction time — if the pack function accidentally re-generates an ID on unpack, the soul would lose its persistent DID-based identity.

### Multi-Layer Memory Preservation

`test_pack_with_layers` seeds three layers (`episodic`, `semantic`, `procedural`) and confirms all survive the roundtrip:

```python
assert set(layers.keys()) == {"episodic", "semantic", "procedural"}
assert layers["procedural"][0]["content"] == "how to make tea"
```

This matters because the most common failure mode for zip-based formats is that only the first or last item in an iterable is written. Testing three distinct layers with distinct content catches both off-by-one and key-collision bugs.

### Empty Memory Store

`test_pack_empty_memory` confirms that packing a soul with no memories produces a valid, parseable archive with an empty layers dict — not a crash, not a corrupt zip, not an archive missing `identity.json`:

```python
data = pack_soul(identity, store)
restored_identity, layers = unpack_soul(data)
assert layers == {}
```

This is critical for new soul provisioning, where a freshly created companion has identity but no memories yet.

## Container Helper

`unpack_to_container()` is a higher-level alternative to `unpack_soul()` that returns a `DictMemoryStore` instead of raw layer dicts. This saves callers from manually reconstructing a store object:

```python
restored_identity, restored_store = unpack_to_container(data)
recalled = restored_store.recall("episodic")
assert len(recalled) == 2
```

The test also checks that layer names are correctly mapped to the store, not just content — `set(restored_store.layers()) == {"semantic", "working"}`. A bug here would cause silent layer collisions or incorrect tiered recall.

## Error Handling

### Invalid Archive

`test_unpack_invalid_raises_value_error` feeds random bytes to `unpack_soul()` and expects a `ValueError` or an `Exception`. The broad catch is intentional — the spec requires failure to be explicit, but does not constrain the exact exception type when the input is not even a valid zip.

### Missing identity.json

`test_unpack_missing_identity_raises_value_error` constructs a valid zip containing only `manifest.json` and asserts a `ValueError` with a message matching `"identity.json"`. This is the expected behavior when a soul archive was assembled incorrectly — the error message must identify the missing file so the operator knows what went wrong:

```python
with pytest.raises(ValueError, match="identity.json"):
    unpack_soul(buf.getvalue())
```

### Output Type Check

`test_pack_produces_bytes` asserts that `pack_soul()` returns `bytes`, not a string or file handle. This prevents subtle bugs where downstream code passes the result to an API expecting a binary payload.

## Known Gaps

- There is no test for what happens when `identity.json` is present but malformed (invalid JSON). The error path for a corrupt identity file is not covered.
- `manifest.json` content is not validated on unpack — a missing or wrong-version manifest does not appear to raise an error.
- Layer file naming conventions inside the zip are not tested — callers assume a specific naming scheme but no test enforces it.