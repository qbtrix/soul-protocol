---
{
  "title": "Test Suite for MemoryEntry, MemoryStore Protocol, and DictMemoryStore",
  "summary": "This test suite validates the core in-memory building blocks of Soul Protocol's spec-level memory system: the `MemoryEntry` data model, the `MemoryStore` protocol interface, and the `DictMemoryStore` reference implementation. Tests cover entry creation, metadata handling, layer isolation, BM25-style search, delete semantics, and ordering guarantees.",
  "concepts": [
    "MemoryEntry",
    "DictMemoryStore",
    "MemoryStore",
    "memory layers",
    "episodic memory",
    "semantic memory",
    "BM25 search",
    "recall ordering",
    "layer isolation",
    "protocol compliance",
    "token overlap"
  ],
  "categories": [
    "testing",
    "memory-system",
    "spec",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "3adf70195b68fac6"
  ],
  "backlinks": null,
  "word_count": 545,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The spec-level memory system defines a minimal, portable interface for storing and retrieving soul memories. `MemoryEntry` is the atomic unit; `MemoryStore` is a runtime-checkable protocol that any backend must satisfy; `DictMemoryStore` is the reference in-memory implementation used in tests and lightweight deployments.

## MemoryEntry Construction

### Auto-Generated Identifiers

Each `MemoryEntry` auto-generates a 12-character lowercase hex `id` and a `timestamp` on construction. The test validates both:

```python
entry = MemoryEntry(content="test content")
assert len(entry.id) == 12
assert all(c in "0123456789abcdef" for c in entry.id)
assert entry.timestamp is not None
```

This auto-generation prevents callers from accidentally creating duplicate or `None` IDs. The hex constraint is explicitly tested because future serialization layers may rely on the format being safe for filenames and JSON keys.

### Metadata Passthrough

Metadata is an open-ended dict. The test confirms arbitrary nested structures (list values, numeric keys) pass through without transformation. This flexibility is deliberate — memory backends should not impose schemas on caller-supplied context like importance scores or tags.

## DictMemoryStore Behaviors

### Layer Isolation

Memories stored in different named layers (`"episodic"`, `"semantic"`, `"procedural"`) are completely isolated:

```python
store.store("episodic", MemoryEntry(content="met Aria today"))
store.store("semantic", MemoryEntry(content="the sky is blue"))
epidosic = store.recall("episodic")  # returns only episodic entries
```

This prevents a common bug where a query for episodic events accidentally surfaces factual semantic memories, breaking the tiered memory architecture.

### Layer Mutation on Store

`store()` mutates `entry.layer` to match the target layer name. This side effect is tested explicitly to document that callers should not rely on `entry.layer` retaining its pre-store value:

```python
store.store("procedural", entry)
assert entry.layer == "procedural"
```

### Search by Token Overlap

`search()` performs BM25-style token overlap matching. The test seeds entries across layers and confirms that only entries with matching tokens are returned:

```python
results = store.search("cat mat")
assert any("cat" in c for c in [r.content for r in results])
assert not any("dogs" in c for c in [r.content for r in results])
```

### Delete Semantics

`delete()` returns `True` on success and `False` when the ID does not exist. The `False` path is tested separately to document that callers must not treat a missing delete as an error — idempotent deletes are a required property for eventual consistency across stores.

### Recall Ordering and Limits

`recall()` returns entries sorted newest-first. The test uses `time.sleep(0.01)` between stores to guarantee a detectable timestamp difference:

```python
recalled = store.recall("episodic")
assert recalled[0].content == "second"  # most recent first
```

The `limit` parameter is validated to prevent runaway memory allocation in large stores.

### Protocol Compliance Check

```python
assert isinstance(store, MemoryStore)
```

The `MemoryStore` is a `runtime_checkable` protocol. This test ensures `DictMemoryStore` satisfies it at runtime, which matters for any code that uses `isinstance` checks to validate backend compliance at injection points.

## Known Gaps

- `layers()` only lists layers with at least one entry. There is no test for what happens to a layer listing after its last entry is deleted via iteration — only direct single-entry deletion is covered.
- `search()` does not have tests for case sensitivity, punctuation handling, or Unicode content.
- `count()` with a nonexistent layer returns 0 rather than raising — this is the expected behavior but there is no test documenting that `recall()` on a nonexistent layer also returns an empty list rather than raising.