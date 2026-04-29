---
{
  "title": "Developer Onboarding Demo Smoke Test",
  "summary": "A minimal async smoke test that runs the soul-protocol onboarding demo end-to-end in a non-interactive mode. It uses `monkeypatch` to set `SOUL_DEMO_NO_PAUSE=1`, preventing the demo from blocking on user input during CI.",
  "concepts": [
    "onboarding demo",
    "smoke test",
    "SOUL_DEMO_NO_PAUSE",
    "monkeypatch",
    "pytest.mark.asyncio",
    "run_demo",
    "non-interactive CI",
    "developer experience",
    "async test"
  ],
  "categories": [
    "testing",
    "developer-experience",
    "onboarding",
    "test"
  ],
  "source_docs": [
    "56d3553c85f5c862"
  ],
  "backlinks": null,
  "word_count": 313,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

This test ensures that the developer onboarding demo (`soul_protocol.demo.run_demo`) completes without raising an exception. It is a smoke test — not a behavioral test — meaning it validates that the demo is runnable, not that every output is correct.

## Why This Exists

The onboarding demo is the first thing a new developer runs after installing soul-protocol. If it crashes, the first impression is broken regardless of how solid the rest of the SDK is. This test acts as a canary: if any import, runtime initialization, or async setup step regresses, the test catches it before the developer does.

## The Non-Interactive Guard

```python
@pytest.mark.asyncio
async def test_demo_runs_without_error(monkeypatch):
    monkeypatch.setenv("SOUL_DEMO_NO_PAUSE", "1")
    await run_demo()
```

The `SOUL_DEMO_NO_PAUSE=1` environment variable is critical. Without it, `run_demo()` would pause for user input between steps (a deliberate "slow reveal" UX for humans). In a CI environment, that pause would hang indefinitely. The monkeypatch injects the flag scoped to this test only, so other tests are unaffected.

This pattern was added in the March 2026 update (`2026-03-13`) after the demo was presumably found to block in automated test runs.

## Data Flow

1. `monkeypatch.setenv` injects `SOUL_DEMO_NO_PAUSE=1` into the process environment for the duration of the test.
2. `await run_demo()` executes the full onboarding sequence: soul birth, observation, recall, and export steps.
3. If no exception propagates, the test passes.

## Defensive Patterns

Using `pytest.mark.asyncio` rather than `asyncio.run()` inside a sync test avoids event loop conflicts when other async tests run in the same session. This is the standard pattern for async smoke tests in soul-protocol.

## Known Gaps

The test does not assert on output content — it only checks that no exception is raised. A richer test would capture stdout and verify that key demo steps (e.g., "Soul born", "Memory stored") are printed. This is by design for a smoke test but means output regressions are invisible.