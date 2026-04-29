---
{
  "title": "Engine Package Namespace — `soul_protocol.engine`",
  "summary": "An intentionally minimal package initialiser that marks `soul_protocol.engine` as a Python package and documents its role as the runtime implementation layer behind the protocol's `spec/` models.",
  "concepts": [
    "engine layer",
    "spec vs engine",
    "two-layer architecture",
    "soul_protocol.engine",
    "journal engine",
    "package namespace",
    "runtime primitives",
    "Org Architecture RFC"
  ],
  "categories": [
    "architecture",
    "package-structure"
  ],
  "source_docs": [
    "1ba972767c471290"
  ],
  "backlinks": null,
  "word_count": 413,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`src/soul_protocol/engine/__init__.py` is a header-only file with no executable code. Created as part of the Org Architecture RFC (feat/journal-engine, Workstream A slice 2), it marks `soul_protocol.engine` as a Python package and documents the architectural role of the engine layer.

## The Spec / Engine Split

Soul-protocol enforces a strict two-layer separation across all its core subsystems:

```
soul_protocol/
├── spec/      ← Protocol primitives: data models and interfaces only
│              (no storage, no side effects, no opinions)
└── engine/    ← Runtime implementations: concrete behaviour behind spec models
               (storage backends, enforcement logic, scheduling)
```

This separation exists to enable:

- **Testability**: Tests can use lightweight in-memory spec models without pulling in SQLite or other storage dependencies.
- **Substitutability**: The SQLite journal backend can be replaced with a different backend (Postgres, in-memory, cloud-native) without changing any spec code.
- **Portability**: The spec layer can be imported by external tools (validators, exporters, schema generators) without any engine dependencies.

## Concrete Example: The Journal

The journal subsystem illustrates the split clearly:

| Layer | Module | Role |
|-------|--------|------|
| Spec | `soul_protocol.spec.journal` | Defines `EventEntry`, `Actor` data models |
| Engine | `soul_protocol.engine.journal.backend` | Defines `JournalBackend` Protocol |
| Engine | `soul_protocol.engine.journal.journal` | Implements invariant enforcement |
| Engine | `soul_protocol.engine.journal.sqlite` | Implements SQLite storage |

Callers that only need to work with `EventEntry` objects import from `spec.journal`. Callers that need to write to a persistent journal import from `engine.journal`.

## Current Engine Modules

```
src/soul_protocol/engine/
├── __init__.py         ← this file
└── journal/
    ├── __init__.py     ← re-exports Journal, JournalBackend, open_journal, exceptions
    ├── backend.py      ← JournalBackend Protocol (storage contract)
    ├── exceptions.py   ← JournalError hierarchy
    ├── journal.py      ← Journal class with invariant enforcement + hash chain
    ├── scope.py        ← scope_matches, scopes_overlap utilities
    └── sqlite.py       ← SQLiteJournalBackend (production implementation)
```

The comment in this file mentions "fabric" as a future engine module alongside the journal. The fabric module is expected to implement the retrieval routing and credential brokering primitives described in the Org Architecture RFC.

## Naming Convention

Engine modules use short, noun-based names matching the spec primitives they back: `journal/` backs `spec/journal.py`. This naming convention makes it easy to navigate between the contract (spec) and the implementation (engine).

## Known Gaps

- The "fabric" module referenced in the comment does not yet exist. The engine layer currently contains only the journal subsystem.
- There is no explicit enforcement preventing `spec/` modules from importing `engine/` modules; the separation is maintained by convention and code review rather than import guards.
