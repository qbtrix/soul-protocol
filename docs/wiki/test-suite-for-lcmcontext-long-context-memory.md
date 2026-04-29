---
{
  "title": "Test Suite for LCMContext (Long-Context Memory)",
  "summary": "Integration tests for `LCMContext`, the context engine that ingests conversation messages, assembles token-budgeted context windows, and auto-compacts history using a `CognitiveEngine`. Covers protocol compliance, initialization guards, token estimation, compaction triggers, grep search, and lifecycle close/reopen semantics.",
  "concepts": [
    "LCMContext",
    "ContextEngine",
    "ingest",
    "assemble",
    "token budget",
    "compaction",
    "auto-compaction",
    "CognitiveEngine",
    "grep",
    "expand",
    "lifecycle",
    "initialization guard",
    "long-context memory",
    "MockCognitiveEngine",
    "CompactionLevel"
  ],
  "categories": [
    "testing",
    "context-management",
    "LCM",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "4cf76425d41a204a"
  ],
  "backlinks": null,
  "word_count": 435,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

LCM (Long-Context Memory) is Soul Protocol's stateful context layer, responsible for keeping agent conversations within model token limits while preserving as much relevant history as possible. `test_lcm.py` validates the entire `LCMContext` lifecycle through exhaustive integration tests.

## Protocol Compliance

`TestProtocolCompliance` checks that `LCMContext` satisfies the `ContextEngine` protocol:

```python
def test_implements_context_engine(lcm):
    assert isinstance(lcm, ContextEngine)
```

This guards against protocol drift — if `LCMContext` drops a method required by `ContextEngine`, consuming code would fail at runtime rather than at import.

## Initialization Guards

`TestInitialization` tests that calling any operation before `initialize()` raises an error (`test_uninitialized_ingest_raises`, etc.). Without these guards, a misconfigured agent could silently operate on a null store. `test_double_initialize` verifies that calling `initialize()` twice is safe — this is an idempotency guard preventing resource leak or state corruption on duplicate setup calls.

## Ingestion (`TestIngest`)

- Each message receives a unique ID.
- Multiple roles (user, assistant, system) are accepted.
- Token count estimation is tested — correctness of the estimator matters because it drives compaction decisions.

## Context Assembly (`TestAssemble`)

`assemble()` returns a list of messages that fit within a token budget:

- `test_respects_token_budget` — messages are excluded if adding them would exceed the budget.
- `test_system_reserve` — a reserved system-message budget is deducted from the available window.
- `test_zero_budget_returns_empty` and `test_negative_effective_budget` — edge cases that would cause infinite loops or incorrect slicing without explicit guards.
- `test_nodes_ordered_by_sequence` — assembled messages maintain chronological order.

## Auto-Compaction (`TestAutoCompaction`)

When total token count exceeds a threshold, `LCMContext` compacts older messages using the `CognitiveEngine`:

```python
class MockCognitiveEngine:
    async def think(self, prompt: str) -> str:
        if "[TASK:context_summary]" in prompt:
            return "Summarized conversation."
        if "[TASK:context_bullets]" in prompt:
            return "- Key point"
        return "OK"
```

The mock engine returns deterministic output so tests are reproducible without LLM calls. `test_triggers_on_threshold` verifies compaction fires automatically; `test_manual_compact` confirms it can be triggered explicitly.

## Search (`TestGrepIntegration`)

`grep()` searches ingested messages by content. Tests verify matches are found, non-matching queries return empty results, and a `limit` parameter caps results.

## Expand After Compaction (`TestExpandIntegration`)

Compacted context nodes store a summary. `test_expand_after_compaction` verifies that the original messages can be recovered from a compacted node — critical for audit trails and debugging. `test_expand_nonexistent_node` returns `None` rather than raising.

## Lifecycle (`TestLifecycle`)

- `test_close_and_reopen` — close the context, reopen with the same storage path, and verify state is preserved.
- `test_operations_after_close_raise` — operations on a closed context raise errors rather than silently operating on stale data.

## Known Gaps

- `CompactionLevel` model is imported but its full range of levels is not exercised in these tests.
- No tests for concurrent ingest from multiple async tasks.