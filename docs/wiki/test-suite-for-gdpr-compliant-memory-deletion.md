---
{
  "title": "Test Suite for GDPR-Compliant Memory Deletion",
  "summary": "Comprehensive tests for Soul Protocol's right-to-erasure implementation, covering query-based, entity-based, and time-based deletion across all memory tiers, with full audit trail verification. Ensures deleted memories become invisible to recall and that audit records never expose the deleted content itself.",
  "concepts": [
    "GDPR",
    "forget",
    "forget_entity",
    "forget_before",
    "right to erasure",
    "audit trail",
    "cascade deletion",
    "memory tiers",
    "knowledge graph",
    "Soul",
    "episodic",
    "semantic",
    "procedural",
    "recall invisibility",
    "privacy"
  ],
  "categories": [
    "testing",
    "privacy",
    "GDPR",
    "memory",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "27d787ec770819f2"
  ],
  "backlinks": null,
  "word_count": 422,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

GDPR's right to erasure requires that forgotten data be truly gone from all storage layers, not merely hidden. `test_gdpr_deletion.py` verifies that `Soul.forget()`, `Soul.forget_entity()`, and `Soul.forget_before()` collectively satisfy this requirement and maintain a tamper-evident audit trail.

## Fixture Design

```python
@pytest.fixture
async def soul():
    s = await Soul.birth(
        name="TestSoul",
        personality="A test soul for deletion testing.",
        values=["privacy", "trust"],
    )
    ...

@pytest.fixture
async def soul_with_memories(soul):
    # Soul pre-loaded with diverse memories across tiers
    ...
```

The `soul_with_memories` fixture pre-populates all memory tiers (episodic, semantic, procedural) and the knowledge graph, ensuring each deletion test runs against a realistic data set rather than a trivially empty store.

## Deletion Strategies

### Query-Based (`forget(query)`)
- `test_forget_removes_matching_memories` — search terms remove matching entries across tiers.
- `test_forget_preserves_unrelated_memories` — non-matching entries survive intact.
- `test_forget_returns_per_tier_breakdown` — the return value enumerates how many entries were deleted per tier, enabling callers to audit the operation.
- `test_forget_no_matches_returns_zero` — a query that matches nothing returns zeros rather than raising an error.

### Entity-Based (`forget_entity(entity)`)
- `test_forget_entity_removes_graph_node` — the entity node itself is removed from the knowledge graph.
- `test_forget_entity_removes_connected_edges` — all edges incident to the entity are also removed (cascade deletion), preventing dangling references.
- `test_forget_entity_removes_related_memories` — memories that reference the entity are purged from all tiers.

### Time-Based (`forget_before(timestamp)`)
- `test_forget_before_removes_old_memories` — entries older than the cutoff are deleted.
- `test_forget_before_preserves_recent_memories` — entries newer than the cutoff survive.
- Per-tier breakdown is returned, matching the pattern of query-based deletion.

## Audit Trail

Every deletion operation appends to an immutable audit log. Tests in `TestDeletionAuditTrail` verify:

- Each audit entry contains required fields (timestamp, operation type, query/entity, count).
- Audit entries do **not** contain the deleted content — only metadata. This is a critical privacy constraint: the audit trail must prove deletion happened without reconstituting the deleted data.
- The trail accumulates across multiple operations.
- No audit entry is created when nothing was deleted.
- All three deletion strategies (`forget`, `forget_entity`, `forget_before`) produce audit entries.

## Recall Invisibility

`TestDeletedMemoriesInvisible` confirms that deleted memories do not appear in subsequent `recall()` results — the core user-facing guarantee of the right to erasure.

## Store-Level Tests

`TestStoreLevel` targets the underlying storage primitives directly:

- Episodic, semantic, and procedural stores each have search-and-delete methods.
- Episodic store exposes a `delete_before()` for bulk time-range deletion.
- Knowledge graph exposes `remove_entity()` which handles cascade edge removal.

## Known Gaps

- No tests for concurrent deletion (two goroutines/tasks deleting the same memory simultaneously).
- No tests for deletion across persisted-to-disk stores — only in-memory fixtures are used.