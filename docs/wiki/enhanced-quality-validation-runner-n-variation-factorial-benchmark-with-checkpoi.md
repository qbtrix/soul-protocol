---
{
  "title": "Enhanced Quality Validation Runner — N-Variation Factorial Benchmark with Checkpointing",
  "summary": "Orchestrates a full factorial quality benchmark: N scenario variations × 3 test types × M judge models × 4 ablation conditions, accumulating statistically meaningful results with 95% confidence intervals. Checkpoint/resume logic survives process crashes, and a formatted results table with win rates is printed on completion.",
  "concepts": [
    "factorial benchmark",
    "N-variation",
    "checkpoint resume",
    "confidence interval",
    "win rate",
    "judge models",
    "enhanced runner",
    "response quality",
    "hard recall",
    "emotional continuity",
    "ablation conditions",
    "statistical aggregation",
    "HaikuCognitiveEngine",
    "LiteLLMEngine",
    "asyncio"
  ],
  "categories": [
    "research",
    "quality-evaluation",
    "benchmarking",
    "soul-protocol"
  ],
  "source_docs": [
    "df9b0a0d5112ab97"
  ],
  "backlinks": null,
  "word_count": 394,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Single-scenario quality tests produce noisy scores — one scenario may favor the baseline condition by chance. The enhanced runner runs N variations of each scenario type to produce means and confidence intervals suitable for a research paper. With N=10 and 3 test types, a full run generates 30 scenario × judge evaluations per judge model.

## Factorial Design

The three test types map to distinct scenario generators:

| Key | Test Type | Generator |
|-----|-----------|----------|
| `response` | Response quality | `generate_response_quality_scenarios` |
| `recall` | Hard recall | `generate_hard_recall_scenarios` |
| `emotional` | Emotional continuity | `generate_emotional_continuity_scenarios` |

Each variation uses a different persona and scenario seed, ensuring variation across the N runs rather than repeating the same scenario.

## Checkpoint and Resume

A JSON checkpoint file (`CHECKPOINT_FILE`) is written after each test-judge combination completes. On the next run, completed combinations are loaded and skipped. This is critical for benchmarks that take 30-60 minutes: a crash mid-run doesn't require starting over.

```python
_save_checkpoint(all_results, completed_keys, checkpoint_meta)
```

On successful completion, `_clear_checkpoint()` removes the file so stale checkpoints don't affect future runs.

## Judge Models

Three judge engines are supported:

```python
JUDGE_MODELS = {
    "haiku": {"type": "haiku"},
    "gemini-3-flash": {"type": "litellm", "model": "gemini/gemini-3-flash"},
    "deepseek-v3": {"type": "litellm", "model": "deepseek-chat"},
}
```

Default is `["haiku"]` for speed. Multi-judge runs add Gemini and DeepSeek for inter-rater reliability.

## Statistical Aggregation

`_aggregate_test_results()` computes per-condition:
- Mean score and standard deviation across N variations
- 95% confidence interval using t-distribution approximation
- Win rate: fraction of variations where the condition beat the bare baseline

Results are printed in a table:
```
  Test                  | Full Soul              | RAG Only
  response              | 7.2±0.4 (w:90%)        | 6.1±0.5 (w:70%)
```

## Error Handling Per Variation

Each variation is wrapped in a try/except. On failure, an error dict is appended to the variations list and the run continues. This prevents one failing scenario from aborting the entire benchmark and ensures the checkpoint reflects partial progress.

## CLI Interface

```
python -m research.quality.enhanced_runner --variations 10 --tests response,recall --judges haiku,gemini-3-flash --output research/results/enhanced
```

## Known Gaps

- Variations within a test-judge combination run sequentially. Parallelizing across variations would significantly reduce wall-clock time.
- The checkpoint format is not versioned; schema changes to result dicts will silently corrupt resume logic.
- `CHECKPOINT_FILE` is a hardcoded path, so two concurrent benchmark runs would corrupt each other's checkpoint.