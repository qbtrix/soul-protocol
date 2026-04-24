---
{
  "title": "Episodic Memory Store — Autobiographical Interaction History",
  "summary": "Provides `EpisodicStore`, the in-memory repository for timestamped interaction records. Supports both basic and psychology-enriched storage paths, significance-based eviction, GDPR-compliant deletion, and filtering of archived entries from search results.",
  "concepts": [
    "episodic memory",
    "EpisodicStore",
    "interaction history",
    "somatic marker",
    "significance-based eviction",
    "GDPR deletion",
    "archival filtering",
    "psychology pipeline",
    "autobiographical memory",
    "update_entry"
  ],
  "categories": [
    "memory",
    "episodic",
    "soul-protocol-core"
  ],
  "source_docs": [
    "c932284e56b1527e"
  ],
  "backlinks": null,
  "word_count": 293,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## What Episodic Memory Stores

Episodic memories are the soul's diary — each entry records what was said by the user and by the agent, with a timestamp. Unlike semantic facts ("User is vegetarian") or procedural knowledge ("How to reset a password"), episodic entries are event-bound: they happened at a specific time during a specific interaction.

## Two Storage Paths

### Basic Path — `add(interaction)`

Converts an `Interaction` into a `MemoryEntry` with fixed importance 5. Used for simple, non-psychology-enriched pipelines.

### Enriched Path — `add_with_psychology(interaction, somatic, significance)`

Used by the v0.2.0+ observe pipeline. Emotional arousal from the `SomaticMarker` drives importance:

```python
importance = 5
if somatic and somatic.arousal > 0.3:
    importance = min(9, 5 + int(somatic.arousal * 4))
```

Highly emotional interactions (arousal 0.9) reach importance 8–9, making them harder to evict and easier to recall.

## Eviction Policy

When the store reaches `max_entries` (default 10,000), `_evict_least_significant()` removes the entry with the lowest combined `(significance * importance)` score. This preserves emotionally and contextually significant memories over mundane chatter.

## GDPR Deletion

- `search_and_delete(query)` — finds and removes entries matching a keyword query
- `delete_before(cutoff_datetime)` — time-based bulk deletion
- Both methods log deletion counts for audit purposes

## Archival Filtering

Entries with `archived=True` are excluded from `search()` results (F2 fix, 2026-03-29). Once a session is compressed into a `ConversationArchive`, its constituent episodic entries are marked archived so they do not reappear in active recall. They remain accessible via `ArchivalMemoryStore.search_archives()`.

## update_entry() API

The v0.3.x refactor replaced direct `_memories[id]` dictionary access from `MemoryManager` with the public `update_entry(**kwargs)` method. This encapsulates the store's internal representation and allows field validation at the boundary.

## Known Gaps

- `max_entries` is fixed at construction time — there is no dynamic resizing or per-soul configuration from the soul file.