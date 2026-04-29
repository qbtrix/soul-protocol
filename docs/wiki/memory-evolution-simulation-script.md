---
{
  "title": "Memory Evolution Simulation Script",
  "summary": "A standalone simulation that exercises 100 interactions to demonstrate memory compression, archival storage growth, and temporal knowledge-graph evolution in soul-protocol. It serves as a developer-facing proof that the memory pipeline works end-to-end without a live LLM.",
  "concepts": [
    "memory compression",
    "archival storage",
    "knowledge graph",
    "temporal graph",
    "MemoryEntry",
    "MemoryCompressor",
    "ArchivalMemoryStore",
    "KnowledgeGraph",
    "simulation",
    "memory management",
    "ConversationArchive"
  ],
  "categories": [
    "scripts",
    "memory-system",
    "developer-tools"
  ],
  "source_docs": [
    "1307934ee604137c"
  ],
  "backlinks": null,
  "word_count": 455,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`simulate_memory_evolution.py` is a developer utility that runs 100 scripted interactions through the soul-protocol memory stack and prints a before/after report. Its purpose is to make abstract memory-management behaviour concrete and observable — showing that compression actually reduces entry counts, archival storage actually grows, and the knowledge graph actually accumulates edges over time.

## Why It Exists

Memory management in long-lived AI companions is easy to get wrong silently. Without a visible end-to-end test:

- **Compression** might run but produce no net reduction if the threshold is misconfigured.
- **Archival** might never fire if the trigger condition is never met in unit tests.
- **Graph edges** might stale-accumulate without the temporal pruning that keeps the graph navigable.

By replaying a deterministic set of `TOPICS` (ten domain-labelled sentences spanning technology, hobbies, career, location, preferences, habits, relationships, and projects), the script exercises realistic diversity while remaining reproducible.

## Data Flow

```
TOPICS (10 fixed sentences × 10 cycles = 100 interactions)
        │
        ▼
MemoryEntry objects  ──►  MemoryCompressor  ──►  compressed store
        │
        ▼
ArchivalMemoryStore  ──►  ConversationArchive records
        │
        ▼
KnowledgeGraph  ──►  entity/relation edges  ──►  temporal metadata
```

1. **Setup**: Three components are instantiated fresh — `ArchivalMemoryStore`, `MemoryCompressor`, and `KnowledgeGraph`.
2. **Interaction loop**: Each `MemoryEntry` is created with a `MemoryType` label and fed into all three components.
3. **Midpoint snapshot**: After 50 interactions a snapshot records raw counts for the before/after comparison.
4. **Compression run**: `MemoryCompressor` is triggered explicitly to consolidate entries.
5. **Final report**: Summary stats are printed — compression ratio, archive size, graph node/edge count.

## Key Imports

| Import | Role |
|--------|------|
| `ArchivalMemoryStore` | Writes `ConversationArchive` records to cold storage |
| `MemoryCompressor` | Merges redundant `MemoryEntry` objects into summaries |
| `KnowledgeGraph` | Tracks entity-relation edges with temporal metadata |
| `MemoryEntry` / `MemoryType` | Core data types from `soul_protocol.runtime.types` |

## Patterns Worth Noting

- **Fixed `TOPICS` list** — Keeps the simulation deterministic and easy to diff across versions. Random inputs would make regressions ambiguous.
- **Explicit compression trigger** — Compression is not automatic in the simulation; it is called at the midpoint so the before/after delta is clean.
- **Async entry point** — `run_simulation()` is `async` because the production memory APIs are async; the script uses `asyncio.run()` as the shell harness.

## Known Gaps

- The script has no assertions — it is observational rather than a pass/fail test. A failing compression step would print a 0% reduction but would not exit non-zero.
- `uuid` is imported but `MemoryEntry` IDs may be auto-generated internally; the explicit UUID import suggests planned work to supply deterministic IDs for reproducibility.
- There is no cleanup of the in-memory stores between runs, so repeated calls to `run_simulation()` within the same process would inflate counts.
