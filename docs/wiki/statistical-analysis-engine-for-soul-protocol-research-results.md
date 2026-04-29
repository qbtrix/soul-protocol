---
{
  "title": "Statistical Analysis Engine for Soul Protocol Research Results",
  "summary": "Provides `ResultsAnalyzer`, which takes flat metric rows from experiment runs and produces statistical summary tables, pairwise condition comparisons with Cohen's d effect sizes and Mann-Whitney U p-values, ablation chains, per-use-case breakdowns, and a full markdown report. All analysis uses stdlib-only dependencies to maximize portability.",
  "concepts": [
    "ResultsAnalyzer",
    "Cohen's d",
    "Mann-Whitney U",
    "effect size",
    "95% confidence interval",
    "ASCII table formatter",
    "ablation chain",
    "key metrics",
    "recall precision",
    "emotion accuracy",
    "bond strength",
    "markdown report",
    "statistical analysis",
    "stdlib-only"
  ],
  "categories": [
    "research",
    "statistics",
    "analysis",
    "soul-protocol"
  ],
  "source_docs": [
    "d7affc342daec15b"
  ],
  "backlinks": null,
  "word_count": 520,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`analysis.py` transforms raw experiment output — one flat dict per agent run — into publication-ready statistical tables. It is designed to run in any Python environment without installing scipy or pandas, using only `statistics` (stdlib) and helpers from `research.metrics`.

## Why Stdlib-Only

The zero-external-dependency requirement exists for portability. The research validation might need to run in minimal Docker images, CI environments, or contributor machines that haven't installed a scientific Python stack. Depending only on stdlib prevents the common failure mode where `pip install scipy` resolves to a different version across environments and subtly changes p-values.

## Condition Ordering

```python
CONDITION_ORDER = [
    MemoryCondition.NONE.value,          # No Memory
    MemoryCondition.RAG_ONLY.value,      # RAG Only
    MemoryCondition.RAG_SIGNIFICANCE.value,  # RAG + Significance
    MemoryCondition.FULL_NO_EMOTION.value,   # Full (no emotion)
    MemoryCondition.FULL_SOUL.value,         # Full Soul
]
```

This ordering is the ablation chain — from weakest to strongest memory condition. Tables and waterfall charts follow this order so readers can track the cumulative contribution of each added capability.

## Key Metric Selection

Of the 11 numeric metrics tracked per run, 6 are designated as `KEY_METRICS` for ablation analysis:

- `recall_precision` — what fraction of recalled memories were relevant
- `recall_hit_rate` — fraction of queries that returned at least one relevant result
- `emotion_accuracy` — how correctly the soul modeled the user's emotional state
- `bond_final` — final bond strength between agent and user
- `personality_drift` — how much the agent's personality changed over sessions (lower = more stable)
- `memory_compression` — ratio of unique memories to total interactions (higher = better deduplication)

## Statistical Methods

Pairwise comparisons use two statistics from `research.metrics`:

- **Mann-Whitney U** (`mann_whitney_u`) — a non-parametric rank test that does not assume normally distributed scores. This is appropriate because quality scores often cluster near ceiling or floor, violating normality assumptions.
- **Cohen's d** (`cohens_d`) — effect size, labeled by magnitude: negligible (<0.2), small (<0.5), medium (<0.8), large (≥0.8)
- **95% CI** (`confidence_interval_95`) — confidence interval around the mean

Significance is reported using `ALPHA = 0.05` with star notation (`***`, `**`, `*`, `ns`).

## ASCII Table Formatter

`format_table()` renders GitHub-flavored markdown tables with configurable per-column alignment:

```python
format_table(
    headers=["Condition", "Recall", "Emotion"],
    rows=[["Full Soul", "0.847", "0.921"]],
    align="lrr"
)
```

The formatter normalizes short rows (padding with empty strings) and computes column widths from max cell content — defensive patterns that prevent IndexError if a row has fewer cells than headers.

## Report Generation

`ResultsAnalyzer.generate_report(output_dir)` writes a complete markdown report including:
1. Summary statistics table (all conditions × all metrics)
2. Pairwise comparisons against the `NONE` baseline
3. Ablation chain: incremental gain from each condition level
4. Per-use-case breakdown (support, coding, companion, knowledge)
5. Methodology notes

The report is also written as a CSV via `_write_csv()` for downstream spreadsheet analysis.

## Known Gaps

- The `ResultsAnalyzer` accumulates all rows in memory. For 20,000+ runs × 11 metrics, this is approximately 200,000 float values — manageable but not streaming. Very large experiments would need chunked processing.
- No multiple comparison correction (Bonferroni or FDR) is applied despite multiple pairwise tests. This is a methodological gap that reviewers may flag — the `ALPHA = 0.05` threshold becomes anti-conservative with many comparisons.