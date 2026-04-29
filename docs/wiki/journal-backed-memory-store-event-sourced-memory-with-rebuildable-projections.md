---
{
  "title": "Journal-Backed Memory Store: Event-Sourced Memory with Rebuildable Projections",
  "summary": "`JournalBackedMemoryStore` is a spike implementation of the `MemoryStore` protocol that treats the append-only journal as the single source of truth, using SQLite FTS5 projections as a rebuildable read cache. It was designed to eliminate the class of bug where cleanup operations irreversibly wiped memory state.",
  "concepts": [
    "event sourcing",
    "journal-backed storage",
    "SQLite FTS5",
    "projection rebuild",
    "memory tiers",
    "GDPR tombstone",
    "BM25 search",
    "append-only log",
    "MemoryStore protocol",
    "WAL mode"
  ],
  "categories": [
    "memory",
    "storage",
    "spike"
  ],
  "source_docs": [
    "ec7d5f7102ae180a"
  ],
  "backlinks": null,
  "word_count": 521,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Why This Exists

The original memory store held state only in a mutable SQLite projection. When a cleanup or migration ran, there was no way to recover erased entries — the projection *was* the truth. This produced a class of catastrophic bug: routine maintenance could silently destroy the soul's entire memory.

`JournalBackedMemoryStore` inverts that relationship. The journal (an append-only event log) becomes truth. The SQLite projection becomes a cache that can be dropped and rebuilt from the journal at any time using `rebuild()`.

## Data Flow

```
write path:
  store() / delete() / promote()
      → emit event to Journal (journal.db)
      → immediately apply event to SQLite projection (projection.db)

read path:
  recall() / search() / layers()
      → query SQLite projection directly (fast)

recovery path:
  rebuild()
      → DELETE all projection rows
      → replay every journal event from seq=0
      → rebuild projection from scratch
```

## Key Components

### Event Types

Four event `action` strings form the memory event vocabulary:

- `memory.remembered` — a new memory was stored
- `memory.forgotten` — a memory was deleted (tombstone; content removed from projection)
- `memory.graduated` — a memory moved to a different tier
- `memory.archived` — a memory was archived (treated like `forgotten` in projections)

### Projection Schema

The SQLite projection uses two tables and one virtual table:

```python
# memory_tier: primary store with importance/emotion/tags/source columns
# fts_memories: FTS5 virtual table with porter+unicode61 tokenizer
# projection_meta: tracks schema_version and last_replayed_seq
```

WAL mode is enabled on the connection to allow concurrent reads during writes.

### FTS5 Search

`_build_fts_query()` converts a free-text user query into a safe FTS5 MATCH expression. It splits on non-alphanumeric characters (matching the unicode61 tokenizer's own rules) and joins tokens with OR. This means `"alice@example.com"` produces the same token set on both sides of the match — preventing the common failure where email addresses or URLs return zero results because FTS special characters break the query syntax.

```python
# Input: "alice@example.com"
# Output: '"alice" OR "example" OR "com"'
```

### GDPR-Safe Deletes

`delete()` writes a `memory.forgotten` tombstone whose payload contains only the `memory_id` and reason. The original `memory.remembered` event in the journal still holds the full content for audit purposes, but the projection immediately removes the row. A future `delete_content_for_gdpr` slice can redact the journal event payload on demand without breaking the rest of the audit trail.

### Idempotent Writes

`_apply_remembered()` uses `INSERT OR REPLACE` to handle the case where `rebuild()` replays events that already exist in the projection. This makes the replay loop safe to interrupt and restart.

## Factory Function

```python
store = open_memory_store(
    base_dir=Path(".soul/memory"),
    actor=Actor(kind="agent", id="did:soul:aria", scope_context=["org:default"]),
)
# Creates: .soul/memory/journal.db + .soul/memory/projection.db
```

## Known Gaps

- `audit_trail()` scans all journal events with a Python-side payload filter rather than a DB index. For souls with large journals this will be slow. A future slice should add a `memory_id` column or payload-key index.
- The `rebuild()` method holds no lock. Concurrent writes during a rebuild could produce an inconsistent projection. A future slice should coordinate this with a write lock or a generation counter.
- The FTS query builder does not support phrase matching or field-scoped queries from user input.