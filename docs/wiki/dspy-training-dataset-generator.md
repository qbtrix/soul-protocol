---
{
  "title": "DSPy Training Dataset Generator",
  "summary": "Generates labeled training data for DSPy-optimized memory significance and recall query expansion. Produces two dataset types—significance classification and query expansion—split into train/val sets for fine-tuning the soul's memory filtering models.",
  "concepts": [
    "DSPy",
    "training data",
    "should_store",
    "significance labeling",
    "query expansion",
    "BM25",
    "recall",
    "memory filtering",
    "scenario generation",
    "train/val split",
    "importance_hint",
    "planted facts"
  ],
  "categories": [
    "research",
    "machine-learning",
    "memory-system",
    "dspy-optimization"
  ],
  "source_docs": [
    "1c19d360e3e2fbaa"
  ],
  "backlinks": null,
  "word_count": 441,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

This module creates the labeled data that powers DSPy optimization of two critical soul-protocol behaviors: deciding which interactions are worth storing in memory (`should_store`) and generating better recall queries through expansion.

Without good training data, DSPy cannot learn the threshold between signal and noise. A soul that stores everything becomes cluttered; one that stores too little forgets what matters.

## Significance Dataset

The `generate_significance_dataset` function simulates 10 users across four use cases (`support`, `coding`, `companion`, `knowledge`). For each user/use-case combination it generates conversation scenarios via `generate_scenarios`, then labels every turn:

```python
should_store = turn.contains_fact or turn.importance_hint >= 0.8
```

The labeling logic evolved deliberately. The original implementation used a `near_fact` window (within 2 turns of a planted fact) and an importance threshold of `0.7`. Both were tightened:
- **Window removed entirely**: scenarios are dense with facts; adjacency produced too many false positives as training examples.
- **Threshold raised 0.7 → 0.8**: forces the model to learn a stricter boundary, reducing memory bloat in production.
- **`expected_emotion` removed**: too broad a signal—nearly every turn in companion scenarios would have qualified.

Each labeled example carries rich metadata (`scenario_id`, `turn_index`, `contains_fact`, `importance_hint`, `use_case`) so downstream analysis can audit why labels were assigned.

## Recall Dataset

The `generate_recall_dataset` function harvests `recall_queries` already embedded in each scenario and generates 3–5 rephrasings via `_expand_query_heuristic`:

1. **Keyword extraction** from the expected fact (stop words removed)
2. **The fact itself** as a query variation (exact-match coverage)
3. **"Tell me about X"** variation (natural language rephrase)
4. **Keyword-only short form** stripped of common interrogatives

This matters because BM25 recall depends on token overlap. If a user asks "what's my cat's name?" but the stored fact says "adopted a cat named Mochi," overlap is low. Expanded queries bridge the vocabulary gap during training.

## Train/Val Splitting

`split_dataset` performs a reproducible 80/20 split using a seeded `random.Random` instance. Seeding is essential: the same seed must produce the same split so evaluation metrics are comparable across runs.

## Entry Point

The `main` function wires everything together:

```python
python -m research.dspy_training.generate_dataset
python -m research.dspy_training.generate_dataset --output-dir custom/path
```

It prints positive rate for the significance dataset (useful for catching class imbalance) and writes four JSON files: `significance_train.json`, `significance_val.json`, `recall_train.json`, `recall_val.json`.

The `PROJECT_ROOT` sys.path insertion at module load is a defensive pattern against relative import failures when running as a top-level script versus a module (`python -m`).

## Known Gaps

- Query expansion is purely heuristic (string manipulation). DSPy fine-tuning will eventually replace this with a learned expansion model.
- `personality_summary` field in recall examples is always an empty string—placeholder for a future feature that would include the user's OCEAN profile summary as context.