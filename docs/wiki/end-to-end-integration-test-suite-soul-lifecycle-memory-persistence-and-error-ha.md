---
{
  "title": "End-to-End Integration Test Suite — Soul Lifecycle, Memory Persistence, and Error Handling",
  "summary": "Full end-to-end integration tests for the Soul class covering the complete lifecycle from birth through export and awakening. Tests validate memory persistence across all five tiers, self-model emergence, core memory editing, directory format save/load, and robust error handling for corrupt or missing soul files.",
  "concepts": [
    "Soul.birth",
    "Soul.observe",
    "Soul.recall",
    "export",
    "awaken",
    "memory persistence",
    "self-model",
    "core memory",
    "YAML config",
    "JSON config",
    "directory format",
    "rich_soul fixture",
    "multi-tier memory",
    "corrupt file handling"
  ],
  "categories": [
    "testing",
    "integration",
    "soul-lifecycle",
    "test"
  ],
  "source_docs": [
    "59566596a2cf4208"
  ],
  "backlinks": null,
  "word_count": 422,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

This is the primary integration test suite for soul-protocol. While unit tests validate individual components, this suite validates the system as a whole: that a soul can be born, accumulate memories and state, serialized to disk, and faithfully reconstituted with all data intact.

## Why This Exists

The soul's value proposition is persistence — if anything is lost during export/awaken cycles, the soul degrades silently. These tests function as data integrity contracts. Every memory tier, state field, and identity attribute that matters must survive a roundtrip.

## Test Structure

### Full Lifecycle

`TestFullLifecycle` follows the canonical flow:

```python
async def test_birth_creates_active_soul()
async def test_observe_updates_state(rich_soul)
async def test_recall_finds_stored_memories(rich_soul)
async def test_full_export_awaken_cycle(rich_soul, tmp_path)
```

The `rich_soul` fixture births a soul with realistic config and pre-loaded memories, shared across tests that need a populated starting state.

### Config Roundtrip

`TestConfigRoundtrip` verifies that YAML and JSON config formats survive export/awaken. This guards against format-specific serialization bugs (e.g., YAML boolean coercion, JSON null handling).

### Memory Persistence

`TestMemoryPersistence` is the most thorough section — it validates each memory tier independently:

- **Semantic** — facts and beliefs
- **Episodic** — interaction events
- **Core** — identity-level persona and human fields
- **Procedural** — learned skills and habits
- **Multi-tier** — all tiers in a single save/load

The `test_memory_count_preserved` test is particularly important: it verifies that no memories are silently dropped during serialization, which could happen if a collection is iterated while being modified.

### Self-Model Emergence

`TestSelfModelEmergence` validates that after multiple technical interactions, the soul's self-model populates with domain knowledge:

```python
async def test_self_model_confidence_grows()
async def test_self_model_persists_through_export(tmp_path)
```

The confidence growth test ensures the system isn't stuck at initialization values — a regression that would make the self-model useless for prompting.

### Core Memory Editing

`TestCoreMemoryEditing` verifies that persona and human fields can be directly edited and survive export. Core memory is the soul's fixed identity — its persistence is non-negotiable.

### Directory Format

`TestDirectoryFormat` tests the alternative save format (directory instead of zip archive). This format is used for human-readable inspection and tooling.

### Error Handling

`TestErrorHandling` validates the failure modes:

```python
async def test_corrupt_soul_file(tmp_path)
async def test_nonexistent_soul_file(tmp_path)
async def test_unsupported_config_format(tmp_path)
async def test_missing_config_file(tmp_path)
```

Corrupt files and missing files must raise specific, actionable errors rather than `AttributeError` or silent data loss. This is especially important for CLI users who might accidentally pass wrong paths.

## Known Gaps

No tests cover concurrent access (two processes awakening the same soul file simultaneously) or migration between format versions (upgrading an old `.soul` archive to a new schema).