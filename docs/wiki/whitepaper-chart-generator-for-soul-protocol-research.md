---
{
  "title": "Whitepaper Chart Generator for Soul Protocol Research",
  "summary": "Generates five publication-quality PNG charts that visualize Soul Protocol's research validation results, covering multi-judge quality tests, component ablation, competitive comparisons (vs. Mem0), judge agreement heatmaps, and a waterfall plot of cumulative score improvements. Each chart is designed to standalone as a figure in the Soul Protocol whitepaper with accessible color coding and clean academic styling.",
  "concepts": [
    "matplotlib",
    "whitepaper charts",
    "ablation study",
    "Soul Protocol benchmarks",
    "multi-judge evaluation",
    "Mem0 comparison",
    "OCEAN personality",
    "waterfall chart",
    "heatmap",
    "Agg backend",
    "color palette",
    "rcParams",
    "figure generation",
    "research visualization"
  ],
  "categories": [
    "research",
    "visualization",
    "benchmarking",
    "whitepaper"
  ],
  "source_docs": [
    "9d71cc9d5b2fd738"
  ],
  "backlinks": null,
  "word_count": 600,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`generate_charts.py` exists to turn raw benchmark numbers into visual evidence. The Soul Protocol research validation produced scores across thousands of simulated runs, and communicating those findings to technical readers requires figures that are immediately interpretable. The script produces five PNG charts saved to an `assets/charts/` directory, one per research tier.

## Why This File Exists

Research claims without visualizations are easy to dismiss. Each chart targets a specific skeptical question:

- **Chart 1** answers: "Did Soul Protocol actually beat a stateless baseline across diverse quality dimensions?"
- **Chart 2** answers: "Which components drive the improvement — memory, personality, or emotion?"
- **Chart 3** answers: "How does Soul Protocol compare to existing tools like Mem0?"
- **Chart 4** answers: "Did different judge models agree, or is this a fluke of one evaluator?"
- **Chart 5** answers: "How much does each layer of the stack contribute incrementally?"

## Chart Inventory

```python
chart_1_multijudge()   # Tier 3: Soul vs Baseline, 4 quality dimensions
chart_2_ablation()     # Tier 4: Full Soul vs RAG Only vs Personality Only
chart_3_mem0()         # Tier 5: Soul vs Mem0 vs Baseline (horizontal bars)
chart_4_judge_heatmap()  # Per-judge agreement heatmap
chart_5_gap_waterfall()  # Baseline -> +memory -> +personality -> +emotion
```

## Color System and Design Choices

The script defines a consistent semantic color palette at module level:

| Constant | Color | Represents |
|---|---|---|
| `SOUL` | Blue (#2563EB) | Full Soul Protocol |
| `RAG` | Amber (#F59E0B) | RAG-only condition |
| `PERSONALITY` | Purple (#8B5CF6) | Personality-only |
| `BASELINE` | Gray (#9CA3AF) | Stateless baseline |
| `MEM0` | Red (#EF4444) | Mem0 competitor |
| `ACCENT` | Green (#10B981) | Positive delta highlights |

This palette is intentionally accessible and maps intuitively (blue = protagonist, gray = baseline). Using module-level constants prevents color drift across charts — if the palette changes, one edit propagates everywhere.

## Matplotlib Backend Choice

The file calls `matplotlib.use("Agg")` before importing `pyplot`. This switches to a non-interactive backend that renders directly to files without requiring a display server. This is critical for running in CI, headless Docker, or on macOS when no GUI session is available. Without this guard, `import matplotlib.pyplot` on a headless server would raise a `_tkinter` error.

## Global Style Configuration

`plt.rcParams.update(...)` applies consistent styling globally:
- `figure.dpi = 200` produces retina-quality images without individual per-figure settings
- `savefig.bbox = "tight"` clips empty whitespace automatically
- Top and right spines are removed for cleaner academic aesthetics

## Chart 4: The Heatmap Rationale

The judge heatmap (`chart_4_judge_heatmap`) exists specifically to address inter-rater reliability. If only one judge model consistently favored Soul Protocol, the results could reflect model bias rather than real quality. Displaying agreement across model families visually demonstrates the finding holds regardless of which LLM performs the evaluation.

## Chart 5: Waterfall Logic

The waterfall chart maps the incremental score gain from each protocol layer: `baseline → +memory → +personality → +emotion → Full Soul`. This sequential decomposition motivates the ablation study design and shows the marginal contribution of each component, defending the claim that all three matter.

## Known Gaps

- Score data is hardcoded as Python literals rather than loaded from the results CSV. If research reruns produce updated numbers, every chart function must be manually updated to match.
- No test coverage exists for the chart functions — PNG byte equivalence is impractical to assert, but smoke tests checking that `OUT/*.png` files are created would catch regressions.
- The `chart_4_judge_heatmap` function signature appears in the AST but its body was not extracted, suggesting it may be a stub or was truncated in the source snapshot.