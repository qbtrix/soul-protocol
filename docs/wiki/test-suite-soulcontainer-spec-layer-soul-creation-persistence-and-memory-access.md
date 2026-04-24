---
{
  "title": "Test Suite: SoulContainer — Spec-Layer Soul Creation, Persistence, and Memory Access",
  "summary": "Validates the spec-layer `SoulContainer` — the lightweight soul abstraction for integrations that do not need the full runtime. The suite covers container construction, traits storage, `.soul` file save/open round-trips, multi-layer memory preservation, error handling for missing files, and the default `DictMemoryStore`.",
  "concepts": [
    "SoulContainer",
    "SoulContainer.create",
    "SoulContainer.open",
    "SoulContainer.save",
    "DictMemoryStore",
    "MemoryStore",
    "MemoryEntry",
    "Identity",
    "traits",
    "soul file",
    "spec layer",
    "round-trip"
  ],
  "categories": [
    "testing",
    "spec layer",
    "soul persistence",
    "memory store",
    "test"
  ],
  "source_docs": [
    "f974dc7a037bc298"
  ],
  "backlinks": null,
  "word_count": 464,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`SoulContainer` is the spec-layer entry point for Soul Protocol. It is intentionally simpler than the runtime `Soul` class — no psychology pipeline, no LLM integration, no async — just a portable container for identity and layered memories. It targets integrations and language ports that need soul persistence without the full runtime stack. These tests pin that minimal contract.

## Construction

```python
def test_create_basic():
    soul = SoulContainer.create("Aria")
    assert soul.name == "Aria"
    assert soul.id is not None
    assert len(soul.id) == 12
```

The 12-character hex ID (same format as `Identity.id`) provides a unique, human-readable identifier without requiring a full DID. Traits default to an empty dict when omitted — preventing `AttributeError` on `soul.identity.traits["role"]` in code that checks traits conditionally.

## Properties vs. Identity

```python
def test_name_and_id():
    assert soul.name == soul.identity.name
    assert soul.id == soul.identity.id
```

The `name` and `id` properties are convenience accessors that delegate to the underlying `Identity` object. Testing this prevents a refactor from accidentally breaking the shorthand properties while the underlying identity remains correct.

## Save and Open Round-Trip

```python
def test_save_and_open(tmp_path):
    soul = SoulContainer.create("Aria", traits={"role": "assistant"})
    soul.memory.store("episodic", MemoryEntry(content="hello world"))
    soul.save(path)
    restored = SoulContainer.open(path)
    assert restored.name == soul.name
    assert restored.id == soul.id
    assert restored.identity.traits == soul.identity.traits
    recalled = restored.memory.recall("episodic")
    assert recalled[0].content == "hello world"
```

The round-trip test is the most critical: it proves that `.soul` files preserve both identity metadata and memory content. Without this, a container save/open cycle would silently drop memories or traits, making persistence unreliable.

`test_save_and_open_multiple_memories` verifies that multiple memories across multiple layers (episodic, semantic) are all preserved — not just the first one. This prevents bugs where only the last written memory is serialized.

## Error Handling

```python
def test_open_nonexistent_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        SoulContainer.open("/tmp/does_not_exist_abc123.soul")
```

Explicit `FileNotFoundError` is better than a raw OS error or a silent None return, because callers can catch it specifically and present a user-friendly message. The test locks the error type so a refactor cannot accidentally change it to a generic `Exception`.

`test_save_overwrites_existing_file` verifies that saving to an existing path silently replaces it — no error, no versioning. This behavior matters for update workflows where the same path is reused across sessions.

## Memory Store

The `.memory` property returns a `MemoryStore` instance (abstract type). The default concrete type is `DictMemoryStore` — an in-memory dict-backed store. Testing both the abstract type and the concrete type ensures:
- The property satisfies the `MemoryStore` protocol (for duck-typing compatibility)
- The default is `DictMemoryStore` (not None, not a different implementation)

## Known Gaps

No TODO or FIXME markers. There is no test for creating a `SoulContainer` with a custom `MemoryStore` implementation — the alternative constructor path is not covered. There is also no test for what happens when a `.soul` file is corrupted (truncated, invalid zip) — the `open()` error path for malformed files is untested.