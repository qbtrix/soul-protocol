---
{
  "title": "DSPy Optimization Pipeline: MIPROv2-Based Significance Gate and Query Expansion Tuning",
  "summary": "This pipeline runs a four-phase experiment: baseline heuristic ablation, DSPy MIPROv2 optimization of the significance gate and query expander, post-optimization ablation with the trained modules active, and saved reports comparing before/after metrics. It exists to replace hand-tuned heuristics with learned prompts that generalize across diverse interaction types.",
  "concepts": [
    "DSPy",
    "MIPROv2",
    "significance gate",
    "query expansion",
    "training data",
    "optimization",
    "LongHorizonRunner",
    "planted facts",
    "heuristic pipeline",
    "recall precision",
    "ablation comparison"
  ],
  "categories": [
    "research",
    "dspy-optimization",
    "machine-learning",
    "soul-protocol"
  ],
  "source_docs": [
    "5660c33fb46212f1"
  ],
  "backlinks": null,
  "word_count": 378,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Soul Protocol's memory pipeline contains two LLM-backed decision points: the **significance gate** (should this interaction be stored?) and the **query expander** (how should a recall query be broadened to find related memories?). These are initially implemented as hand-crafted prompts. DSPy's MIPROv2 optimizer can automatically search for better prompt wording by optimizing against labeled training data — potentially outperforming human-written prompts without manual iteration.

## Four-Phase Pipeline

```
Phase 1: baseline heuristic ablation
  └── run_all(scenarios) with heuristic significance + heuristic recall
Phase 2: DSPy optimization
  └── generate_training_data() → labeled (interaction, should_store) examples
      └── MIPROv2.compile(significance_gate, trainset) → optimized module
          └── MIPROv2.compile(query_expander, trainset) → optimized module
Phase 3: post-optimization ablation
  └── run_all(scenarios) with DSPy significance + DSPy recall
Phase 4: save reports
  └── save_reports(baseline, optimized, dspy_results)
```

## Training Data Generation

```python
def generate_training_data() -> list[dict]:
    scenarios = generate_all_scenarios(seed=42)
    # Label each turn: should_store = True if near a planted fact
    # or if text contains emotional keywords
    for i, (user_input, agent_output) in enumerate(scenario.turns):
        is_fact_turn = i in fact_indices
        is_near_fact = i in near_fact_indices  # ±1-2 turns around fact
```

The labeling strategy uses proximity to planted facts (known ground truth) plus emotional keyword heuristics. Near-fact turns are labeled `should_store=True` because context around a fact often contains the priming information needed for later recall.

## Significance Fix

The update note in the source header explains the key bug this fixes: the significance gate previously used heuristics that missed important facts (low recall precision). Routing it through the DSPy-optimized module improved recall by correctly identifying fact-adjacent turns as significant.

## Report Outputs

`save_reports(baseline, optimized, dspy_results)` writes to `research/results/dspy_optimization/`:
- `baseline.json` / `optimized.json` — raw ConditionResult data
- `comparison.md` — Markdown table with delta metrics

The timestamp-free filenames mean each run overwrites the previous. This is intentional: the optimization results are only meaningful relative to the current codebase, so preserving stale results would be misleading.

## Known Gaps

- MIPROv2 optimization requires an Anthropic API key with sufficient quota; there is no fallback if optimization fails mid-run. A checkpoint that saves the optimized module after phase 2 would allow phase 3 to run separately.
- Training data labels (`is_near_fact`, emotional keywords) are heuristic proxies for true importance. Mislabeled examples could cause MIPROv2 to optimize toward the heuristic rather than genuine significance.
