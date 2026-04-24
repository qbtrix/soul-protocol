---
{
  "title": "Quick Ablation Runner: Heuristic-Only Long-Horizon Scenario Executor",
  "summary": "A minimal, API-key-free script that runs all long-horizon scenarios through the `LongHorizonRunner` and prints a structured ablation table comparing recall precision, memory count, and bond strength across conditions. It is the fastest way to verify the heuristic pipeline without incurring LLM costs.",
  "concepts": [
    "LongHorizonRunner",
    "build_all_scenarios",
    "heuristic pipeline",
    "recall precision",
    "bond strength",
    "memory efficiency",
    "ablation study",
    "no-API runner",
    "long-horizon scenarios"
  ],
  "categories": [
    "research",
    "ablation",
    "simulation",
    "soul-protocol"
  ],
  "source_docs": [
    "0a8b55e64cc174b7"
  ],
  "backlinks": null,
  "word_count": 348,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

During active development of the Soul Protocol memory pipeline, engineers need fast feedback on whether a code change improved or regressed recall performance. The full ablation pipeline (`run.py`) runs 1000 agents with real LLM calls — too slow for iteration. `run_ablation.py` fills this gap: it runs only the heuristic pipeline (no API key needed) and produces results in seconds.

## Design

The script is intentionally minimal. Its `main()` function does three things:

1. Build all long-horizon scenarios with a fixed seed
2. Run them through `LongHorizonRunner`
3. Print per-scenario, per-condition results

```python
async def main():
    scenarios = build_all_scenarios(seed=42)
    runner = LongHorizonRunner()
    results = await runner.run_all(scenarios)
```

No argument parsing, no output files, no configuration objects. The simplicity is the feature: there is nothing to misconfigure, and the output is always identical given identical source code.

## Output Format

Results print as a two-level table: scenario → condition → metrics.

```
--- adventure_traveler (adventure_traveler_001) ---
  full_soul            | Recall: 8/10 (80.0%) | Memories:   42 (18.1% stored) | Bond:  72.3
  rag_only             | Recall: 10/10(100.0%) | Memories:  553 (100.0% stored) | Bond:   0.0
  personality_only     | Recall: 0/10  (0.0%) | Memories:    0 ( 0.0% stored) | Bond:  68.1
  bare_baseline        | Recall: 0/10  (0.0%) | Memories:    0 ( 0.0% stored) | Bond:   0.0
```

The final "OVERALL AVERAGES" block aggregates across scenarios using `defaultdict` accumulators. This makes cross-condition comparison immediate without requiring a spreadsheet.

## Relationship to Other Runners

| Script | API calls | Agent count | Purpose |
|---|---|---|---|
| `run_ablation.py` | None | all scenarios | Fast heuristic check |
| `run.py` | Yes | 1000 | Full ablation |
| `run_scale_ablation.py` | None | marathon only | 1000-turn scale test |
| `run_dspy_optimization.py` | Yes | all scenarios | DSPy optimization |

## Known Gaps

- No argument parsing: seed, scenario subset, and output format are hardcoded. Adding `--seed` and `--scenarios` flags would make this useful for targeted debugging without editing source.
- The inline `defaultdict` aggregation in `main()` is a copy of logic that also exists in other runners. A shared `aggregate_results()` utility would eliminate this duplication.
