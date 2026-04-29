---
{
  "title": "SoulOptimizer: MIPROv2 Training Harness for Cognitive Modules",
  "summary": "`SoulOptimizer` is an offline training harness that uses DSPy's MIPROv2 optimizer to tune `SignificanceGate` and `QueryExpander` against labeled interaction data derived from ablation scenarios or production logs. Optimized module weights are serialized to disk and loaded by `DSPyCognitiveProcessor` at runtime.",
  "concepts": [
    "SoulOptimizer",
    "MIPROv2",
    "DSPy",
    "SignificanceGate",
    "QueryExpander",
    "training data",
    "ablation scenarios",
    "module optimization",
    "offline training",
    "DSPyCognitiveProcessor"
  ],
  "categories": [
    "cognitive engine",
    "DSPy",
    "optimization",
    "research"
  ],
  "source_docs": [
    "a636ffa8c9f98f40"
  ],
  "backlinks": null,
  "word_count": 415,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Hard-coded LLM prompts plateau at a fixed quality ceiling. `SoulOptimizer` breaks through that ceiling by treating soul-protocol's cognitive modules as learnable programs and running systematic prompt optimization with DSPy's MIPROv2. The result is a set of module files encoding the best discovered prompts and demonstrations for a specific LLM, which `DSPyCognitiveProcessor` loads at startup.

## Optimization Workflow

```python
optimizer = SoulOptimizer(lm_model="anthropic/claude-haiku-4-5-20251001")
trainset = optimizer.create_training_data()
train, val = trainset[:40], trainset[40:]

optimized_gate = optimizer.optimize_significance_gate(train, val)
optimizer.save_optimized("optimized_modules/")
```

This is an offline process — run once, ship the results, load in production. Re-optimization is triggered manually when accumulated production logs suggest the current prompts are underperforming.

## MIPROv2 Configuration

MIPROv2 (Multi-prompt Instruction PRoposal Optimizer v2) is DSPy's most capable optimizer. `SoulOptimizer` configures it with:

- `num_candidates`: number of prompt candidates to evaluate per trial
- `max_trials`: total optimization budget (defaults to 20 per module)
- The module's metric function as the optimization objective

MIPROv2 explores the space of prompt instructions and few-shot demonstrations, evaluating each candidate on the validation set and keeping the best performer.

## Metric Functions

**Significance metric** (`_significance_metric`): Rewards correct `should_store` binary prediction with full score, with partial credit for reasonable confidence even when the label is wrong — this acknowledges the inherent ambiguity of borderline interactions where reasonable people would disagree.

**Recall metric** (`_recall_metric`): Measures whether any of the expanded queries would have retrieved the relevant interaction from memory. Scoring is recall-oriented: credit for finding the right document at all, more credit for finding it in fewer queries.

## Training Data Generation

`create_training_data()` generates labeled examples from soul-protocol's ablation scenario library using these heuristics:

- Interactions containing planted facts → `should_store=True`
- Small talk and filler turns → `should_store=False`
- Turns within two positions of a planted fact → `should_store=True` (contextual relevance)
- High importance-hint or emotional content → `should_store=True`

Custom scenarios can be substituted via the `scenarios_path` JSON parameter.

## Save / Load Protocol

```python
optimizer.save_optimized("optimized_modules/")
# In production:
processor = DSPyCognitiveProcessor(optimized_path="optimized_modules/")
```

Each module serializes to a DSPy JSON file. The load path is shared with `DSPyCognitiveProcessor`, creating a clean optimize-once, deploy-many workflow that does not require DSPy to be installed in production environments.

## Known Gaps

- `FactExtractor` optimization is not yet implemented — only `SignificanceGate` and `QueryExpander` have optimization methods.
- No automated re-optimization trigger. Operators must manually decide when to re-run optimization.
- The research scenario import (`from research.agents import UserProfile`) silently returns empty training data if the research subpackage is not installed, without emitting a warning.