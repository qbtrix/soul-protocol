---
{
  "title": "Test Suite for Long-Horizon Benchmark Analysis (Cohen's d, Effect Labels, Report Generation)",
  "summary": "Validates the statistical analysis layer of the long-horizon benchmark framework, covering Cohen's d calculation, effect-size labeling, and the LongHorizonAnalyzer that produces summary tables and Markdown reports from experimental results. Uses a deterministic mock-results factory to isolate the analysis logic from live LLM calls.",
  "concepts": [
    "Cohen's d",
    "effect size",
    "LongHorizonAnalyzer",
    "summary table",
    "pairwise comparison",
    "Markdown report",
    "mock results",
    "recall precision",
    "bond strength",
    "memory efficiency",
    "benchmark analysis",
    "effect label",
    "long-horizon"
  ],
  "categories": [
    "testing",
    "long-horizon benchmark",
    "statistics",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "15e2a6701214f1c6"
  ],
  "backlinks": null,
  "word_count": 529,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_analyze.py` verifies the correctness of the statistical and reporting components used after a long-horizon benchmark run completes. It sits above the runner layer — by the time these tests run, raw `LongHorizonResults` already exist; the analyzer's job is to distill those into human-readable comparisons and structured tables.

## Cohen's d (TestCohensD)

Cohen's d is the effect-size statistic chosen to compare recall, memory efficiency, and bond strength across experimental conditions (Full Soul vs. RAG-only vs. bare baseline). The tests cover:

- **Identical groups** — d must be 0.0 (no effect)
- **Different groups** — d must be non-zero and directional
- **Empty or single-element groups** — guards against division-by-zero; degenerate inputs must not crash
- **Large effect** — confirms the formula returns a value ≥ 0.8 for clearly separated distributions

These edge-case tests exist because real benchmark runs can produce conditions with very few samples if a scenario is short or a condition fails to produce output.

## Effect Labeling (TestEffectLabel)

Effect labels (`negligible`, `small`, `medium`, `large`) convert a raw d value into a readable word for the report. Tests confirm:

- Standard thresholds: |d| < 0.2 → negligible, 0.2–0.5 → small, 0.5–0.8 → medium, ≥ 0.8 → large
- **Negative large** — a d of −0.8 must still label as `large` (magnitude, not sign). This prevents a sign-check bug where negative d values fall through the labeling logic.

## LongHorizonAnalyzer (TestLongHorizonAnalyzer)

The analyzer consumes a `LongHorizonResults` object and produces:

### Summary Table
- Every benchmark condition (Full Soul, RAG Only, Personality Only, Bare) must appear as a row
- Spot-checks on recall, memory efficiency, and bond strength verify the means match the known mock values

### Pairwise Comparisons
- The comparison dict is non-empty
- Specific pairings (Full Soul vs. RAG, Full Soul vs. Bare) check both the direction and magnitude of Cohen's d

### Report Generation
```python
analyzer = LongHorizonAnalyzer(results)
report = analyzer.generate_report()  # returns Markdown string
```
- Output must start with `#` (Markdown heading)
- Condition names must appear verbatim in the body
- At least one numeric value must be present — confirming real data was serialized

## Mock Data Factory

`_make_mock_results()` builds a `LongHorizonResults` with controlled values (e.g., Full Soul recall = 0.9, RAG recall = 0.6). This is essential because the benchmark runner itself makes LLM calls — the analysis tests must not require a live model. The mock isolates the statistical layer from the I/O layer entirely.

## Edge Cases (TestEdgeCases)

- **Empty results** — analyzer built on zero data must not raise; it should return an empty or gracefully degraded table
- **Single scenario** — only one scenario present; pairwise comparisons must still function with N=1
- **Single condition** — only one experimental arm; inter-condition comparisons are vacuous but must not crash

These tests prevent the report pipeline from failing silently when early benchmark runs are incomplete or a condition configuration is invalid.

## Known Gaps

No TODOs or FIXMEs flagged in the AST. The mock factory covers the happy path well, but there are no tests for non-numeric or `NaN` values in result fields, which could arise if an LLM returns unparseable output during a real benchmark run.