---
{
  "title": "ProceduralStore: How-To Memory Storage and GDPR Deletion",
  "summary": "Provides an in-memory store specifically for procedural memories — step-by-step how-tos and learned processes. Includes token-overlap relevance search and GDPR-targeted deletion operations added in v0.3.",
  "concepts": [
    "procedural memory",
    "how-to memory",
    "memory store",
    "GDPR deletion",
    "token-overlap search",
    "relevance scoring",
    "memory tier",
    "in-memory store",
    "delete_before",
    "search_and_delete"
  ],
  "categories": [
    "memory",
    "storage",
    "GDPR",
    "procedural"
  ],
  "source_docs": [
    "6f39a0109a9ed25c"
  ],
  "backlinks": null,
  "word_count": 519,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Procedural memories are a distinct tier in Soul Protocol's five-layer memory architecture. Where episodic memories record *what happened* and semantic memories record *what is true*, procedural memories capture *how to do things*: deployment commands, workflow preferences, debugging recipes. Storing them separately lets the recall pipeline surface actionable knowledge with a dedicated type filter rather than competing against factual or narrative memories.

## Class Design

`ProceduralStore` is an async-first dict-backed store keyed by memory ID:

```python
class ProceduralStore:
    def __init__(self) -> None:
        self._procedures: dict[str, MemoryEntry] = {}
```

The in-memory design is intentional — Soul Protocol persists to `.soul` archives on save, so runtime state is always ephemeral. The dict provides O(1) lookup for targeted removal.

## Forced Type Tagging

`add()` enforces `MemoryType.PROCEDURAL` regardless of what the caller passed in:

```python
entry.type = MemoryType.PROCEDURAL
```

This prevents inconsistencies when a caller stores a semantic memory using the wrong store. Without this guard, a `recall(types=[MemoryType.PROCEDURAL])` filter would silently miss entries added with incorrect types.

## Relevance-Scored Search

Early versions used substring matching. The replacement with `relevance_score()` from `search.py` provides token-overlap scoring — entries scoring 0.0 are excluded entirely, then results are ranked by relevance descending, then importance descending, then recency:

```python
scored.sort(key=lambda t: (-t[0], -t[1].importance, -t[1].created_at.timestamp()))
```

The composite sort key ensures that when two entries have equal relevance (common when queries match many short tokens), the more important and more recent memory wins.

## GDPR-Targeted Deletion

Added in 2026-03-10, `search_and_delete()` lets callers remove all procedures matching a query — for example, erasing everything the soul knows about a particular technology stack. `delete_before(timestamp)` removes all procedures created before a date for time-based data retention policies:

```python
async def delete_before(self, timestamp: datetime) -> list[str]:
    to_delete = [pid for pid, p in self._procedures.items()
                 if p.created_at < timestamp]
    for pid in to_delete:
        del self._procedures[pid]
    return to_delete
```

Both return lists of deleted IDs so the caller (usually `MemoryManager`) can log the deletion audit trail required for GDPR Article 30 records.

## Known Gaps

- The store is purely in-memory. Under heavy write loads, there is no size cap — unlike `SemanticStore`'s `max_facts` eviction, `ProceduralStore` will grow unboundedly until the soul is saved and re-awakened.
- No deduplication: adding the same procedure twice creates two entries with different UUIDs. The soul relies on the LLM observing duplicates during reflection to prune them.

## ID Generation and Type Enforcement

When an entry arrives without an ID, a 12-character hex UUID is generated:

```python
if not entry.id:
    entry.id = uuid.uuid4().hex[:12]
```

Twelve characters (48 bits) provides enough uniqueness for any realistic soul's memory count while keeping IDs short enough to be human-readable in logs. The type enforcement (`entry.type = MemoryType.PROCEDURAL`) then runs unconditionally, even if the caller already set the correct type — this defensive overwrite prevents the class invariant from being violated by caller bugs.

## List All Procedures

The `entries()` method returns all stored procedures as a flat list without scoring:

```python
def entries(self) -> list[MemoryEntry]:
    return list(self._procedures.values())
```

This is used by the `RecallEngine` for full-scan operations (e.g., during `dream()` consolidation) where relevance scoring is applied externally rather than inside the store.
