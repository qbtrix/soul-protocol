---
{
  "title": "Journal Engine Error Hierarchy — `exceptions.py`",
  "summary": "Defines the four-class exception hierarchy for the journal engine, with `JournalError` as the catchable base class and three specialisations covering schema incompatibility, invariant violations, and missing records.",
  "concepts": [
    "JournalError",
    "SchemaError",
    "IntegrityError",
    "NotFoundError",
    "exception hierarchy",
    "journal engine",
    "append invariants",
    "schema migration",
    "error handling"
  ],
  "categories": [
    "journal-engine",
    "error-handling"
  ],
  "source_docs": [
    "2c9396f8034ffa54"
  ],
  "backlinks": null,
  "word_count": 477,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`exceptions.py` establishes the error taxonomy for the journal engine. All four classes are pure Python `Exception` subclasses with no custom attributes — the design is intentionally minimal to keep the exception hierarchy stable as the engine evolves.

## The Hierarchy

```
Exception
└── JournalError           ← catch all journal failures here
    ├── SchemaError        ← on-disk schema is incompatible with this engine
    ├── IntegrityError     ← append would violate a defined invariant
    └── NotFoundError      ← requested event, seq, or id does not exist
```

## Design Rationale: Common Base Class

`JournalError` exists so callers that do not care which specific failure occurred can write a single, future-proof handler:

```python
try:
    journal.append(entry)
except JournalError as exc:
    logger.error("Journal operation failed: %s", exc)
```

Without a shared base class, any new exception type added in a later version would silently fall through existing handlers. The common base is a forward-compatibility guarantee.

## Individual Exceptions

### `SchemaError`

Raised during `open_journal()` when the SQLite database exists but its schema version does not match what the current engine expects. This prevents silent data corruption that would occur if a newer engine tried to write records in a format that an older engine cannot parse. The correct response is either to run a migration or to roll back the engine version.

### `IntegrityError`

Raised by `Journal.append()` when a new event would violate one of the journal's defined invariants:

- Timestamp is timezone-naive or in a non-UTC timezone
- Timestamp is earlier than the previous event's timestamp (monotonic ordering violation)
- Any Pydantic model-level validation failure on `EventEntry` fields

`IntegrityError` is the journal's defence against corrupted or deliberately malformed events reaching permanent storage. An event that violates an invariant is rejected entirely — the journal does not partially write or silently coerce bad data.

### `NotFoundError`

Raised by `Journal.query()` and `Journal.replay_from()` when a caller requests a specific sequence number, event ID, or named record that does not exist in the journal. Unlike `IntegrityError` (which signals a bad write), `NotFoundError` signals a bad read — typically a programming error in the caller (e.g., using a stale sequence number after the journal has been rebuilt).

## Import Pattern

All three specialisations are re-exported from `soul_protocol.engine.journal.__init__`:

```python
from soul_protocol.engine.journal import (
    JournalError,
    SchemaError,
    IntegrityError,
    NotFoundError,
)
```

Callers should always import from the package, not from `exceptions.py` directly, so that future reorganisations do not break imports.

## Known Gaps

- None of the exceptions carry structured attributes (e.g., `expected_version` / `actual_version` for `SchemaError`). Callers must parse the error message string for diagnostic details, which is brittle for programmatic handling.
- There is no `LockError` or `TimeoutError` subclass for cases where the SQLite WAL lock cannot be acquired within a deadline — a scenario that occurs under concurrent write load.
- `IntegrityError` and Python's built-in `sqlite3.IntegrityError` share the same name. Code that imports both must alias one to avoid shadowing.
