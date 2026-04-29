---
{
  "title": "Heuristic Rubric Evaluator and Evolution Trigger Detection",
  "summary": "`evaluation.py` provides a lightweight, LLM-free rubric evaluation system that scores soul interactions across dimensions like completeness, relevance, specificity, and empathy. Score history feeds the evolution system — when a soul shows a sustained high-performance streak in a domain, the evaluator surfaces a trigger that prompts a DNA mutation proposal.",
  "concepts": [
    "Evaluator",
    "heuristic evaluation",
    "rubric",
    "RubricResult",
    "completeness",
    "relevance",
    "specificity",
    "empathy",
    "evolution triggers",
    "LearningEvent",
    "domain scoring",
    "high-performance streak"
  ],
  "categories": [
    "evaluation",
    "evolution",
    "learning",
    "heuristics"
  ],
  "source_docs": [
    "835b54372e9d4949"
  ],
  "backlinks": null,
  "word_count": 453,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Before a soul can evolve, it needs feedback on how well it's performing. `evaluation.py` implements that feedback loop without requiring an LLM call for each interaction — a deliberate efficiency choice for the MVP. Heuristic scoring runs locally, synchronously, and is cheap enough to run on every interaction.

The evaluation layer sits between raw interaction data and the evolution system: it transforms text inputs/outputs into numeric scores, tracks history, and detects patterns worth acting on.

## Scoring Architecture

Five heuristic functions produce scores in [0.0, 1.0]:

| Function | What it measures | Key calibration |
|---|---|---|
| `_score_completeness` | Response length relative to 20-word threshold | 20-word threshold (not 40) — a solid 2-sentence reply scores ~1.0 |
| `_score_relevance` | Token overlap between user input and agent output | `user_tokens` as denominator — verbose agent responses aren't penalized |
| `_score_helpfulness` | Average of completeness + relevance with sentiment boost | Positive-sentiment responses get a 1.2× multiplier |
| `_score_specificity` | Proportion of words that are specific/technical | 6+ char words count as specific — conversational technical answers score fairly |
| `_score_empathy` | Presence of empathy marker words | Count of ~15 markers, capped at 3 for 1.0 |

These are intentionally coarse. The comments explicitly call out `originality` as "unknowable heuristically" and hardcode it to 0.5. The goal is a bootstrapping system that produces useful signal — not perfection.

## Rubric and Domain System

Each `Rubric` is a named collection of weighted criteria. Six default rubrics correspond to the soul's seed domains:

```python
DEFAULT_RUBRICS = {
    "technical_helper": ...,  # completeness + relevance + helpfulness + specificity
    "creative_writer": ...,   # + originality
    "emotional_companion": ..., # + empathy
    ...
}
```

The `Evaluator.evaluate()` method auto-selects the rubric for the current domain, falling back to `technical_helper` for unknown domains.

## Evolution Trigger Detection

```python
def check_evolution_triggers(self) -> list[dict]:
    # streak >= 5 consecutive scores >= 0.55 AND avg >= 0.55
    → "high_performance_streak" trigger
```

The thresholds (0.55 streak, 0.55 average) were calibrated after recalibrating the scoring functions — a solid technical conversation now naturally scores 0.65-0.80, making these thresholds achievable without inflation.

## Learning Events

`create_learning_event()` converts a `RubricResult` into a `LearningEvent` for the memory system. Scores ≥ 0.8 produce `"Success pattern"` events; scores ≤ 0.3 produce `"Failure pattern"` events. Mid-range scores return `None` — only outliers are worth recording.

## Known Gaps

- `originality` is always 0.5 — truly unknowable heuristically. An LLM evaluator would be needed for this.
- Stop words list is intentionally self-contained (not shared with `self_model.py`) to avoid coupling, but this means two copies of similar data.
- The 100-result history cap is hardcoded. Long-running souls with high interaction volume could benefit from configurable retention.