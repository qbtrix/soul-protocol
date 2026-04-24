---
{
  "title": "Research Metrics Schema — Six-Dimensional Agent Quality Measurement",
  "summary": "Defines the full metric collection schema for Soul Protocol's research framework across six orthogonal dimensions: retrieval quality, emotional tracking, personality stability, memory efficiency, bond formation, and skill acquisition. All metric classes are dataclasses that aggregate per-interaction observations into summary statistics for factorial analysis.",
  "concepts": [
    "RecallMetrics",
    "EmotionalMetrics",
    "PersonalityMetrics",
    "MemoryEfficiencyMetrics",
    "BondMetrics",
    "SkillMetrics",
    "AgentRunMetrics",
    "precision",
    "recall",
    "hit rate",
    "retrieval latency",
    "trait drift",
    "compression ratio",
    "bond trajectory",
    "factorial analysis"
  ],
  "categories": [
    "research",
    "metrics",
    "evaluation",
    "soul-protocol"
  ],
  "source_docs": [
    "4a81b8c0c6da3df5"
  ],
  "backlinks": null,
  "word_count": 430,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`metrics.py` provides the measurement vocabulary for Soul Protocol's research. Without a principled, multi-dimensional metric schema, evaluation risks optimizing only for recall precision while ignoring whether the soul's emotional and personality layers actually work. The six dimensions map directly to the six components of the soul stack.

## Metric Dimensions

### RecallMetrics
Measures retrieval quality at four granularities:
- `precision_scores` — of returned memories, how many were relevant?
- `recall_scores` — of planted facts, how many were retrieved?
- `hit_at_k` — bool list: was the exact fact in the top-k results?
- `retrieval_latency` — turns between planting and first successful retrieval

The distinction between precision and recall is important: a system can achieve high recall by returning many memories (low precision), or high precision by returning few highly relevant ones (potentially low recall).

### EmotionalMetrics
- `emotion_accuracy` — did the somatic marker match the expected emotion?
- `valence_trajectory` — list of valence values over time
- `bond_correlation` — does bond strength correlate with positive valence?

### PersonalityMetrics
- `trait_drift` — per-OCEAN-dimension drift list; low drift means stable personality
- `style_consistency` — output characteristic variance

`mean_drift` averages across all five OCEAN traits to give a single personality stability score.

### MemoryEfficiencyMetrics
- `memory_growth_rate` — `(interaction_count, memory_count)` tuples
- `memory_utilization` — fraction of stored memories retrieved at least once
- `significance_scores` — distribution of significance values assigned by the gating layer

`compression_ratio` computes interactions-per-stored-memory. Higher compression means more selective storage, which is the design goal of the significance gate.

### BondMetrics
- `strength_trajectory` — bond strength sampled over time
- `interaction_count_at_milestones` — maps milestone interaction counts to bond values

`growth_rate` computes the slope of bond strength over the trajectory.

### SkillMetrics
Tracks the evolution system: skills discovered, total XP earned, max level reached, and skill names.

## AgentRunMetrics: The Composite Record

```python
@dataclass
class AgentRunMetrics:
    agent_id: int
    condition: str
    use_case: str
    recall: RecallMetrics
    emotional: EmotionalMetrics
    personality: PersonalityMetrics
    efficiency: MemoryEfficiencyMetrics
    bond: BondMetrics
    skills: SkillMetrics
```

`to_row()` flattens all nested metrics to a single dict for pandas-compatible tabular analysis. This allows full factorial analysis (agent × condition × use_case) without deeply nested JSON wrangling.

## Statistical Utilities

`cohens_d(group1, group2)` and `_norm_cdf(x)` are duplicated here from `long_horizon/analyze.py`. The duplication allows `metrics.py` to stand alone without coupling to the long-horizon subpackage.

## Known Gaps

- **Most metric fields are not populated** by the current runners. `RecallMetrics.retrieval_latency`, `EmotionalMetrics.bond_correlation`, and `PersonalityMetrics.style_consistency` are defined but never written by the long-horizon or quality runners. The schema is ahead of the implementation.
- `SkillMetrics` assumes the evolution system is active, but skills are not tracked in any current benchmark scenario.