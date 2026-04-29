---
{
  "title": "Dream Engine Test Suite — Memory Consolidation and Behavioral Analysis",
  "summary": "Comprehensive test suite for the soul-protocol `dream` subsystem, which performs offline memory consolidation: clustering topics, detecting recurring procedures, pruning duplicates, and suggesting personality evolution. Tests span unit-level phase functions through full integration scenarios with before/after memory state comparisons.",
  "concepts": [
    "dream consolidation",
    "memory clustering",
    "procedure detection",
    "semantic deduplication",
    "behavioral trends",
    "knowledge graph pruning",
    "DreamReport",
    "soft delete",
    "superseded_by",
    "episodic memory",
    "dry run",
    "personality evolution"
  ],
  "categories": [
    "testing",
    "memory",
    "dream-engine",
    "test"
  ],
  "source_docs": [
    "aa7537e6408c0804"
  ],
  "backlinks": null,
  "word_count": 494,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The dream engine runs during idle periods to consolidate a soul's episodic memories into higher-order knowledge. It is analogous to sleep-based memory consolidation in neuroscience — raw episodes are clustered, procedural patterns extracted, near-duplicates pruned, and knowledge graphs cleaned. This test suite validates every processing phase independently and then the full pipeline.

## Why This Exists

Without dream consolidation, a soul accumulates redundant facts, loses signal in noise, and cannot form durable skills from repeated behaviors. The dream engine prevents memory entropy. The tests exist to ensure each consolidation step is correct in isolation before being trusted in production, where mutations to a live soul's memory store are irreversible.

## Test Structure

### DreamReport

Validates the report dataclass: default zero-values, required summary fields, and the cap at 5 displayed clusters (a UX decision to avoid overwhelming reports).

### Gather Phase

```python
# test_gather_filters_episodes_after_since()
# Verifies timestamp-based filtering is inclusive at the boundary
```

The `_gather_episodes(since=...)` function filters by timestamp. The boundary-inclusive test matters because off-by-one errors in time comparisons would silently drop the most recent episode.

### Topic Clustering

`_detect_topic_clusters()` groups episodes by shared terms. Tests verify that:
- Distinct topics form separate clusters
- Small clusters below the minimum size are discarded (preventing trivial 1-episode "trends")
- Clusters are sorted by episode count descending (most active topics first)

### Procedure Detection

`_detect_procedures()` finds recurring agent-response patterns that indicate learned behaviors. Tests verify the minimum frequency threshold: patterns seen fewer than N times are ignored, preventing noise from being promoted to procedures.

### Behavioral Trend Detection

Splits the episode window in half and compares topic frequency. Emerging topics (growing in second half) and declining topics (fading from first half) are surfaced. Requires at least 6 episodes — the test `test_fewer_than_six_episodes_returns_no_trends` guards the guard.

### Semantic Deduplication

```python
# _dedup_semantic() — removes facts with >= 85% token overlap
async def test_removes_near_duplicate_facts()
async def test_dedup_soft_deletes_via_superseded_by()
```

This phase performs soft deletion: duplicate facts get a `superseded_by` pointer rather than being erased. This preserves audit trails. The 85% overlap threshold prevents removing legitimately similar but distinct facts.

### Dry Run

`dream(dry_run=True)` runs analysis without mutating any memory store. Tests confirm:
- The semantic store is unchanged after dry run
- The report `dry_run` flag is set
- The 48-hour archival cutoff logic and minimum-three guard are respected

### Graph Consolidation

`_consolidate_graph()` merges case-insensitive duplicate entities (e.g., "Python" and "python"), prunes edges expired over 30 days, and removes exact-duplicate edges. The 30-day window keeps recent connections alive while discarding stale relationships.

### End-to-End Integration

`TestSoulDreamIntegration` wires through the full `Soul.dream()` method. `TestDreamBeforeAfterSimulation` is the most behaviorally rich: it runs 20 interactions, calls dream, and prints a before/after memory state to stdout — providing a human-readable regression baseline.

## Known Gaps

No test covers the interaction between the consolidation phases when all run together (e.g., topic clusters feeding into procedure synthesis). The integration tests use the full pipeline but do not assert on intermediate state between phases.