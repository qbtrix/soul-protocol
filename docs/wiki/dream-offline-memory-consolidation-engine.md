---
{
  "title": "Dream: Offline Memory Consolidation Engine",
  "summary": "The `Dreamer` class implements offline memory consolidation for soul agents — the async background process that reviews accumulated episodic memories in batch, detects patterns, compacts redundant data, and synthesizes higher-order knowledge. It is the offline counterpart to `observe()`, which handles real-time interaction processing.",
  "concepts": [
    "dream",
    "memory consolidation",
    "Dreamer",
    "DreamReport",
    "topic clustering",
    "procedure detection",
    "behavioral trends",
    "semantic deduplication",
    "graph consolidation",
    "dry_run",
    "OCEAN evolution",
    "episodic memory",
    "procedural memory"
  ],
  "categories": [
    "memory system",
    "offline processing",
    "soul evolution"
  ],
  "source_docs": [
    "eecd3f95618a1640"
  ],
  "backlinks": null,
  "word_count": 531,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Soul Protocol's memory model mirrors human memory consolidation during sleep (Stickgold & Walker, 2013). While `observe()` processes interactions one at a time in real time, `dream()` reviews accumulated episodes in batch to:

1. Detect recurring topic clusters and behavioral patterns
2. Archive and deduplicate old memories
3. Synthesize episodic patterns into procedural memories
4. Generate personality evolution insights from behavioral trends

Without periodic dreaming, episodic memory grows unbounded, semantic facts accumulate duplicates, and the graph accumulates stale/redundant edges.

## Four-Phase Pipeline

### Phase 1: Gather (read-only)
Collects episodes from the episodic store, optionally filtered by a `since` datetime. A key defensive fix handles timezone mismatch: the episodic store may use naive datetimes while `since` may come from timezone-aware sources (MCP vs CLI). Both sides are stripped to naive before comparison to avoid `TypeError`.

### Phase 2: Pattern Detection (read-only, heuristic)

- **Topic clustering** — Episodes are grouped by Jaccard token overlap (`_CLUSTER_THRESHOLD = 0.25`). Clusters with fewer than 3 episodes are discarded. Topic labels are formed from the top 3 most frequent tokens.
- **Procedure detection** — Agent response tokens are normalized into "action signatures". Signatures appearing 3+ times (`_PROCEDURE_MIN_FREQ`) become `DetectedProcedure` candidates.
- **Behavioral trend detection** — Episodes are split chronologically (first half vs second half). Tokens appearing in >30% of the second half but <10% of the first half flag emerging topics; the reverse flags declining topics.

### Phase 3: Consolidation (destructive — skipped in dry_run)

- **Archive old** — Delegates to `MemoryManager.archive_old_memories()`. Reports the **delta** (newly archived count), not cumulative, to prevent misleading reports across successive dream cycles.
- **Semantic deduplication** — Uses token overlap (≥0.85 threshold) to identify duplicate facts. Duplicates are **soft-deleted** via `superseded_by` rather than hard-deleted, preserving an audit trail. The `_find_semantic_duplicates()` helper is shared between the real dedup and the dry-run counter.
- **Graph consolidation** — Merges entity name variants (e.g., "Python" vs "python"), prunes edges expired >30 days ago, and removes exact duplicate edges.

### Phase 4: Synthesis (destructive — skipped in dry_run)

- Detected procedures with confidence ≥ 0.3 are written to procedural memory, skipping any that already have ≥0.6 similarity to an existing procedure.
- OCEAN trait evolution insights are generated from behavioral evidence: topic diversity maps to Openness, planning keyword frequency to Conscientiousness, interaction density to Extraversion.

## Dry-Run Mode

```python
report = await dreamer.dream(dry_run=True)
# report shows what WOULD happen — no mutations applied
```

All four phases run for analysis, but destructive operations (archive, dedup, graph changes, procedure creation) are skipped. The report counters reflect what *would* have happened, enabling safe preview before committing.

## Output: DreamReport

```python
@dataclass
class DreamReport:
    episodes_reviewed: int
    topic_clusters: list[TopicCluster]
    detected_procedures: list[DetectedProcedure]
    behavioral_trends: list[str]
    archived_count: int
    deduplicated_count: int
    graph_consolidation: GraphConsolidation
    procedures_created: int
    evolution_insights: list[EvolutionInsight]
    duration_ms: int
    dry_run: bool
```

The `summary()` method produces a human-readable multi-line text report.

## Known Gaps

- **Agreeableness and Neuroticism** trait mapping in `_analyze_evolution()` are explicitly marked `# TODO` — only Openness, Conscientiousness, and Extraversion are currently mapped.
- The `_count_archivable()` dry-run counter hardcodes a 48-hour cutoff that mirrors `archive_old_memories()`. A comment notes that if the archive logic changes its cutoff, this method must be updated manually — drift is guarded by a specific test (`test_count_archivable_matches_archive_cutoff`).