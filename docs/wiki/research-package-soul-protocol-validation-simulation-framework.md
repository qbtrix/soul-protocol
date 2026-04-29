---
{
  "title": "Research Package: Soul Protocol Validation Simulation Framework",
  "summary": "The `research/` package is a large-scale simulation framework designed to validate Soul Protocol's psychology-informed memory claims at publication grade, running 1,000 simulated agents across 5 memory conditions and 4 use cases for more than 20,000 experimental runs. It is structured for reproducibility and statistical rigor.",
  "concepts": [
    "simulation framework",
    "experimental design",
    "OCEAN personality",
    "memory conditions",
    "ablation study",
    "reproducibility",
    "random seed",
    "statistical validation",
    "20000 runs",
    "publication-grade",
    "independent variable",
    "dependent variable"
  ],
  "categories": [
    "research",
    "simulation",
    "validation",
    "soul-protocol"
  ],
  "source_docs": [
    "50a19d18dddeb9c6"
  ],
  "backlinks": null,
  "word_count": 454,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `research/` package provides the scientific grounding for Soul Protocol's claims that psychology-informed memory selection outperforms naive RAG. The package header states the design goal plainly:

> 1000 simulated agents x 5 memory conditions x 4 use cases = 20,000+ experimental runs. Designed for reproducibility and publication-grade statistical analysis.

This is not a demo or a benchmark script — it is a controlled experiment framework. Every design decision (seeded random number generators, configurable OCEAN distributions, five conditions from stateless to full soul) exists to make the results defensible to technical reviewers.

## Why Simulation Instead of Real Users

Running 20,000+ experimental conversations with real users is impractical and introduces confounding variables (user mood, question quality, off-topic tangents). Simulated agents with known OCEAN personality distributions allow the experiment to:

- Hold the agent distribution constant across all conditions
- Replay the same interaction sequences under different memory conditions
- Generate statistically sufficient sample sizes without ethical review boards
- Reproduce results exactly by seeding the random number generator

The validity argument rests on the simulation being realistic enough — agents with truncated-normal OCEAN distributions, diverse archetypes, and use-case-appropriate topic pools — not on using real users.

## Package Structure

The package exposes its sub-modules through the standard Python package init pattern (empty `__init__.py`). The actual capabilities are distributed across:

| Module | Responsibility |
|---|---|
| `agents.py` | Generate 1,000 agent profiles with OCEAN personalities |
| `conditions.py` | Implement the 5 experimental memory conditions |
| `config.py` | Define experiment parameters (scale, conditions, thresholds) |
| `analysis.py` | Statistical analysis and report generation |
| `metrics.py` | Metric computation (Cohen's d, Mann-Whitney U, CI) |
| `dspy_training/` | Training data generation for DSPy module optimization |

## Experimental Design Summary

**Independent variable**: Memory condition (5 levels, from no memory to full Soul Protocol stack)

**Dependent variables**: Recall precision, recall hit rate, emotion accuracy, bond strength, personality drift, memory compression

**Covariates**: Agent OCEAN profile, use case domain, session number

**Controls**: Fixed random seed (42), identical interaction sequences per condition, same agent pool across conditions

## Reproducibility Guarantee

The package design prioritizes exact reproducibility:
- `random_seed = 42` is the default in `ExperimentConfig`
- `generate_agents(seed=42)` produces the identical 1,000 agents every run
- `generate_users(seed=42)` produces identical user profiles
- All OCEAN sampling uses `random.Random(seed)` (not the global random state) to prevent contamination from other library code that calls `random`

## Known Gaps

- The `__init__.py` is empty — no `__all__` is defined, so `from research import *` imports nothing useful. Downstream code must import from sub-modules directly.
- No versioning of experiment results is shown — if the Soul Protocol runtime changes between runs, results may not be comparable without re-running the full experiment.