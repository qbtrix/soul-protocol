---
{
  "title": "Soul Health Score Report Renderer",
  "summary": "Renders SoulHealthReport objects into four output formats—markdown table, JSON, RAG comparison table, and an ANSI terminal dashboard—without external dependencies. Provides human-readable and machine-readable views of evaluation results.",
  "concepts": [
    "report rendering",
    "SoulHealthReport",
    "ANSI terminal",
    "markdown table",
    "JSON serialization",
    "RAG comparison",
    "bar chart",
    "score tiers",
    "dashboard",
    "production ready"
  ],
  "categories": [
    "evaluation",
    "reporting",
    "soul-health-score"
  ],
  "source_docs": [
    "e18b29c06db3bb4c"
  ],
  "backlinks": null,
  "word_count": 409,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Evaluation results are only useful if they are readable. This module translates the structured `SoulHealthReport` dataclass into output formats suitable for different audiences: markdown tables for whitepapers, JSON for programmatic processing, comparison tables for positioning against RAG-only baselines, and colorful terminal dashboards for interactive development.

## No External Dependencies

The file header explicitly notes "No external dependencies (no rich, no tabulate)." This is intentional: eval tooling should not require additional packages that might not be available in CI or restricted environments. All formatting is done with string concatenation and ANSI escape codes.

## Four Renderers

### Markdown Report (`render_markdown`)
Produces a full markdown document with a summary table, per-dimension detail section, and a score interpretation block. The interpretation maps score ranges to readiness tiers:

| Score | Status |
|-------|--------|
| ≥ 90 | Production Ready ● |
| ≥ 75 | Strong ◐ |
| ≥ 50 | Developing ○ |
| < 50 | Needs Work ✗ |

### JSON Report (`render_json`)
Serializes the report via `report.to_dict()` with a custom `_default` handler that converts `datetime` objects to ISO 8601 strings. JSON's lack of native datetime support would otherwise raise `TypeError`.

### Comparison Table (`render_comparison_table`)
Renders a Full Soul vs. RAG Only side-by-side table. RAG-only scoring:
- **D1**: gets partial credit from `rag_recall_precision * 50` (if the metric is present in D1 results)
- **D2–D7**: always 0 (RAG has no personality, bond, identity, or self-model)

This table is designed for whitepaper use—demonstrating the quantitative lift of the full soul system over a naive retrieval baseline.

### Terminal Dashboard (`print_dashboard`)
Prints ANSI bar charts for each dimension:
```
D1 Memory Recall          [████████████░░░░░░░░]  63.5/100  (3✓ 0✗)
```

Colors are gated behind `_use_color()`, which checks `sys.stdout.isatty()`. When stdout is redirected to a file or pipe, all ANSI codes are stripped automatically—output is always readable in both contexts.

## Score Tier Symbols

The `_score_label` function returns a `(label, symbol)` tuple. The symbols (`●`, `◐`, `○`, `✗`) were chosen to be visually distinct at a glance in monospace terminals and to render correctly in markdown. A comment notes these were simplified from an earlier version that had overlapping tier symbols.

## Known Gaps

- `render_comparison_table` silently shows `0.0` for D1's RAG baseline if `rag_recall_precision` is not present in `DimensionResult.metrics`—no warning is emitted.
- The markdown interpretation section only covers five ranges but `_score_label` only defines four (the 40–59 "Early Stage" range in the markdown text has no corresponding symbol in `_score_label`).