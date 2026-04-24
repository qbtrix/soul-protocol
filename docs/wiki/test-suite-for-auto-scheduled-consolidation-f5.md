---
{
  "title": "Test Suite for Auto-Scheduled Consolidation (F5)",
  "summary": "This test suite validates that `Soul.observe()` automatically triggers memory consolidation (archival and reflection) at a configurable interval, that the interval is configurable and disableable, and that the interaction count persists through export/awaken cycles so consolidation timing survives restarts.",
  "concepts": [
    "auto-consolidation",
    "interaction count",
    "observe",
    "consolidation_interval",
    "MemorySettings",
    "archive_old_memories",
    "reflect",
    "CognitiveEngine",
    "persistence",
    "AsyncMock"
  ],
  "categories": [
    "testing",
    "memory",
    "soul-lifecycle",
    "test"
  ],
  "source_docs": [
    "324478f39e7172be"
  ],
  "backlinks": null,
  "word_count": 413,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Feature F5 introduced auto-consolidation: after every N interactions, `observe()` automatically calls `archive_old_memories()` and (if a `CognitiveEngine` is present) `reflect()`. Without this, callers would need to manually trigger consolidation, which in practice never happens.

This test suite was created 2026-03-29 to lock that behavior.

## Interaction Count

```python
assert soul._interaction_count == 0
await soul.observe(_make_interaction("First"))
assert soul._interaction_count == 1
```

Every call to `observe()` increments `_interaction_count`. This counter is the clock that determines when consolidation fires.

## Consolidation Trigger (`TestAutoConsolidation`)

```python
soul._memory._settings.consolidation_interval = 3

await soul.observe(...)   # count = 1 — no trigger
await soul.observe(...)   # count = 2 — no trigger
await soul.observe(...)   # count = 3 — triggers archive_old_memories()
```

The mock confirms `archive_old_memories` was called exactly once. Tests use `AsyncMock` with `patch.object` to intercept the call without executing the real archival logic — this keeps the test fast and focused on the trigger mechanism, not the archival behavior (which is covered in `test_archival_integration.py`).

## No-Engine Guard

When `soul._engine is None`, consolidation should only call `archive_old_memories()` — NOT `reflect()`. Reflection requires an LLM engine; calling it without one would raise an exception. The test patches both methods and verifies:

```python
mock_archive.assert_called_once()  # always fires
mock_reflect.assert_not_called()   # only with engine
```

## Configurable Interval

The `consolidation_interval` is an integer on `MemorySettings`. The tests verify:

- Setting it to 5 fires after exactly 5 interactions (not 4, not 6)
- Setting it to 0 disables consolidation entirely — 25 interactions pass without a single trigger

The zero-disables-consolidation semantic is important for testing environments and for users who want full manual control.

## Default Value

```python
assert MemorySettings().consolidation_interval == 20
```

The default of 20 is locked by test. Changing it would require updating this assertion, making accidental default changes visible in CI.

## Persistence Through Export/Awaken

```python
soul._interaction_count = 15
await soul.export(str(path))
restored = await Soul.awaken(str(path))
assert restored._interaction_count == 15
```

Without persistence, every soul re-awakened from a `.soul` file would reset its interaction clock to 0, causing consolidation to fire unexpectedly early (at interaction N) or unexpectedly late (never, if the soul was near the interval boundary). Persisting the count through `SoulConfig` prevents both failure modes.

## Known Gaps

- There is no test for consolidation behavior when `archive_old_memories()` raises an exception mid-observe. The current behavior (exception propagates to caller) may not be the desired UX.
- The consolidation trigger fires at exactly `N * interval` interactions. There is no jitter or backpressure mechanism; if archival is slow, a backup could form.