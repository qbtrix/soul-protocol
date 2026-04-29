---
{
  "title": "Long-Horizon Ablation Study Package",
  "summary": "The `research/long_horizon` package bundles the scenario generators, ablation runner, and statistical analyzer for Soul Protocol's long-horizon study, which proves that the psychology stack (significance gating, activation decay, somatic markers) produces measurable advantages at 100+ turn conversation scales. The `__init__.py` re-exports the three key classes and five scenario generator functions as the public API.",
  "concepts": [
    "long-horizon study",
    "ablation",
    "LongHorizonRunner",
    "LongHorizonAnalyzer",
    "LongHorizonScenario",
    "TestPoint",
    "scenario generator",
    "psychology stack",
    "memory recall",
    "package API"
  ],
  "categories": [
    "research",
    "ablation-study",
    "package-structure",
    "soul-protocol"
  ],
  "source_docs": [
    "c720c26ceaa66254"
  ],
  "backlinks": null,
  "word_count": 243,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

This package exists to answer a specific research question: does Soul Protocol's multi-layer psychology stack matter at scale, or does a naive RAG approach perform equivalently when conversations grow long?

The hypothesis is that Soul's significance gating keeps the memory corpus lean and precise, while a RAG store that saves everything becomes noisy at high turn counts — degrading BM25 recall precision as the corpus grows.

## Package Structure

Three modules make up the package:

| Module | Responsibility |
|--------|---------------|
| `scenarios.py` | Generates 100-200 turn synthetic conversations with planted facts and test points |
| `runner.py` | Runs scenarios through 4 ablation conditions, collects infrastructure metrics |
| `analyze.py` | Computes statistics, effect sizes, and generates a markdown report |

## Public API

The `__init__.py` re-exports:

```python
from .analyze import LongHorizonAnalyzer
from .runner import LongHorizonRunner
from .scenarios import (
    LongHorizonScenario,
    TestPoint,
    generate_adversarial_burial,
    generate_emotional_rollercoaster,
    generate_life_updates,
)
```

External scripts (e.g., a Jupyter notebook or CLI runner) can import directly from `research.long_horizon` without knowing which submodule each symbol lives in.

## Design Philosophy

The study is intentionally designed to run without an LLM. No API key is required for the core recall and memory-efficiency metrics. This keeps CI-friendly and allows large-scale sweeps without per-run LLM costs. LLM calls are opt-in via DSPy integration for query expansion and significance gating.

## Known Gaps

- `scale_scenarios.py` (the 1000-turn marathon) is not re-exported from this `__init__.py`, so callers must import it directly from `research.long_horizon.scale_scenarios`.