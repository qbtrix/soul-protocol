---
{
  "title": "Context Package Exports: LCMContext and SQLiteContextStore",
  "summary": "The `runtime/context` package's `__init__.py` provides a clean public surface for the Lossless Context Management (LCM) subsystem, re-exporting `LCMContext` (the reference `ContextEngine` implementation) and `SQLiteContextStore` (the persistence layer) so consumers import from a single stable path rather than internal submodules.",
  "concepts": [
    "LCMContext",
    "SQLiteContextStore",
    "ContextEngine",
    "Lossless Context Management",
    "context package",
    "intra-session context",
    "v0.3.0",
    "compaction",
    "context assembly",
    "public API"
  ],
  "categories": [
    "context management",
    "runtime",
    "package structure",
    "LCM"
  ],
  "source_docs": [
    "6f0b39d862cfc0cc"
  ],
  "backlinks": null,
  "word_count": 440,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `runtime/context` package implements soul-protocol's intra-session context management — the system responsible for keeping conversation history within token budgets using intelligent compaction. This `__init__.py` is the package's stable public API, providing a clean single-import path for the two classes that most consumers need.

## What Gets Exported

```python
from soul_protocol.runtime.context import LCMContext, SQLiteContextStore
```

| Export | Source module | Purpose |
|--------|--------------|---------|
| `LCMContext` | `context.lcm` | Reference `ContextEngine` — manages ingestion, assembly, and compaction |
| `SQLiteContextStore` | `context.store` | Immutable SQLite persistence layer for messages and compaction DAG |

## Why Both Classes Are Exported

`LCMContext` is the typical entry point — most callers create an `LCMContext` and never touch the store directly. However, `SQLiteContextStore` is exported for two legitimate use cases:

1. **Custom `ContextEngine` implementations**: A team building their own window management strategy can reuse the immutable append-only store and its DAG compaction tracking without adopting LCMContext's assembly logic.
2. **Testing and direct inspection**: Tests can verify what was actually written to the database at the row level, without going through the full engine's token counting and assembly code.

## Package Context

The LCM subsystem was introduced in v0.3.0. The design is "batteries-included but not locked-in" — `LCMContext` works out of the box with a single `await lcm.initialize()` call, but teams can swap in a custom `ContextEngine` implementation by satisfying the spec's protocol while reusing `SQLiteContextStore` independently.

## Internal Modules Not Exported

The following modules are intentionally not part of the stable public API:

- `context.compaction` — `ThreeLevelCompactor` is an implementation detail of `LCMContext`
- `context.retrieval` — `grep`, `expand`, `describe` are thin delegation wrappers used by `LCMContext`
- `context.prompts` — `SUMMARY_PROMPT` and `BULLETS_PROMPT` are compaction internals

These are accessible via direct import but are not guaranteed stable across versions. Consumers should import only from `soul_protocol.runtime.context` to insulate themselves from internal module refactors.

## Standalone Use Beyond Soul

`LCMContext` and `SQLiteContextStore` operate entirely independently of the `Soul` class. They can be used as a general-purpose lossless context manager for any LLM application that needs to keep conversation history within a token budget — a chat application, a coding assistant, or any multi-turn agent that runs long sessions.

## Initialization Pattern

```python
from soul_protocol.runtime.context import LCMContext

lcm = LCMContext(db_path=":memory:")  # or a file path for persistence
await lcm.initialize()  # Must be called before any other method
```

Using `":memory:"` creates an in-memory database ideal for tests and ephemeral sessions. A file path enables persistence across process restarts.

## Known Gaps

No `__version__` attribute is exposed at the package level, making it harder to programmatically detect which LCM feature set is available at runtime for compatibility checking.