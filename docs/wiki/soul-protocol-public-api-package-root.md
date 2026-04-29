---
{
  "title": "soul-protocol Public API — Package Root",
  "summary": "The top-level `__init__.py` is the single import surface for all public soul-protocol types, runtime objects, and exceptions. It bridges the two-layer architecture (spec primitives and runtime engine) into a stable, versioned API.",
  "concepts": [
    "public API",
    "package root",
    "__init__.py",
    "two-layer architecture",
    "spec primitives",
    "runtime engine",
    "backward compatibility",
    "Soul",
    "Bond",
    "MemoryEntry",
    "CognitiveEngine",
    "versioning",
    "soul-protocol"
  ],
  "categories": [
    "api",
    "architecture",
    "package-structure"
  ],
  "source_docs": [
    "e693986b1bdf12d6"
  ],
  "backlinks": null,
  "word_count": 418,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`src/soul_protocol/__init__.py` is the canonical entry point for any code that imports `soul_protocol`. It re-exports every symbol that consumers need from both the `spec/` (protocol primitives) and `runtime/` (opinionated engine) layers, and it carries the package version string.

## Two-Layer Architecture

Soul-protocol is split into two layers:

```
soul_protocol/
├── spec/      # Protocol primitives — data models, interfaces, no opinions
│   ├── identity.py      → CoreIdentity, Identity, Participant, BondTarget
│   ├── memory.py        → CoreMemoryEntry, MemoryStore, DictMemoryStore, ...
│   ├── manifest.py      → CoreManifest
│   ├── journal.py       → EventEntry (decision traces)
│   ├── decisions.py     → Decision spec types
│   └── template.py      → role archetype templates
└── runtime/   # Opinionated engine — builds on spec, adds behaviour
    ├── soul.py          → Soul (primary class)
    ├── bond.py          → Bond
    ├── skills.py        → Skill, SkillRegistry
    ├── eternal.py       → eternal storage
    ├── types.py         → MemoryEntry, MemoryType, Mood, ...
    ├── cognitive/       → CognitiveEngine, HeuristicEngine
    ├── memory/          → MemoryManager, SearchStrategy, ...
    └── templates.py     → bundled role archetypes
```

The root `__init__.py` imports from both layers and exposes them under the flat `soul_protocol.*` namespace. This is intentional: callers should never need to know whether a symbol lives in `spec/` or `runtime/`.

## Version History Highlights

| Version | Notable change |
|---------|---------------|
| 0.2.0 | Added psychology types (SomaticMark, mood system) |
| 0.2.1 | `CognitiveEngine`, `HeuristicEngine`, `ReflectionResult` |
| 0.2.2 | `SearchStrategy`, `TokenOverlapStrategy` |
| 0.2.3 | First public release |
| 0.2.9 | General stabilisation pass |
| 0.3.0 | Dream cycle, smart recall, significance short-circuit, `--type` flag |
| 0.3.1 | Org layer (journal + SQLite WAL), `RetrievalTrace`, bundled templates, CLI fix |
| 0.3.2 | Exception classes added to public exports |

## Key Export Groups

- **Core runtime**: `Soul`, `Bond`, `Skill`, `SkillRegistry`, `Eternal`
- **Memory**: `MemoryEntry`, `MemoryType`, `SearchStrategy`, `TokenOverlapStrategy`, `MemoryStore`, `DictMemoryStore`
- **Identity**: `Identity`, `CoreIdentity`, `Participant`, `BondTarget`
- **Psychology**: `Mood`, `SomaticMark`, `CognitiveEngine`, `HeuristicEngine`, `ReflectionResult`
- **Exceptions**: `SoulEncryptedError`, `SoulDecryptionError`
- **Org**: `EventEntry`, `Decision`, `RetrievalTrace`
- **Templates**: bundled role archetype templates

## Backward Compatibility Guarantee

The comment history documents that every version bump preserves all prior public exports. This matters because downstream projects (PocketPaw, MiroFish, any consumer) import from the flat namespace; breaking changes would silently corrupt running agents.

## Known Gaps

- `SomaticMark` and related psychology types appear in the version history but are not individually listed in the visible `__all__`; coverage may be incomplete in the exports.
- The `spec/` vs `runtime/` boundary is a convention enforced by discipline, not by Python packaging; nothing prevents internal code from importing `runtime/` directly into `spec/`.
