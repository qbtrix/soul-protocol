---
{
  "title": "Runtime Package: Reference Implementation Public API",
  "summary": "The runtime package `__init__.py` defines the public API surface for soul-protocol's reference implementation, currently exporting the Lossless Context Management (LCM) and evaluation subsystems. It serves as the 'batteries-included' layer built on top of the lower-level spec primitives.",
  "concepts": [
    "runtime package",
    "LCMContext",
    "SQLiteContextStore",
    "Evaluator",
    "DEFAULT_RUBRICS",
    "heuristic_evaluate",
    "public API",
    "reference implementation",
    "spec layer",
    "batteries-included"
  ],
  "categories": [
    "runtime",
    "api",
    "context-management",
    "evaluation"
  ],
  "source_docs": [
    "8a3753ae5702844e"
  ],
  "backlinks": null,
  "word_count": 348,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The soul-protocol project is structured in two layers:

- **`spec/`** — Protocol primitives: data models, interfaces, and contracts. Minimal dependencies.
- **`runtime/`** — Reference implementation: opinionated, batteries-included. The comment in source describes it as "the nginx to the protocol's HTTP."

This `__init__.py` declares what the runtime layer exposes publicly. Consumers who want to use soul-protocol's production subsystems import from here rather than reaching into internal modules.

## Current Exports

```python
from .context import LCMContext, SQLiteContextStore
from .evaluation import DEFAULT_RUBRICS, Evaluator, heuristic_evaluate

__all__ = [
    "DEFAULT_RUBRICS",
    "Evaluator",
    "LCMContext",
    "SQLiteContextStore",
    "heuristic_evaluate",
]
```

### Lossless Context Management

- **`LCMContext`** — The primary context window manager. Ingests messages, assembles token-budgeted context windows, and applies three-level compaction (Summary, Bullets, Truncation) when approaching limits.
- **`SQLiteContextStore`** — The persistence backend for LCM. Stores all messages immutably so they remain searchable even after compaction.

### Evaluation Subsystem

- **`Evaluator`** — Scores agent interactions against rubrics (completeness, relevance, helpfulness, specificity). Feeds the evolution trigger system.
- **`DEFAULT_RUBRICS`** — A pre-built set of evaluation rubrics for common domains. Callers can pass custom rubrics or rely on these defaults.
- **`heuristic_evaluate`** — A zero-dependency fallback evaluator that scores interactions using keyword heuristics rather than an LLM. Used when no cognitive engine is configured.

## Design Rationale

Keeping the `__init__.py` focused on explicit re-exports serves two purposes:

1. **Stable API surface**: Internal module reorganization (moving `LCMContext` to a different file, splitting the evaluation module) does not break callers.
2. **Import clarity**: The `__all__` list is the contract. Anything not listed here is considered internal and may change without notice.

## Data Flow Context

The runtime package sits between the spec layer and the application layer:

```
Application
    -> soul_protocol.runtime (this package)
        -> LCMContext (context management)
        -> Evaluator (interaction scoring)
        -> Soul (via soul_protocol.runtime.soul)
    -> soul_protocol.spec (protocol primitives)
```

## Known Gaps

The main `Soul` class and its supporting types (`Bond`, `Identity`, `DNA`, etc.) are not re-exported from the runtime `__init__.py` — callers must import `Soul` from `soul_protocol` (the top-level package) or `soul_protocol.runtime.soul` directly. This is a minor inconsistency that may be addressed in a future cleanup.