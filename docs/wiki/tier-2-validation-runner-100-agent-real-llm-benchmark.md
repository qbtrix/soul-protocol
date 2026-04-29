---
{
  "title": "Tier 2 Validation Runner: 100-Agent Real LLM Benchmark",
  "summary": "The Tier 2 runner validates Soul Protocol with real Anthropic API calls across 100 simulated agents, comparing heuristic-only cognitive processing against LLM-backed processing using `HaikuCognitiveEngine`. It collects a comprehensive set of metrics — memory, personality, recall, bond, emotional, and skill dimensions — and saves the results as JSON.",
  "concepts": [
    "Tier 2 validation",
    "HaikuCognitiveEngine",
    "100 agents",
    "AgentRunMetrics",
    "BondMetrics",
    "EmotionalMetrics",
    "MemoryEfficiencyMetrics",
    "RecallMetrics",
    "SkillMetrics",
    "heuristic vs LLM",
    "real API calls"
  ],
  "categories": [
    "research",
    "validation",
    "simulation",
    "soul-protocol"
  ],
  "source_docs": [
    "fd4750e8e7ce3b9c"
  ],
  "backlinks": null,
  "word_count": 327,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The research framework has two tiers of validation: Tier 1 runs entirely on heuristics (no API cost, fast), and Tier 2 replaces the significance gate and reflection pipeline with real LLM calls. Tier 2 exists because heuristics are approximations — they may correctly identify the *right* interactions to store while producing subtly wrong *outputs* (e.g., poor memory summaries). Only real LLM calls reveal whether the cognitive pipeline produces human-quality outputs at scale.

## Architecture

```python
async def run_agent_with_engine(
    agent_profile,
    user_profile,
    use_case: str,
    engine: HaikuCognitiveEngine | None,
    seed: int,
) -> AgentRunMetrics:
```

`engine: HaikuCognitiveEngine | None` allows the same function to serve both conditions: passing `None` runs pure heuristics (Tier 1 equivalent), passing a live engine runs LLM-backed processing. This avoids duplicating the agent simulation loop and makes the heuristic/LLM comparison exact — same code path, different engine.

## Metrics Collected

```python
from .metrics import (
    AgentRunMetrics,
    BondMetrics,
    EmotionalMetrics,
    MemoryEfficiencyMetrics,
    PersonalityMetrics,
    RecallMetrics,
    SkillMetrics,
)
```

All seven metric dimensions are collected per agent per condition. `AgentRunMetrics.to_row()` flattens these into a dict for tabular analysis. Collecting all dimensions simultaneously prevents re-running expensive simulations to answer follow-up questions.

## Scale and CLI

```
python -m research.run_tier2 [--agents 100] [--quick]
```

Default is 100 agents (vs 1000 in the full ablation). This is a calibrated choice: 100 agents with real LLM calls takes meaningful wall time and API budget, but is small enough to run in a CI job with a budget limit. `--quick` drops to 10 agents for pre-commit checks.

## Known Gaps

- There is no retry logic on individual agent runs. An API timeout midway through a 100-agent run aborts the whole batch; partial results are not saved to disk.
- The comparison between `engine=None` and `engine=HaikuCognitiveEngine()` is only valid if the heuristic and LLM paths produce results on the same scale. No normalization is applied, so a metric that heuristics score 0-1 and LLM scores 1-5 would appear to show the LLM always wins.
