---
{
  "title": "Test Suite for JournalBackedMemoryStore Benchmark Harness",
  "summary": "This benchmark harness compares `JournalBackedMemoryStore` against the baseline `DictMemoryStore` across four dimensions: recall quality (recall@5), write latency, search latency, and delete correctness. It was created to produce a data-driven decision on whether the append-only journal architecture is worth adopting, with pass criteria derived from the spike design document.",
  "concepts": [
    "JournalBackedMemoryStore",
    "DictMemoryStore",
    "BM25 search",
    "recall@5",
    "write latency",
    "rebuild",
    "append-only journal",
    "SQLite FTS5",
    "cleanup incident",
    "benchmark harness"
  ],
  "categories": [
    "testing",
    "benchmarks",
    "memory-system",
    "spike",
    "test"
  ],
  "source_docs": [
    "20aa1d0eebe366ec"
  ],
  "backlinks": null,
  "word_count": 576,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose and Context

The `test_benchmark.py` file is a decision harness, not a correctness harness. Its purpose is to quantify whether `JournalBackedMemoryStore` (an SQLite-backed, append-only journal store) can replace `DictMemoryStore` (a plain Python dict store) without regressions in the workflows the captain actually uses. Every benchmark prints timing to stdout and gates on budget thresholds from `docs/memory-journal-spike.md`.

The historical motivation is specific: a cleanup incident in which the dedup heuristic with `dedup=True` at 0.8 Jaccard threshold wiped most production memories. The journal architecture prevents this by making all writes append-only — projections can be wiped and rebuilt from the journal.

## Canonical Corpus

The tests seed a 25-entry `CANONICAL_CORPUS` drawn from real production Soul Protocol session content:

```python
("Ripple widgets use SvelteFlow + ELK.js for graph layouts", "semantic", 8),
("Soul Protocol v0.3.1 shipped the org-level event journal", "semantic", 9),
("The .soul file is a zip archive holding identity + memory", "semantic", 8),
# ... 22 more entries
```

Using real content matters: synthetic lorem ipsum corpora can make BM25 search look better or worse than it performs in production because the token distribution is artificial.

## Benchmark Tests

### Recall Quality (recall@5)

```python
assert candidate_recall >= baseline_recall - 0.1
```

For each of 10 canonical queries, the test checks whether at least one required substring appears in the top-5 search results. The pass criterion is that the journal store's recall rate must not drop more than 10 percentage points below the dict baseline — approximately 1 query of allowable noise.

### Write Latency

A batch of 100 writes is timed on both stores. The journal store includes a warm-up step to trigger SQLite WAL initialization and FTS5 index allocation before the measured run. Without the warm-up, the first write batch would be artificially slow due to file creation overhead:

```python
# Warm-up (SQLite WAL init, FTS5 index allocation).
journal_writer()
dict_writer()
# Reset for clean measurement.
dict_store._data.clear()
journal_store.rebuild()
```

Budget: 100 writes must complete in under 2 seconds.

### Search Latency

A 100-memory corpus is searched with 120 queries (6 topics × 20 repetitions). Budget: under 50ms per query.

### Delete Correctness

`test_benchmark_forget_correctness_vs_dict` validates that deleting one memory removes exactly that memory with no collateral damage — the property the cleanup incident violated. Both stores are tested in parallel:

```python
expected = len(CANONICAL_CORPUS) - 1
assert dict_remaining == expected
assert journal_remaining == expected
```

### Rebuild Safety

The benchmark's signature test: wipe the projection tables (simulating a data loss event), call `rebuild()`, and verify zero data loss:

```python
journal_store._db.execute("DELETE FROM memory_tier")
journal_store._db.execute("DELETE FROM fts_memories")
journal_store._db.commit()
mid = sum(...)  # 0 after wipe
replayed = journal_store.rebuild()
post = sum(...)  # must equal pre
assert pre == post
```

`DictMemoryStore` cannot pass this test — data loss in the dict is permanent. Only the journal store has this property.

### Real Fixture Test (Conditional)

`test_benchmark_real_fixture_roundtrip` loads a real `pocketpaw-snapshot-2026-04-16.soul` file, ingests all memories into the journal store, and measures storage footprint. It is skipped when the fixture file does not exist, making it local-only for the captain's machine.

## Known Gaps

- The `rebuild()` call in the write latency test resets projections but does not replay the warm-up journal events — the comparison may not be entirely apples-to-apples.
- The recall@5 metric does not distinguish between the journal store finding the wrong entry (collision) and finding no entry at all.
- The real fixture test is skipped in CI, meaning the production-scale numbers are never automatically tracked for regression.