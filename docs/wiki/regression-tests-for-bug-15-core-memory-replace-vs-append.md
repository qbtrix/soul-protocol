---
{
  "title": "Regression Tests for Bug #15: Core Memory Replace vs. Append",
  "summary": "This regression suite locks the fix for Bug #15, where `edit_core_memory()` was appending new values to existing persona and human fields instead of replacing them. The tests verify replace semantics, partial-field isolation, and the explicit absence of the old append behavior.",
  "concepts": [
    "Bug #15",
    "edit_core_memory",
    "append vs replace",
    "regression test",
    "CoreMemory",
    "persona field",
    "human field",
    "partial update"
  ],
  "categories": [
    "testing",
    "bug-regression",
    "core-memory",
    "test"
  ],
  "source_docs": [
    "a6252921d1805bbb"
  ],
  "backlinks": null,
  "word_count": 404,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## The Bug

Bug #15: `Soul.edit_core_memory()` was appending the new value to the existing field rather than replacing it. A soul initialized with `persona="I am helpful"` that received `edit_core_memory(persona="I am creative")` would end up with `persona="I am helpfulI am creative"` (or similar concatenation) instead of `"I am creative"`.

This is a category of bug that is easy to introduce and hard to notice — the field appears to update, but over many edits it accumulates an ever-growing string of historical values.

## Test Design

Regression tests for this class of bug serve a different purpose than functional tests. They document what was broken, so if the implementation ever regresses the test name tells the reader exactly which bug came back.

### Replace Semantics (persona)

```python
await soul.edit_core_memory(persona="I am creative")
assert soul.get_core_memory().persona == "I am creative"
# Not "I am helpfulI am creative"
```

### Replace Semantics (human)

```python
await soul.edit_core_memory(human="Alice, a developer")
await soul.edit_core_memory(human="Bob, a designer")
assert soul.get_core_memory().human == "Bob, a designer"
# Not "Alice, a developerBob, a designer"
```

### Partial Update Isolation

Editing `persona` must not touch `human`, and vice versa:

```python
await soul.edit_core_memory(persona="I am creative")
assert soul.get_core_memory().human == "Alice"  # unchanged

await soul.edit_core_memory(human="Bob")
assert soul.get_core_memory().persona == "I am creative"  # unchanged
```

This test prevents a different failure mode: an overly-eager fix that replaces the entire `CoreMemory` object on every call, zeroing out fields that were not explicitly passed.

### Explicit Anti-Append Assertion

```python
await soul.edit_core_memory(persona="Second")
assert "First" not in soul.get_core_memory().persona
assert soul.get_core_memory().persona == "Second"
```

The `"First" not in` check is deliberately redundant with the equality check — it names the failure mode explicitly, making the intent of the test clear to anyone reading a failure message.

## Why Four Tests Instead of One?

Each test targets a distinct failure scenario:

1. `test_edit_core_memory_replaces_persona` — basic replace on persona
2. `test_edit_core_memory_replaces_human` — basic replace on human (same bug, different field)
3. `test_edit_core_memory_partial_update` — partial updates don't zero out other fields
4. `test_edit_core_memory_does_not_append` — explicit anti-append contract

A single combined test would pass or fail as a unit, making it harder to diagnose which part of the contract broke.

## Known Gaps

- There is no test for concurrent calls to `edit_core_memory()` — if two calls race, the last-write-wins behavior is assumed but not verified.
- There are no tests for empty string values (`edit_core_memory(persona="")`) — whether an empty string is treated as "no change" or as a deliberate wipe is unspecified.