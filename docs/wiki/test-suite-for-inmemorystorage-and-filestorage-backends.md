---
{
  "title": "Test Suite for InMemoryStorage and FileStorage Backends",
  "summary": "This test suite validates both storage backends provided by Soul Protocol's runtime: `InMemoryStorage` (dict-backed, in-process) and `FileStorage` (disk-backed, directory-per-soul). It covers the full CRUD surface — save, load, delete, and list — with particular attention to idempotent delete behavior and the expected on-disk directory structure for `FileStorage`.",
  "concepts": [
    "InMemoryStorage",
    "FileStorage",
    "SoulConfig",
    "Identity",
    "DID",
    "async storage",
    "save",
    "load",
    "delete",
    "list_souls",
    "soul.json"
  ],
  "categories": [
    "testing",
    "storage",
    "persistence",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "a07bf56062e0d36c"
  ],
  "backlinks": null,
  "word_count": 519,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul Protocol's runtime requires a pluggable persistence layer so that soul data can be stored in different backends depending on deployment context — ephemeral in-process storage for tests and development, and file-backed storage for production CLI and desktop use. Both backends implement the same async protocol, tested here.

## Test Fixture

A shared `SoulConfig` fixture creates a minimal config with an `Identity` using a DID:

```python
@pytest.fixture
def config() -> SoulConfig:
    return SoulConfig(
        identity=Identity(name="Aria", did="did:soul:aria-abc123"),
    )
```

Using a DID in the fixture is intentional — the storage layer must preserve DID strings exactly, without normalization, since DIDs are the cross-platform identity anchor.

## InMemoryStorage

### Save and Load

```python
await store.save("aria", config)
loaded = await store.load("aria")
assert loaded.identity.name == "Aria"
assert loaded.identity.did == "did:soul:aria-abc123"
```

The load verifies both the name and the DID — confirming that nested Identity fields survive the in-memory serialization path.

### Idempotent Delete

```python
result = await store.delete("aria")   # True
loaded = await store.load("aria")      # None
result2 = await store.delete("aria")  # False — already gone
```

The delete-twice pattern is tested explicitly. Returning `False` on a second delete (rather than raising an error) is important for eventual consistency patterns where a delete may be issued multiple times. A raised exception would force callers to guard against it.

### List

`list_souls()` returns all saved soul IDs. The test seeds two configs and confirms both appear:

```python
souls = await store.list_souls()
assert set(souls) == {"aria", "nova"}
```

## FileStorage

### On-Disk Directory Structure

`FileStorage` creates a per-soul directory under `base_dir`. The test verifies the expected files exist after a save:

```python
soul_dir = tmp_path / "aria"
assert (soul_dir / "soul.json").exists()
assert (soul_dir / "dna.md").exists()
assert (soul_dir / "state.json").exists()
```

This structure is important for portability — users can inspect, backup, or edit soul files using standard filesystem tools. The test documents which files are mandatory so that future changes to the serialization layer know what not to break.

### Delete Removes Directory

File delete removes the entire soul directory:

```python
result = await store.delete("aria")
assert not (tmp_path / "aria").exists()
```

Directory-level deletion is tested (not just file deletion) because partial deletes — where `soul.json` is removed but `state.json` is left — would cause load to return inconsistent data on restart.

### Load Non-Existent Returns None

```python
missing = await store.load("missing-soul")
assert missing is None
```

Returning `None` instead of raising means callers can use `if loaded:` checks without try/except, consistent with the `Optional[SoulConfig]` return type.

### List Uses Disk Scan

`list_souls()` scans the base directory rather than maintaining an in-memory index. This means it stays correct even if souls are added or removed by other processes.

## Known Gaps

- There is no test for what happens when `soul.json` exists but `state.json` is missing (partial directory). The load behavior in this case is not specified.
- `dna.md` is listed in the directory structure assertion but its contents are never validated — it may be empty or contain a default template.
- There are no concurrency tests for `FileStorage` — two processes saving to the same soul ID simultaneously could produce a corrupt directory.