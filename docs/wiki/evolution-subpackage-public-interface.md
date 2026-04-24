---
{
  "title": "Evolution Subpackage Public Interface",
  "summary": "The `evolution/__init__.py` init re-exports `EvolutionManager` as the sole public entry point for the evolution subsystem. Callers import from `soul_protocol.runtime.evolution` rather than navigating to the `manager` submodule directly.",
  "concepts": [
    "EvolutionManager",
    "evolution subpackage",
    "package init",
    "import boundary",
    "public API",
    "runtime restructure"
  ],
  "categories": [
    "evolution",
    "package-structure",
    "architecture"
  ],
  "source_docs": [
    "d219f5aeaa7b1551"
  ],
  "backlinks": null,
  "word_count": 176,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`evolution/__init__.py` is a one-liner public interface for the evolution subpackage. It exists to enforce a clean import boundary: all callers use `from soul_protocol.runtime.evolution import EvolutionManager` rather than reaching into `soul_protocol.runtime.evolution.manager`.

```python
from soul_protocol.runtime.evolution.manager import EvolutionManager
__all__ = ["EvolutionManager"]
```

## Why a Dedicated Package Init

The evolution subsystem could grow. Today it has only `manager.py`, but future additions might include:
- `triggers.py` — autonomous trigger detection strategies
- `proposers.py` — LLM-based mutation proposers
- `history.py` — long-term evolution analytics

By routing all external imports through `__init__.py`, the internal module structure can evolve (adding, renaming, splitting files) without changing any callsite. The public API remains stable at the package level.

## Import Path History

The module comment records a migration: import paths were updated from `soul_protocol.core.evolution` to `soul_protocol.runtime.evolution` during a runtime restructure. The init absorbed that change so downstream callers never saw it.

## Data Flow

External caller → `soul_protocol.runtime.evolution` → `EvolutionManager` (from `evolution/manager.py`).

## Known Gaps

None. This module is intentionally a thin facade. Its value is entirely in the import boundary it creates.