---
{
  "title": "Test Suite for Soul Eternal Storage Integration",
  "summary": "Tests the integration between the Soul class and EternalStorageManager, covering Soul.archive(), the with_mocks() factory, the eternal= parameter on Soul.birth() and Soul.awaken(), and the export(archive=True) convenience flag.",
  "concepts": [
    "Soul.archive",
    "EternalStorageManager",
    "with_mocks",
    "eternal parameter",
    "export archive flag",
    "Soul.awaken",
    "Soul.birth",
    "RuntimeError",
    "eternal storage integration",
    "soul lifecycle"
  ],
  "categories": [
    "testing",
    "eternal storage",
    "soul lifecycle",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "e05a6626bd8d1a78"
  ],
  "backlinks": null,
  "word_count": 497,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_soul_eternal.py` tests the public API surface that links the `Soul` class to eternal storage. While `test_manager.py` and `test_e2e_eternal.py` test the storage subsystem in isolation, this file verifies that souls can actually invoke eternal storage through their own methods — the integration that end users and agents will actually call.

## The `with_mocks()` Factory

```python
async def test_with_mocks_factory():
    mgr = EternalStorageManager.with_mocks()
    assert "ipfs" in mgr._providers
    assert "arweave" in mgr._providers
```

`EternalStorageManager.with_mocks()` is a convenience constructor that pre-registers mock IPFS and Arweave providers. This factory exists so that developers can quickly spin up an eternal-storage-enabled soul in tests and demos without manually registering providers. The test confirms the factory registers exactly the expected providers — if someone adds or removes a provider from `with_mocks()`, this test catches the change.

## Soul.archive()

```python
async def test_soul_archive_works():
    eternal = EternalStorageManager.with_mocks()
    soul = await Soul.birth("TestSoul", eternal=eternal)
    await soul.remember("test memory", importance=5)
    results = await soul.archive(tiers=["ipfs"])
    assert len(results) == 1
    assert results[0].tier == "ipfs"
    assert results[0].reference
```

`Soul.birth(eternal=eternal)` is the primary integration point: a soul that knows about its eternal storage manager can archive itself without the caller needing to manage the manager directly. The test verifies that after birth and a memory operation, `soul.archive()` produces a valid result with a non-empty reference.

## Error Without Eternal Storage

```python
async def test_soul_archive_without_eternal_raises():
    soul = await Soul.birth("TestSoul")  # no eternal= param
    with pytest.raises(RuntimeError, match="No eternal storage configured"):
        await soul.archive()
```

A soul born without an eternal storage manager must raise `RuntimeError` with a clear message if `archive()` is called. Without this guard, the caller would get an `AttributeError` on `None._providers` or similar — an opaque crash with no actionable guidance.

## export(archive=True)

```python
async def test_export_with_archive_flag(tmp_path):
    eternal = EternalStorageManager.with_mocks()
    soul = await Soul.birth("TestSoul", eternal=eternal)
    await soul.export(str(path), archive=True, archive_tiers=["ipfs"])
    assert path.exists()
```

The `archive=True` flag on `Soul.export()` triggers archival automatically after writing the `.soul` file. This is the most ergonomic path for users: export and archive in one call. The test confirms that the local file is still written (the primary export) and the archive side effect does not prevent normal operation.

## Soul.awaken() with eternal=

```python
async def test_awaken_with_eternal(tmp_path):
    soul = await Soul.birth("TestSoul")
    await soul.export(str(path))
    eternal = EternalStorageManager.with_mocks()
    restored = await Soul.awaken(str(path), eternal=eternal)
    assert restored._eternal is eternal
    results = await restored.archive(tiers=["ipfs"])
    assert len(results) == 1
```

A soul can be awakened from a file and immediately connected to eternal storage, even if it was originally born or exported without an eternal manager. This supports the migration scenario: an existing soul file can be upgraded to use eternal storage without re-creating the soul from scratch.

The `restored._eternal is eternal` assertion checks object identity (not just equality), confirming that the manager instance passed in is the exact one stored — no copying or wrapping occurs.

## Known Gaps

No TODO markers. The `export(archive=True)` test only checks that the file exists, not that the archive actually succeeded. A more complete test would assert on the archive results, but this may be left to the e2e tests.
