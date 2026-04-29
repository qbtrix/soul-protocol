---
{
  "title": "State Subpackage Public Interface",
  "summary": "The `state/__init__.py` module is the stable public entry point for the runtime state management subpackage, re-exporting `StateManager` so callers never couple to internal module paths. This thin facade absorbs internal restructures without breaking consumers.",
  "concepts": [
    "StateManager",
    "state management",
    "subpackage facade",
    "re-export",
    "public interface",
    "runtime state",
    "absolute imports"
  ],
  "categories": [
    "runtime",
    "state management"
  ],
  "source_docs": [
    "107fb171aeaeed92"
  ],
  "backlinks": null,
  "word_count": 478,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `state/__init__.py` file is a deliberate facade — it exports exactly one symbol, `StateManager`, from the internal `soul_protocol.runtime.state.manager` module. This thin re-export layer is standard Python packaging practice: it shields consumers from internal reorganization and keeps the public import path stable regardless of how the internal module tree evolves.

## Why This File Exists

Direct imports from deeply nested modules — `from soul_protocol.runtime.state.manager import StateManager` — are brittle. Any internal restructure breaks every caller. A facade at the subpackage root fixes the import path for all consumers at once. This is sometimes called the "public API surface" pattern: the facade is the contract; everything under it is implementation detail.

The file header documents a historical restructure where absolute import paths were corrected from a previous layout. This is exactly the kind of breakage a stable public interface prevents going forward — the refactor happened behind the facade, and no caller needed updating.

## Public Interface

```python
from soul_protocol.runtime.state import StateManager
```

`StateManager` is the sole exported symbol. It manages the mutable runtime state of a digital soul — energy, social battery, mood, and interaction timestamps — and is the correct entry point for any code that needs to read or mutate a soul's live state. Callers never need to know that `StateManager` lives in `state/manager.py`.

## Design Pattern

- **Single-symbol re-export**: `__all__ = ["StateManager"]` makes the contract explicit and prevents accidental star-import of private helpers that happen to be defined in the module.
- **Absolute import paths**: Using `soul_protocol.runtime.state.manager` rather than a relative `.manager` import ensures the module works correctly when imported from different package contexts — CLI entry points, test fixtures, agent plugins, and MCP servers all benefit from the unambiguous absolute path.

## Relationship to the Runtime

The state subpackage sits inside `soul_protocol.runtime`, which also contains `storage/` (persistence backends), `dna/` (personality and DNA prompt generation), `skills/` (skill registry), and `soul.py` (the top-level Soul class that orchestrates everything). The state layer handles only in-memory mutation of the current `SoulState`; persistence is a separate concern delegated to `FileStorage` or `InMemoryStorage` in the storage subpackage.

When `Soul.birth()` creates a new soul, it immediately wraps the initial `SoulState` in a `StateManager`. From that point forward, all state changes — whether from interactions, rest periods, or explicit resets — flow through `StateManager`. The storage layer snapshots the result when `save_soul_full()` is called.

## Stability Guarantee

Because `StateManager` is the only public export and its signature is stable, this subpackage provides a reliable seam for mocking in tests:

```python
from unittest.mock import MagicMock
from soul_protocol.runtime.state import StateManager
mock_manager = MagicMock(spec=StateManager)
```

Any test that injects a mock `StateManager` is insulated from changes to the internal `state/manager.py` implementation.

## Known Gaps

No known gaps. This module intentionally has minimal scope. The single-symbol export is a conscious decision — adding more symbols here would require careful review to avoid leaking internal helpers.