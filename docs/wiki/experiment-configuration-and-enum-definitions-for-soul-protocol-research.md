---
{
  "title": "Experiment Configuration and Enum Definitions for Soul Protocol Research",
  "summary": "Defines the `ExperimentConfig` dataclass and supporting enums (`MemoryCondition`, `UseCase`) that control every parameter of the Soul Protocol validation study. All experiment parameters live in one place to guarantee reproducibility — any change to scale, thresholds, or conditions is a single-file edit.",
  "concepts": [
    "ExperimentConfig",
    "MemoryCondition",
    "UseCase",
    "StrEnum",
    "dataclass",
    "random seed",
    "reproducibility",
    "significance threshold",
    "activation decay rate",
    "OCEAN distribution",
    "total_runs",
    "total_interactions",
    "experiment parameters",
    "ablation configuration"
  ],
  "categories": [
    "research",
    "configuration",
    "experimental-design",
    "soul-protocol"
  ],
  "source_docs": [
    "a4f5d9c6edf9bb90"
  ],
  "backlinks": null,
  "word_count": 525,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`config.py` is the single source of truth for the research experiment's parameters. It implements a common scientific software pattern: separate configuration from execution. Any researcher who wants to replicate or extend the study only needs to modify this file.

## MemoryCondition Enum

```python
class MemoryCondition(StrEnum):
    NONE = "none"           # Stateless baseline
    RAG_ONLY = "rag_only"   # Pure vector similarity
    RAG_SIGNIFICANCE = "rag_sig"  # RAG + LIDA gating
    FULL_NO_EMOTION = "full_no_emo"  # Full minus somatic
    FULL_SOUL = "full_soul" # Complete stack
```

Using `StrEnum` (Python 3.11+) means condition values serialize as human-readable strings in CSV output and logs. A plain `Enum` would serialize as `MemoryCondition.NONE`, which requires extra handling in the analysis layer. String enum values also make result CSVs directly readable without decoding.

## UseCase Enum

Four evaluation domains chosen to span the practical AI companion use cases:

| Enum | Domain | Why Included |
|---|---|---|
| `CUSTOMER_SUPPORT` | Support tickets | High recall precision demands |
| `CODING_ASSISTANT` | Programming help | Technical, factual, low-emotion |
| `PERSONAL_COMPANION` | Daily conversation | High emotional continuity demand |
| `KNOWLEDGE_WORKER` | Research/analysis | Mixed emotional and factual |

The four domains are deliberately chosen to produce different challenge profiles. If Soul Protocol only outperformed on `PERSONAL_COMPANION` but not on `CODING_ASSISTANT`, the result would be much weaker than universal improvement.

## ExperimentConfig Dataclass

```python
@dataclass
class ExperimentConfig:
    num_agents: int = 1000
    interactions_per_agent: int = 50
    num_sessions: int = 5
    interactions_per_session: int = 10
    conditions: list[MemoryCondition] = field(default_factory=lambda: list(MemoryCondition))
    use_cases: list[UseCase] = field(default_factory=lambda: list(UseCase))
    random_seed: int = 42
    significance_threshold: float = 0.3
    activation_decay_rate: float = 0.95
    ocean_mean: float = 0.5
    ocean_std: float = 0.15
    output_dir: str = "research/results"
```

Key design choices:
- `conditions` defaults to all `MemoryCondition` values — a full experiment run includes all five conditions by default
- `random_seed = 42` is the canonical reproducibility anchor; any deviation must be documented
- `significance_threshold = 0.3` and `activation_decay_rate = 0.95` are the Soul Protocol pipeline parameters used only by the FULL conditions — they are here rather than in conditions.py so that a single config change applies to both Full conditions simultaneously

## Computed Properties

```python
@property
def total_runs(self) -> int:
    return self.num_agents * len(self.conditions) * len(self.use_cases)

@property
def total_interactions(self) -> int:
    return self.total_runs * self.interactions_per_agent
```

With default settings: `1000 agents × 5 conditions × 4 use_cases = 20,000 total runs`, and `20,000 × 50 = 1,000,000 total simulated interactions`. These properties allow the runner to display progress estimates and estimate runtime before committing to a full run.

## Why Dataclass Over Dict

Using a typed dataclass rather than a config dict provides:
- IDE autocomplete and type checking for all parameters
- `field(default_factory=...)` for mutable defaults without the classic `list` default pitfall
- Easy override at runtime: `ExperimentConfig(num_agents=100)` for quick smoke tests

## Known Gaps

- No validation logic (e.g., `interactions_per_session * num_sessions == interactions_per_agent`). Mismatched values would produce misleading results without any error.
- The `activation_decay_rate` parameter is used by the FULL conditions but its exact effect on the runtime is not documented here — readers need to cross-reference `conditions.py` and the Soul Protocol runtime internals to understand its impact.