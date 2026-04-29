---
{
  "title": "Test Suite for Zip Recall Bug: Soul File Export/Awaken Roundtrip and Stale MCP Cache",
  "summary": "This regression test suite targets a production bug where `soul_recall` via the MCP server returned zero results for memories that existed in the `.soul` file on disk. The root cause was the MCP server loading souls at startup and never reloading when the file was updated externally. Tests cover semantic and episodic recall after zip roundtrip, bytes-based awakening, multi-memory preservation, content fidelity, and the stale-cache simulation.",
  "concepts": [
    "zip recall bug",
    "Soul.awaken",
    "Soul.export",
    "stale MCP cache",
    "soul_reload",
    "memory roundtrip",
    "MemoryType.SEMANTIC",
    "MemoryType.EPISODIC",
    "memory_count",
    "MCP server"
  ],
  "categories": [
    "testing",
    "regression",
    "soul-format",
    "mcp-server",
    "test"
  ],
  "source_docs": [
    "6bbca9cf3d7a71a8"
  ],
  "backlinks": null,
  "word_count": 544,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Background: The Bug

In March 2026, a bug was discovered where `soul_recall` via the MCP server returned zero results even though `memory_count > 0` on the loaded soul. The root cause: the MCP server loaded `pocketpaw.soul` once at startup and held it in memory. When another process (Claude Code, the `soul` CLI) added new memories and re-exported the `.soul` file to disk, the MCP server's in-memory soul object was stale — it had no knowledge of the new memories.

This test file documents both the underlying zip roundtrip bug and the stale-cache failure mode.

## Zip Recall After Export/Awaken

### Core Regression Test

`test_zip_recall_semantic_after_export_awaken` is the primary regression test. It asserts that a memory added to a soul is still recallable after `export()` → `Soul.awaken()` roundtrip:

```python
await soul.remember(
    "MiroFish swarm prediction algorithm uses tidal resonance",
    type=MemoryType.SEMANTIC, importance=8,
)
before_export = await soul.recall("MiroFish swarm prediction")
assert len(before_export) >= 1  # sanity: original soul works

await soul.export(str(zip_path))
restored = await Soul.awaken(str(zip_path))

assert restored.memory_count > 0  # proves data survived packing
after_awaken = await restored.recall("MiroFish swarm prediction")
assert len(after_awaken) >= 1    # this was the failing assertion
```

The two-step assertion (first check `memory_count > 0`, then check recall) is deliberate: it distinguishes between the archive being corrupted (memories absent) versus the recall index being broken (memories present but unsearchable).

### Episodic Tier

A separate test exercises the episodic tier because episodic memories are stored differently — they are wrapped as interaction objects before storage. A bug in the episodic-to-zip serialization path would be invisible to semantic-only tests.

### Bytes Path

`test_zip_recall_via_bytes` calls `Soul.awaken(raw_bytes)` instead of `Soul.awaken(path)`, testing the bytes branch of `unpack_soul` + `MemoryManager.from_dict`. This is the path used when souls are transferred over an API or embedded in another payload.

### Multi-Memory Preservation

Three distinct semantic memories are seeded, then the restored soul's `memory_count` must equal the original count exactly:

```python
assert restored.memory_count == original_count
```

This catches off-by-one bugs or deduplication logic that might silently drop entries with similar content.

### Content Fidelity

`test_zip_recall_returns_correct_content` confirms that recalled content matches the exact string stored — not a truncated or transformed version:

```python
assert "MiroFish" in recalled_content
assert "tidal resonance" in recalled_content.lower()
```

## Stale MCP Cache Simulation

`test_stale_soul_reload_picks_up_new_memories` directly simulates the production incident in five phases:

1. Create a soul with initial memories and export.
2. Simulate MCP server loading the soul at startup (`server_soul`).
3. External process adds new memories and re-exports to the same file path.
4. Assert `server_soul` cannot find the new memory (it is stale).
5. Reload from disk (`Soul.awaken(zip_path)`) and assert the new memory is now found.

```python
stale_results = await server_soul.recall("MiroFish swarm prediction")
assert len(stale_results) == 0  # stale — correct expectation

reloaded = await Soul.awaken(str(zip_path))
fresh_results = await reloaded.recall("MiroFish swarm prediction")
assert len(fresh_results) >= 1  # fresh reload works
```

This test documents that the **fix for the MCP bug is to call `Soul.awaken()` again** (the `soul_reload` MCP tool), not to keep a cached soul object alive across external writes.

## Known Gaps

- There is no test for what happens if the `.soul` file is corrupted between the export and awaken steps.
- The test does not verify that `soul_reload` is wired correctly in the MCP server — it only verifies the underlying `Soul.awaken()` behavior.