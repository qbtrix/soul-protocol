---
{
  "title": "Journal Engine Public API — `engine.journal` Package",
  "summary": "Re-exports the complete public surface of the journal engine: the `Journal` class, `JournalBackend` protocol, `SQLiteJournalBackend` implementation, the full exception hierarchy, and scope-matching utilities. Callers import from this package rather than individual submodules.",
  "concepts": [
    "journal engine",
    "Journal",
    "JournalBackend",
    "SQLiteJournalBackend",
    "open_journal",
    "JournalError",
    "scope_matches",
    "scopes_overlap",
    "exception hierarchy",
    "__all__",
    "public API"
  ],
  "categories": [
    "journal-engine",
    "architecture",
    "api"
  ],
  "source_docs": [
    "9e8862f2d3be7a5b"
  ],
  "backlinks": null,
  "word_count": 460,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`src/soul_protocol/engine/journal/__init__.py` is the single import point for everything in the journal engine. It re-exports all public symbols from five submodules and declares them in `__all__`, providing a stable, consolidated surface for callers.

## What It Exports

```python
from soul_protocol.engine.journal import (
    Journal,               # High-level append-only journal
    JournalBackend,        # Protocol (storage contract)
    SQLiteJournalBackend,  # Concrete SQLite implementation
    open_journal,          # Factory: open or create a journal at a path
    JournalError,          # Base exception
    SchemaError,           # Incompatible on-disk schema
    IntegrityError,        # Invariant violation on append
    NotFoundError,         # Event/seq not found
    scope_matches,         # Single scope membership check
    scopes_overlap,        # Intersection check for scope lists
)
```

## Why Centralise Exports Here

The journal engine spans five submodules (`backend`, `exceptions`, `journal`, `scope`, `sqlite`). Without a centralised `__init__.py`, callers would need to know the precise submodule that holds each symbol — an implementation detail that would make refactoring costly. Centralising exports here means:

- `from soul_protocol.engine.journal import Journal` always works, even if `journal.py` is later split into smaller files.
- Third-party code is insulated from internal module reorganisations.
- `__all__` provides an explicit, machine-readable list of the public API for documentation generators and linters.

## Symbol Source Map

| Symbol | Source Submodule | Purpose |
|--------|-----------------|---------|
| `Journal` | `journal.py` | Invariant-enforcing high-level journal |
| `open_journal` | `journal.py` | Factory that opens/migrates SQLite journal |
| `JournalBackend` | `backend.py` | Storage Protocol (structural interface) |
| `SQLiteJournalBackend` | `sqlite.py` | Production SQLite implementation |
| `JournalError` | `exceptions.py` | Catchable base for all journal failures |
| `SchemaError` | `exceptions.py` | Incompatible on-disk schema |
| `IntegrityError` | `exceptions.py` | Invariant violation on append |
| `NotFoundError` | `exceptions.py` | Requested event does not exist |
| `scope_matches` | `scope.py` | Check if a scope string matches a filter |
| `scopes_overlap` | `scope.py` | Check if two scope lists share a member |

## Usage Pattern

```python
from soul_protocol.engine.journal import open_journal, IntegrityError

with open_journal("/path/to/org/journal.db") as journal:
    try:
        committed = journal.append(entry)
    except IntegrityError as exc:
        logger.warning("Rejected event: %s", exc)
    events = journal.query(action_prefix="org.", limit=50)
```

## Scope Utilities

`scope_matches` and `scopes_overlap` are re-exported from `scope.py` because they are used by callers building scope-aware queries, not just internally by `Journal.query()`. For example, the org CLI's status projector uses `scopes_overlap` to filter events relevant to the requesting user's scope list.

## Known Gaps

- `scope.py` and `sqlite.py` are imported but not individually documented in the journal engine's higher-level developer guides. The public API of `scope_matches` and `scopes_overlap` (argument semantics, what counts as a match) is documented only in their docstrings.
- `SQLiteJournalBackend` is re-exported here, which couples the public API to the SQLite implementation. If an alternative backend is added later, it would need its own re-export, potentially expanding the `__init__.py` into a backend registry.
