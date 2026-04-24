---
{
  "title": "D6 Identity Continuity Evaluator",
  "summary": "Tests that a soul survives export/import round-trips with full fidelity—preserving DID, OCEAN traits, bond state, memory count, and recall results—and that reincarnation correctly tracks lineage across incarnation chains. Contributes 10% of the Soul Health Score.",
  "concepts": [
    "identity continuity",
    "export/import round-trip",
    "DID",
    "OCEAN traits",
    "bond fidelity",
    "memory_count",
    "Soul.awaken",
    "reincarnation",
    "incarnation chain",
    "previous_lives",
    "tempfile"
  ],
  "categories": [
    "evaluation",
    "identity",
    "soul-health-score",
    "portability"
  ],
  "source_docs": [
    "1b09fbddce559b84"
  ],
  "backlinks": null,
  "word_count": 395,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Identity continuity is the property that makes a soul *portable*. A soul that loses its personality, memories, or bond history when exported and reimported is not a persistent companion—it is a stateless session. D6 tests that the `.soul` file format truly round-trips all identity-bearing state.

## Three Scenarios

### IC-1: Basic Export/Import Round-Trip
Births a soul, observes 30 varied interactions (name, job, hobbies, cat, relationship), exports to a temp `.soul` file, reimports with `Soul.awaken()`, and compares:

- `did`, `name`, `born` (identity hash)
- All 5 OCEAN traits within ε=0.001 (floating point tolerance)
- `bond_strength` within 0.01 and exact `interaction_count`
- Exact `memory_count`

The tolerance values are deliberate. OCEAN traits should be stored as exact floats but floating-point serialization (JSON → string → float) can introduce sub-epsilon rounding. The 0.001 threshold catches real drift while tolerating format noise.

### IC-2: Recall Consistency
Runs 5 recall queries on both the original and reloaded soul, comparing the top-1 result for each query. If both return the same content (or both return nothing), the query is considered consistent.

The threshold for passing is ≥ 80% (4/5 queries). The 20% tolerance allows for non-deterministic retrieval ordering in edge cases without failing the test entirely.

### IC-3: Incarnation Chain
Births a soul, observes 10 interactions, calls `Soul.reincarnate()`, observes 10 more, then verifies:
- `identity.incarnation == 2`
- The original DID appears in `identity.previous_lives`
- The new DID is different from the old DID

This test is skipped in `quick=True` mode. Reincarnation is the mechanism by which a soul can be "reborn" with a new identity while retaining accumulated wisdom—the lineage chain must be auditable.

## Score Formula

```
score = (identity_hash_match * 25)
      + (dna_fidelity * 20)
      + (bond_fidelity * 15)
      + (memory_count_fidelity * 10)
      + (recall_consistency * 20)
      + (incarnation_chain_integrity * 10)
```

## Tempfile Pattern

The export uses `tempfile.TemporaryDirectory` as a context manager:
```python
with tempfile.TemporaryDirectory() as tmpdir:
    soul_path = Path(tmpdir) / "continuity_test.soul"
    await soul.export(str(soul_path))
    reloaded = await Soul.awaken(str(soul_path))
```

The soul must be fully loaded before the context manager exits (which deletes the temp dir). This pattern prevents `.soul` file leakage between test runs.

## Known Gaps

- `rag_recall_precision` is not tested here—RAG-only recall consistency is out of D6's scope but would be a useful extension.
- The 30-interaction corpus in `_TEST_INTERACTIONS` is rich but not randomized. Different seeds would stress-test the serialization format more thoroughly.