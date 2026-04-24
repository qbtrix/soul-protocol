---
{
  "title": "Archival Memory Store for Conversation History",
  "summary": "Provides long-term, compressed storage for complete conversation sessions via `ArchivalMemoryStore` and `ConversationArchive`. Supports keyword search across summaries and key moments, and date-range queries, without consuming active context.",
  "concepts": [
    "archival memory",
    "ConversationArchive",
    "ArchivalMemoryStore",
    "long-term storage",
    "keyword search",
    "date-range query",
    "memory compression",
    "episodic archival",
    "memory_refs"
  ],
  "categories": [
    "memory",
    "archival",
    "soul-protocol-core"
  ],
  "source_docs": [
    "f30b7678ecfb6f22"
  ],
  "backlinks": null,
  "word_count": 331,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Problem Being Solved

Episodic memory holds individual interaction entries, but individual entries are too granular for long-term history spanning weeks or months. Keeping thousands of raw interactions in active context would overwhelm any LLM's window. The archival tier bridges this gap: conversations are compressed into `ConversationArchive` objects — summary + key moments — and stored outside the active context budget.

## ConversationArchive Model

```python
class ConversationArchive(BaseModel):
    id: str
    start_time: datetime
    end_time: datetime
    summary: str
    key_moments: list[str]
    participants: list[str]
    memory_refs: list[str]  # IDs of extracted MemoryEntry objects
    metadata: dict
```

`memory_refs` links the archive back to the specific `MemoryEntry` objects that were extracted from the session and promoted to semantic or episodic stores. This lets the system trace a recalled memory all the way back to its originating conversation.

## Search Strategy

`search_archives()` uses simple token-overlap ranking — the query is split into tokens and compared against `summary + key_moments`. Archives are scored by overlap count, then by recency as a tiebreaker. This is intentionally lightweight: archival search is a secondary retrieval path, not the primary recall mechanism.

## Date-Range Queries

`get_by_date_range()` uses an overlap condition rather than containment:

```
archive overlaps range if: archive.start_time < range_end AND archive.end_time > range_start
```

This correctly returns archives that started before the range but ended within it, or started within it and ended after — covering partial overlaps.

## Integration with MemoryManager

`MemoryManager.archive_old_memories()` periodically compresses episodic memories older than a threshold into `ConversationArchive` objects. The archived episodic entries are then filtered from active recall results (F2 fix, 2026-03-29), preventing stale interactions from surfacing in everyday queries while keeping them accessible via archival search.

## Known Gaps

- `summary` is a plain string — the caller is responsible for generating it (LLM or rule-based). `ArchivalMemoryStore` does not summarize content itself.
- No persistence layer: archives are stored in-memory in `self._archives`. The `MemoryManager.to_dict()` serializes them, but this module alone has no I/O.
- No relevance ranking beyond token overlap — semantic similarity is not used.