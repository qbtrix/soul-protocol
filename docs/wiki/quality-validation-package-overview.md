---
{
  "title": "Quality Validation Package Overview",
  "summary": "The `research/quality` package contains Soul Protocol's response quality validation infrastructure: test scenarios, experimental condition definitions, LLM-as-judge scoring, and multi-model benchmarking runners. It is the layer that measures subjective quality (how good does the response feel?) rather than infrastructure metrics (how many memories were stored?).",
  "concepts": [
    "quality validation",
    "LLM-as-judge",
    "experimental conditions",
    "response quality",
    "multi-judge",
    "mem0 benchmark",
    "scenario generator",
    "soul-protocol research",
    "ablation"
  ],
  "categories": [
    "research",
    "quality-evaluation",
    "package-structure",
    "soul-protocol"
  ],
  "source_docs": [
    "c22f6cac4b5b5ac9"
  ],
  "backlinks": null,
  "word_count": 257,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

While the `long_horizon` package measures infrastructure correctness — did the right memories get stored and recalled — the `quality` package measures perceived response quality: does having a soul actually make the agent's responses better to a human judge?

The package answers this with an LLM-as-judge design: an independent model scores responses from soul-enabled and baseline agents across six quality dimensions, providing scalable pseudo-human evaluation without recruiting human raters for every experiment.

## Package Contents

| Module | Responsibility |
|--------|---------------|
| `conditions.py` | Defines 4 experimental conditions and `MultiConditionResponder` |
| `judge.py` | LLM-as-judge scoring on 6 quality dimensions |
| `enhanced_runner.py` | N-variation × 4-condition × M-judge orchestration with checkpointing |
| `multi_judge.py` | Multi-model judge runner for inter-rater reliability |
| `mem0_benchmark.py` | Three-way comparison: Soul Protocol vs. Mem0 vs. stateless baseline |
| `scenario_generator.py` | Generates response quality, hard recall, and emotional continuity test cases |

## Design Philosophy

Each module in the package is independently runnable via `python -m research.quality.<module>`. This allows targeted experiments without running the full suite, which matters when individual tests take minutes of LLM time.

The experimental design uses a shared Soul instance across conditions so that personality, memory, and emotional data are identical — only the prompt construction changes. This isolates the effect of each component from confounds in the underlying data.

## Known Gaps

- The `__init__.py` does not re-export any symbols, so callers must import from specific submodules. A public API surface would make the package easier to use from notebooks and external scripts.