---
{
  "title": "D7 Portability Evaluator",
  "summary": "Verifies that a soul produces deterministic system prompts regardless of instantiation order, that recall results survive export/reimport unchanged, and that multi-hop engine swap chains preserve memory count and bond state. Contributes 5% of the Soul Health Score.",
  "concepts": [
    "portability",
    "system prompt determinism",
    "recall independence",
    "engine swap",
    "multi-hop migration",
    "Soul.awaken",
    "memory_count",
    "bond_strength",
    "export/import",
    "engine independence"
  ],
  "categories": [
    "evaluation",
    "portability",
    "soul-health-score"
  ],
  "source_docs": [
    "3374abf7bbfeb3d2"
  ],
  "backlinks": null,
  "word_count": 412,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Portability is about engine independence: a soul born on one LLM backend should produce identical behavior when moved to another. D7 tests the surface-level guarantees that make this possible—deterministic prompt generation, stable recall, and multi-hop state preservation.

## Three Scenarios

### PT-1: System Prompt Independence
Births two souls with identical parameters and verifies that `to_system_prompt()` returns byte-for-byte identical output for both. Any non-determinism here—from timestamps, random seeds, or hash ordering—would mean the system prompt changes on every instantiation, breaking downstream LLM behavior.

When prompts differ, the evaluator finds the first differing line and logs it for diagnosis:
```python
for i, (la, lb) in enumerate(zip(lines_a, lines_b)):
    if la != lb:
        diff_line = i
        break
```

### PT-2: Recall Independence
Observes 20 interactions, runs 5 recall queries, exports/reimports, runs the same queries again, and checks that top-1 results are identical. All 5 queries must match for full credit (binary pass).

This validates that the recall index (BM25 or equivalent) is fully serialized to the `.soul` file and produces identical rankings post-reload. Partial scores are not given—a single mismatched query indicates a serialization bug.

### PT-3: Engine Swap Continuity
Simulates a multi-hop migration: birth → observe 20 turns → export → awaken → observe 10 more → export again → awaken again. Verifies that `memory_count` and `bond_strength` on the final soul match the second checkpoint exactly.

This catches accumulation bugs where re-observing interactions after awakening would double-count memories, or where bond state is partially reconstructed.

Skipped in `quick=True` mode.

## Score Formula

```
score = (system_prompt_independence * 35)
      + (recall_independence * 35)
      + (engine_swap_continuity * 30)
```

All three sub-scores are binary (0 or 1), so the total is always a multiple of the weight. A soul that passes all three gets 100; failing any one drops the score by at least 30 points.

## Shared Birth Parameters

All three scenarios use the same `birth_params` dict:
```python
birth_params = dict(
    name="PortabilityTest",
    values=["curiosity", "honesty"],
    ocean={"openness": 0.85, ...},
    persona="I am a portable soul.",
)
```

Sharing parameters ensures that any differences between scenario outcomes are attributable to the export/import process, not to different initial configurations.

## Known Gaps

- PT-3 re-uses turns 10–19 for the second observation phase (overlap with the first 20). This means the second export may include duplicate memories if the significance gate passes the same turn twice—a subtle test validity issue.
- There is no test for cross-version `.soul` file compatibility (e.g., a file exported by `soul_protocol 0.2.2` loaded by `0.2.3`).