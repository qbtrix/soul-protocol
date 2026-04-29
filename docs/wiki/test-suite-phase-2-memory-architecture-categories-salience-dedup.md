---
{
  "title": "Test Suite: Phase 2 Memory Architecture (Categories, Salience, Dedup)",
  "summary": "Tests for the Phase 2 memory architecture improvements: the MemoryCategory enum, generated abstracts, salience scoring, the deduplication reconcile_fact pipeline, TemporalEdge metadata in the knowledge graph, and the EpisodicStore entry-update API.",
  "concepts": [
    "MemoryCategory",
    "classify_memory_category",
    "generate_abstract",
    "compute_salience",
    "reconcile_fact",
    "TemporalEdge",
    "EpisodicStore",
    "deduplication",
    "salience",
    "memory classification",
    "progressive disclosure"
  ],
  "categories": [
    "memory",
    "testing",
    "phase-2",
    "deduplication",
    "test"
  ],
  "source_docs": [
    "5da67a7edb8df476"
  ],
  "backlinks": null,
  "word_count": 474,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Phase 2 Memory Architecture

`test_memory_v2.py` covers the Phase 2 memory system added in 2026-03-13. Where the original memory system stored raw content and importance scores, Phase 2 adds structured classification, auto-generated summaries, a salience metric, and a deduplication pipeline for conflicting semantic memories.

### MemoryCategory Enum

Phase 2 introduces seven structured categories for classifying semantic memories:

| Category | Description |
|----------|-------------|
| `PROFILE` | Facts about the user's identity (name, location) |
| `PREFERENCE` | User likes, dislikes, preferences |
| `ENTITY` | Named things (people, projects, tools) |
| `EVENT` | Time-bound occurrences |
| `CASE` | Problem/solution pairs |
| `PATTERN` | Recurring behaviors |
| `SKILL` | Capabilities and how-tos |

`TestMemoryCategory` verifies all seven enum values exist, their string representations are stable, and the type is a `StrEnum`.

### classify_memory_category

`TestClassifyMemoryCategory` validates the keyword-based classifier from `cognitive.engine`:

```python
classify_memory_category("User prefers dark mode")  # → PREFERENCE
classify_memory_category("Meeting on Monday")       # → EVENT
classify_memory_category("Alice is a developer")    # → PROFILE
```

Priority ordering matters — `test_preference_takes_priority_over_entity` ensures that "User likes Alice" is classified as PREFERENCE (not ENTITY) because preference keywords take precedence. Case-insensitive matching is also verified.

### generate_abstract

`TestGenerateAbstract` tests the auto-summary function that produces `MemoryEntry.abstract`:

- Extracts the first sentence (period, exclamation, or question mark)
- Falls back to the first line if no sentence boundary exists
- Truncates at 400 characters at a word boundary with an ellipsis
- Returns empty string for empty content

Abstracts power the progressive disclosure feature — overflow entries in recall use the abstract instead of full content to stay within context limits.

### compute_salience

```python
# Weighted sum: novelty(0.3) + emotional(0.3) + relevance(0.2) + recency(0.2)
compute_salience(novelty=1.0, emotional=1.0, relevance=1.0, recency=1.0)  # → 1.0
```

`TestComputeSalience` verifies the additive boost model where salience defaults to 0.5 (mid-range), with higher values reflecting more memorable entries. The v0.3.4-fix updated tests to reflect the additive model.

### reconcile_fact (Deduplication Pipeline)

`TestReconcileFact` validates the deduplication logic for conflicting semantic facts:

```python
reconcile_fact(existing_entry, new_entry)
# → marks old entry as superseded_by=new_id, returns updated entries
```

This prevents the same fact from being stored twice with conflicting values (e.g., "User lives in NYC" vs "User moved to LA"). The `superseded_by` field chains fact revisions without deleting history.

### TemporalEdge in KnowledgeGraph

`TestTemporalEdge` verifies that edges in the knowledge graph carry temporal metadata (`valid_from`, `valid_until`) so the graph can represent evolving relationships, not just static facts.

### EpisodicStore.update_entry

A late addition (2026-03-13), `update_entry()` patches fields on an existing episodic entry. Tests verify partial updates don't clobber unmodified fields and that unknown IDs raise a `KeyError`.

### Known Gaps

Keyword classification for the `CASE` and `PATTERN` categories has limited test coverage. The classifier relies on a fixed keyword list, so novel phrasings that don't match known keywords return `None` (unclassified) even when the content clearly belongs to a category.
