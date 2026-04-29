---
{
  "title": "Test Suite for Long-Horizon Benchmark Runner",
  "summary": "Validates the multi-condition benchmark runner that processes conversation scenarios through different soul configurations (Full Soul, RAG Only, Personality Only, Bare) and records recall, memory growth, and bond-strength metrics. Async tests use a short 15-turn scenario fixture to keep CI fast while still exercising the full execution path.",
  "concepts": [
    "LongHorizonRunner",
    "benchmark runner",
    "ConditionResult",
    "ScenarioResults",
    "recall",
    "memory growth",
    "bond strength",
    "Full Soul",
    "RAG Only",
    "Bare Baseline",
    "Personality Only",
    "run_all",
    "to_rows"
  ],
  "categories": [
    "testing",
    "long-horizon benchmark",
    "runner",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "85b74cb36275d738"
  ],
  "backlinks": null,
  "word_count": 436,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_runner.py` validates the `LongHorizonRunner`, the component that drives conversation scenarios through multiple experimental conditions and records per-condition metrics. The tests confirm that each condition behaves according to its specification and that the output data structures are well-formed.

## Short Scenario Fixture

`_make_short_scenario()` creates a 15-turn scenario (vs. the production 150-turn default) to keep tests fast in CI without sacrificing behavioral coverage. Because the runner iterates turn by turn, shortening the scenario directly reduces test runtime without changing any logic paths.

## Per-Condition Behavioral Tests

Each condition has dedicated tests asserting its defining contract:

| Condition | Key assertions |
|---|---|
| **Full Soul** | Has memories after processing; builds bond strength |
| **Bare Baseline** | Zero memories; zero recall hits |
| **Personality Only** | No memories stored (OCEAN prompt but no storage layer) |
| **RAG Only** | Stores exactly one memory per turn (raw verbatim storage) |

These tests exist to prevent regressions where a code change silently breaks condition isolation — e.g., RAG storage leaking into the Bare condition or bond strength accumulating in a non-Soul context.

## Memory and Recall Verification

```python
async def test_full_soul_has_richer_memory_than_rag():
    # Full Soul stores episodic + semantic; RAG stores raw turns only
    # Asserts len(full_soul_memories) > len(rag_memories)
```

The comparison between Full Soul and RAG-only memory counts is a core product claim: structured Soul memory is richer than raw retrieval-augmented storage. This test makes that claim falsifiable.

`test_memory_growth_tracked` and `test_recall_results_populated` confirm that the runner samples memory counts and recall metrics at periodic checkpoints, not just at the end — essential for plotting growth curves in the final report.

## Data Structure Tests

- `test_runner_creates_results` — the runner returns a `ScenarioResults` with one entry per condition
- `test_condition_result_properties` — verifies computed properties (e.g., recall rate, memory count) on `ConditionResult` use the underlying raw data correctly
- `test_condition_result_empty` — a `ConditionResult` with all-zero values must not raise on property access (guard against division by zero in rates)
- `test_results_to_rows` — `LongHorizonResults.to_rows()` must produce flat dicts suitable for CSV/DataFrame export; this is the serialization path feeding the analyzer

## Multi-Scenario Execution

`test_run_all` verifies that the runner processes multiple scenarios sequentially, producing combined results. This is the integration-level test ensuring the full benchmark pipeline (not just a single scenario) produces valid output.

## Known Gaps

No TODOs or FIXMEs in the AST. The tests use real runner logic but mock or stub LLM calls via the short scenario fixture — if the runner ever adds a step that requires a live model response (e.g., summarization), the fixture approach may need to be updated to inject a mock engine.