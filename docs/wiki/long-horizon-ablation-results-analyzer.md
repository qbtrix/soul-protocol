---
{
  "title": "Long-Horizon Ablation Results Analyzer",
  "summary": "The `LongHorizonAnalyzer` takes `LongHorizonResults` produced by the runner and computes summary statistics, pairwise Cohen's d effect sizes, and per-scenario breakdowns, then renders a structured markdown report. It is the statistical layer that transforms raw recall hits and memory counts into publishable evidence.",
  "concepts": [
    "Cohen's d",
    "effect size",
    "ablation analysis",
    "recall precision",
    "memory efficiency",
    "bond strength",
    "summary table",
    "pairwise comparison",
    "markdown report",
    "statistical analysis",
    "LongHorizonAnalyzer",
    "FULL_SOUL",
    "RAG_ONLY",
    "BARE_BASELINE"
  ],
  "categories": [
    "research",
    "statistics",
    "ablation-study",
    "soul-protocol"
  ],
  "source_docs": [
    "42bb3e13136acc3d"
  ],
  "backlinks": null,
  "word_count": 438,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`analyze.py` exists because raw runner output — lists of hit/miss booleans and memory counts — is not interpretable as evidence. The analyzer applies standard effect-size statistics and structures the data into a report that can be included directly in a research paper or technical document.

## Condition Ordering

Four ablation conditions are compared, always presented in ascending capability order:

```
BARE_BASELINE → PERSONALITY_ONLY → RAG_ONLY → FULL_SOUL
```

This ordering makes the progression of capabilities visually clear in tables: each column adds one more component of the soul stack.

## Summary Table

`summary_table()` aggregates across all scenarios per condition, computing means for:

- **recall_precision** — fraction of test points where expected content was found
- **memory_efficiency** — memories stored per conversation turn (lower = more selective)
- **total_memories** — raw corpus size
- **bond_strength** — final bond value (only meaningful for FULL_SOUL)

Aggregating across scenarios prevents any single scenario's difficulty from dominating the comparison.

## Cohen's d Effect Sizes

The `cohens_d(group1, group2)` function computes pooled standard deviation effect size:

```python
pooled_std = sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
d = (mean1 - mean2) / pooled_std
```

Edge cases handled:
- Empty groups return 0.0 (avoids division by zero when a condition ran no scenarios)
- Zero pooled standard deviation returns 0.0 (identical distributions)

`_effect_label(d)` maps d to Cohen's conventional thresholds: negligible (<0.2), small (<0.5), medium (<0.8), large (≥0.8).

## Pairwise Comparisons

`pairwise_comparisons()` computes Full Soul vs. each other condition across all four metrics, producing rows like:

| vs Condition | Metric | Delta | Cohen's d | Effect |
|---|---|---|---|---|
| RAG Only | Recall Precision | +0.142 | 1.23 | large |

This table is the primary evidence for the claim that the full psychology stack outperforms each ablated variant.

## Per-Scenario Breakdown

`per_scenario_breakdown()` and the corresponding section in `generate_report()` show condition-by-condition results for each individual scenario, plus the first five missed recalls for Full Soul. Exposing missed recalls serves a diagnostic purpose: it shows researchers which specific facts are hardest to surface, guiding future improvements to the recall pipeline.

## Markdown Report Generation

`generate_report()` returns a complete markdown document with three sections:
1. Summary table
2. Pairwise comparisons with effect sizes
3. Per-scenario breakdowns with missed-recall lists

The report is designed to be pasted directly into a research paper or README.

## Known Gaps

- **No p-value computation**: Cohen's d indicates practical significance but not statistical significance. For a published study, t-tests or Mann-Whitney U tests should be added.
- Bond strength is reported for all conditions but is only meaningfully non-zero for FULL_SOUL; the table could suppress it for other conditions to avoid confusion.