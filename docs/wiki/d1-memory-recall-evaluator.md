---
{
  "title": "D1 Memory Recall Evaluator",
  "summary": "Evaluates a soul's ability to recall planted facts across long conversations, measuring recall precision, memory storage efficiency, and resistance to adversarial \"burial\" noise. Contributes 20% of the composite Soul Health Score.",
  "concepts": [
    "memory recall",
    "recall_precision",
    "storage_rate",
    "burial_recall",
    "adversarial burial",
    "LongHorizonRunner",
    "FULL_SOUL",
    "RAG_ONLY",
    "significance gate",
    "long-horizon evaluation"
  ],
  "categories": [
    "evaluation",
    "memory-system",
    "soul-health-score"
  ],
  "source_docs": [
    "ff94a9f7bfac2118"
  ],
  "backlinks": null,
  "word_count": 368,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Memory Recall is the highest-weighted SHS dimension (20%) because it is the foundational capability of a persistent AI companion. If a soul cannot reliably surface facts a user shared earlier, everything else—personality, bond, self-model—becomes irrelevant.

## Metrics

D1 measures three aspects of memory quality:

| Metric | What it captures | Target |
|--------|-----------------|--------|
| `recall_precision` | Fraction of planted facts successfully recalled | ≥ 60% |
| `storage_rate` | `total_memories / total_turns` (lower = more selective) | ≤ 50% |
| `burial_recall` | Recall precision specifically on adversarial_burial scenario | ≥ 50% |

The **adversarial burial** scenario is critical: it plants a fact, then floods the conversation with irrelevant noise turns before issuing the recall query. A naive implementation stores everything and the important fact gets buried under noise; a well-tuned significance gate keeps the noise out.

## Score Formula

```
score = (recall_precision * 50)
      + ((1 - max(0, storage_rate - 0.40)) * 20)
      + (burial_recall * 30)
```

The storage penalty kicks in above a 40% storage rate. Storing more than 4 in 10 turns is considered bloated; the penalty scales linearly to zero at 140% (fully clamped). This prevents a soul from gaming recall_precision by storing everything.

## Implementation Flow

```python
# quick mode: only life_updates scenario (fastest)
# full mode: all scenarios from generate_all_scenarios()
runner = LongHorizonRunner(
    conditions=[ConditionType.FULL_SOUL, ConditionType.RAG_ONLY],
    seed=seed,
)
results = await runner.run_all(scenarios)
```

The runner executes both `FULL_SOUL` and `RAG_ONLY` conditions. Only the `FULL_SOUL` condition contributes to the D1 score; `RAG_ONLY` results are available for the comparison table in `report.py`.

Metrics are aggregated across all scenario results—not averaged per scenario. This weighted aggregation favors scenarios with more recall test points, which are typically the harder ones.

## Quick Mode

When `quick=True`, only the `life_updates` scenario runs. If the adversarial_burial scenario was skipped, `burial_recall_precision` falls back to the overall recall precision. This prevents the metric from unfairly penalizing quick runs with a zero score.

## Known Gaps

The `rag_recall_precision` metric referenced in `report.py`'s comparison table is computed by the LongHorizonRunner but must be explicitly present in `DimensionResult.metrics` for the comparison table to populate D1's RAG baseline. If the runner changes its key names, the comparison table silently shows 0.