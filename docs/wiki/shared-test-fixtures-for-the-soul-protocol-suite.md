---
{
  "title": "Shared Test Fixtures for the Soul Protocol Suite",
  "summary": "`conftest.py` centralizes the four foundational fixtures used across all soul-protocol test modules: a sample `Identity`, a `SoulConfig` built from it, a fully-birthed `Soul`, and a temporary `.soul` file on disk. Centralizing these prevents fixture duplication and ensures all tests operate on consistent, valid starting state.",
  "concepts": [
    "pytest fixtures",
    "conftest",
    "Soul.birth",
    "Soul.awaken",
    "Identity",
    "SoulConfig",
    "async fixtures",
    "test setup",
    "fixture composition"
  ],
  "categories": [
    "testing",
    "fixtures"
  ],
  "source_docs": [
    "7140bc6174f9d4e8"
  ],
  "backlinks": null,
  "word_count": 375,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Without shared fixtures, every test module that needs a `Soul` would repeat the same `Soul.birth("Aria", archetype="The Compassionate Creator")` call. This creates two failure modes:

1. **Drift** — one module uses a slightly different name or archetype, causing subtle test differences that are hard to reason about.
2. **Maintenance cost** — when `Soul.birth()` signature changes, every test file must be updated rather than just one.

`conftest.py` is pytest's built-in mechanism for sharing fixtures without explicit imports. Pytest discovers this file automatically and makes its fixtures available to all tests in the same directory and below.

## Fixtures

### `sample_identity` → `Identity`

```python
Identity(name="Aria", archetype="The Compassionate Creator")
```

Provides a reusable identity object for tests that need to inspect or manipulate `Identity` fields directly without going through the full `Soul` lifecycle.

### `sample_config` → `SoulConfig`

```python
SoulConfig(identity=sample_identity)
```

Built from `sample_identity`, this fixture tests the configuration layer in isolation — useful for serialization round-trips and settings validation.

### `sample_soul` → `Soul` (async)

```python
await Soul.birth("Aria", archetype="The Compassionate Creator")
```

A fully initialized `Soul` instance. Because `Soul.birth()` is async, this fixture is declared `async def` and pytest-asyncio handles the event loop. Tests that modify this soul (adding memories, adjusting bond strength) receive a fresh copy for each test because pytest creates a new fixture instance per test by default.

### `tmp_soul_file` → `str` (async)

```python
path = tmp_path / "aria.soul"
await sample_soul.export(str(path))
return str(path)
```

Exports `sample_soul` to a temporary file and returns the path as a string. Tests that exercise `Soul.awaken()`, import/export round-trips, or CLI commands that operate on `.soul` files use this fixture. The `tmp_path` argument is pytest's built-in temporary directory fixture, which is unique per test and cleaned up after each run.

## Dependency Chain

```
sample_identity
    └── sample_config

Soul.birth()
    └── sample_soul
            └── tmp_soul_file (depends on sample_soul + tmp_path)
```

The fixtures compose correctly because pytest resolves dependencies automatically. `sample_config` declares `sample_identity` as a parameter, and pytest injects the same `sample_identity` instance that was already constructed for that test.

## Known Gaps

- The fixtures only provide a single, fixed identity (`Aria`). Tests that need multiple souls or specific personality configurations create their own souls inline. A future improvement might add parameterized fixtures covering edge-case souls (minimal config, extreme OCEAN scores, pre-populated memories).