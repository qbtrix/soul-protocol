---
{
  "title": "Test Suite for SoulProvider PocketPaw Integration",
  "summary": "Covers the `SoulProvider` reference integration class with 14 async pytest tests verifying system prompt generation, memory recall injection, interaction tracking, auto-save behavior, factory constructors, and low-energy behavioral adaptation. Tests are isolated using fresh Soul instances per fixture to prevent cross-test memory contamination.",
  "concepts": [
    "pytest-asyncio",
    "SoulProvider",
    "async fixtures",
    "AsyncMock",
    "patch.object",
    "system prompt",
    "memory recall injection",
    "auto-save",
    "from_name factory",
    "from_file factory",
    "low-energy adaptation",
    "tmp_path",
    "test isolation",
    "integration tests"
  ],
  "categories": [
    "testing",
    "integration",
    "soul-protocol",
    "PocketPaw",
    "test"
  ],
  "source_docs": [
    "3c5fe7efb8325f58"
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

This test suite validates the `SoulProvider` integration from `examples/pocketpaw_integration.py`. It was originally part of `tests/test_integrations/test_pocketpaw.py` and was moved into the examples directory to keep integration tests co-located with the code they exercise.

## Test Infrastructure

```python
@pytest.fixture
async def soul() -> Soul:
    """Birth a fresh soul for each test."""
    return await Soul.birth("Aria", archetype="The Compassionate Creator")

@pytest.fixture
async def provider(soul: Soul) -> SoulProvider:
    """Create a SoulProvider wrapping the test soul."""
    return SoulProvider(soul)
```

The `soul` fixture births a fresh Soul for every test, preventing memory from one test leaking into another. The `provider` fixture composes on top of it, following pytest's dependency injection pattern. Both are `async` fixtures, using pytest-asyncio conventions.

## Core Behavior Tests

**`test_soul_provider_system_prompt`** — verifies that `get_system_prompt()` returns a non-empty string containing the soul's name. This is the minimum viable assertion: if the soul's identity is not in the prompt, every downstream agent response will be wrong.

**`test_soul_provider_with_query`** — teaches the soul a memory, then checks that `get_system_prompt(user_query="hiking")` injects a `## Relevant Memories` section. This validates the recall-injection pipeline end-to-end.

**`test_soul_provider_with_query_no_matches`** — verifies that the memories section is absent when no relevant memories exist. Without this test, a bug that always injected an empty memories section would pass the previous test but inject noise into every prompt.

**`test_soul_provider_on_interaction`** — calls `on_interaction()` and checks that the soul's energy and social battery change. This confirms the observe pipeline is actually wired up, not just silently discarded.

**`test_soul_provider_status`** — validates that `get_soul_status()` returns a dict with all expected dashboard keys (name, DID, mood, energy, memory count, bond).

## Factory Constructor Tests

**`test_soul_provider_from_name`** — calls `SoulProvider.from_name(name, archetype)` and verifies the resulting soul has the correct name. This tests the async class method factory pattern.

**`test_soul_provider_from_name_defaults`** — verifies that omitting `archetype` uses `'The Companion'` as the default. Defaults are easy to break silently; explicit tests catch regressions.

**`test_soul_provider_from_file`** — births a soul, exports it to a `tmp_path`, then calls `SoulProvider.from_file(path)` to verify round-trip persistence. Uses pytest's `tmp_path` fixture to avoid polluting the filesystem.

## Auto-Save Test

```python
async def test_soul_provider_auto_save(provider):
    with patch.object(provider, "save", new_callable=AsyncMock) as mock_save:
        for _ in range(10):
            await provider.on_interaction(...)
        assert mock_save.call_count == 1
```

Patches `save()` with an `AsyncMock` and counts invocations after exactly N interactions (default 10). This is the canonical way to verify periodic side-effect behavior without performing actual I/O in tests.

## Low-Energy Adaptation Test

**`test_soul_provider_low_energy_note`** — directly sets `provider.soul.state.energy = 20` (below the 30% threshold) and verifies the system prompt includes the low-energy annotation. This tests behavioral adaptation without requiring the energy to drain naturally through interactions, which would be slow and non-deterministic.

## Recall Limit Test

**`test_soul_provider_recall_limit`** — stores multiple memories and verifies that `memory_recall_limit=2` caps the injected memories at 2 regardless of how many match. Tests that the parameter is actually respected, not just accepted.

## Known Gaps

- No test for `sender_id` behavior — since the current implementation ignores sender_id, there is no test verifying per-sender memory scoping (a documented gap in the implementation).
- Auto-save test uses a mock rather than verifying actual file writes, so it cannot catch bugs where `save()` is called but writes nothing to disk.