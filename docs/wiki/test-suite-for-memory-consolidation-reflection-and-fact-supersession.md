---
{
  "title": "Test Suite for Memory Consolidation, Reflection, and Fact Supersession",
  "summary": "Validates the consolidation pipeline that transforms raw episodic memories into structured semantic knowledge — converting summaries into semantic memories, grouping episodes under general-event themes, storing self-insight and emotional patterns, and superseding outdated facts. Also tests the reflect() entry point and the apply=False dry-run mode.",
  "concepts": [
    "consolidation",
    "ConsolidationResult",
    "semantic memory",
    "general events",
    "self-insight",
    "emotional patterns",
    "reflect",
    "apply=False",
    "fact supersession",
    "idempotency",
    "template prefix",
    "MemoryManager"
  ],
  "categories": [
    "testing",
    "memory",
    "consolidation",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "4414806769429a80"
  ],
  "backlinks": null,
  "word_count": 518,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_consolidation.py` verifies the memory consolidation system, which is the "thinking" pass that runs after a batch of interactions have been observed. Consolidation transforms raw episodic memories into higher-level semantic knowledge, linking related episodes, and resolving fact conflicts through supersession.

## Summary Consolidation (TestConsolidateSummaries)

The consolidation engine receives a `ConsolidationResult` from the reflection engine and applies it to the `MemoryManager`:

- `test_summaries_become_semantic_memories` — text summaries in the result are stored as new semantic memory entries
- `test_empty_summary_skipped` — empty string summaries are not stored (prevents blank semantic memories)
- `test_importance_clamped` — importance values outside [1–10] are clamped to the valid range
- `test_no_summaries_noop` — a consolidation result with no summaries makes no changes to memory

## General Events Consolidation (TestConsolidateGeneralEvents)

General events are abstract themes that group related episodic memories:

```python
async def test_themes_create_general_events():
    # Each theme string in the result creates a new general-event memory

async def test_duplicate_theme_updates_not_duplicates():
    # Consolidating the same theme twice must update the existing entry, not create a second one
    # This is the key idempotency guard — prevents theme proliferation on repeated consolidation

async def test_episodes_linked_to_matching_theme():
    # Episodic memories whose content matches a theme get their general_event_id set

async def test_general_event_id_set_on_episode():
    # The foreign key linking episode → general event is written to the episode
```

The duplicate-theme idempotency guard is critical: consolidation can run multiple times on overlapping data windows. Without it, a single theme could produce dozens of duplicate general-event entries.

## Self-Insight and Emotional Patterns

- `test_self_insight_stored` — self-insight strings from the reflection result are stored as a distinct memory type
- `test_emotional_pattern_stored` — identified emotional patterns are stored and queryable
- Both have corresponding `_noop` tests: when the field is absent in the result, no memory is created

## Integration (TestConsolidateIntegration)

`test_all_fields_applied` verifies that a single consolidation call correctly applies all four outputs simultaneously (summaries, themes, self-insight, emotional patterns) without interference. `test_empty_result_noop` confirms a fully empty result leaves the memory store unchanged.

## Reflect Entry Point (TestReflectApply)

`reflect()` is the public method that triggers both the engine call and consolidation:

```python
async def test_reflect_no_engine_returns_none():
    # Without an LLM engine, reflect() returns None (no reflection possible)

async def test_reflect_apply_false_no_side_effects():
    # reflect(apply=False) runs the engine but does NOT write to memory
    # This is a dry-run mode for inspecting what would be consolidated
```

The `apply=False` mode is important for debugging: it lets callers preview the consolidation output without mutating the soul's memory.

## Fact Supersession (TestFactConflicts)

When a new fact shares the same template prefix as an existing one (e.g., both start with "User works at..."), the old fact is superseded:

- `test_same_prefix_supersedes` — the old fact gets `superseded=True`
- `test_superseded_filtered_from_search` — superseded facts do not appear in normal recall results
- `test_superseded_filtered_from_facts` — the facts accessor also hides superseded entries
- `test_include_superseded_shows_all` — passing `include_superseded=True` reveals the full history
- `test_different_prefix_no_conflict` — unrelated facts are not superseded by each other

## Known Gaps

The `TestReflectApply.test_reflect_apply_false_no_side_effects` docstring contains a note: "With no engine, returns None anyway" — the test combines two behaviors (no-engine and apply=False) into one, meaning the apply=False with a live engine is not separately tested.