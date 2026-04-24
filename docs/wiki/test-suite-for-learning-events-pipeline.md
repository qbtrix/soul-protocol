---
{
  "title": "Test Suite for Learning Events Pipeline",
  "summary": "Tests for the full learning events pipeline — from `RubricResult` score thresholding to `LearningEvent` creation, skill XP grant, and the `Soul.learn()` convenience method. Covers model validation, score boundary conditions, XP scaling, and spec module exportability.",
  "concepts": [
    "LearningEvent",
    "Evaluator",
    "create_learning_event",
    "SkillRegistry",
    "grant_xp_from_learning",
    "Soul.learn",
    "confidence",
    "XP",
    "score thresholds",
    "HIGH_SCORE_THRESHOLD",
    "LOW_SCORE_THRESHOLD",
    "reinforce",
    "weaken",
    "domain",
    "skill progression"
  ],
  "categories": [
    "testing",
    "learning",
    "skills",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "10630df0702e5c41"
  ],
  "backlinks": null,
  "word_count": 419,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul Protocol's learning loop converts evaluation results into structured events that drive skill progression. `test_learning_events.py` validates every stage of this pipeline, ensuring that high scores produce reinforcing events, low scores produce corrective events, and medium scores are silently discarded.

## LearningEvent Model (`TestLearningEventModel`)

`LearningEvent` is a Pydantic model that tracks a soul's acquired skill or behaviour pattern:

- `confidence` is validated to `[0.0, 1.0]` — out-of-range values are rejected at model construction.
- `apply()` increments an application count, enabling frequency tracking.
- `reinforce()` increases confidence, capped at `1.0`.
- `weaken()` decreases confidence, floored at `0.0`.
- Each event gets a unique auto-generated ID.
- `created_at` is set automatically.
- Serialisation roundtrip preserves all fields.

## Score Thresholds (`TestCreateLearningEvent`)

`Evaluator.create_learning_event()` maps a `RubricResult` score to a `LearningEvent` or `None`:

| Score | Outcome |
|---|---|
| ≥ `HIGH_SCORE_THRESHOLD` | `LearningEvent` (success) |
| ≤ `LOW_SCORE_THRESHOLD` | `LearningEvent` (failure) |
| Between thresholds | `None` — no event |

Boundary cases (`test_exactly_high_threshold`, `test_exactly_low_threshold`, `test_just_above_low_threshold`, `test_just_below_high_threshold`) pin the threshold behaviour, preventing off-by-epsilon regressions in floating-point comparisons.

Confidence scales with score: a perfect score produces maximum confidence; a zero score produces minimum confidence.

## XP Grant (`TestGrantXpFromLearning`)

`SkillRegistry.grant_xp_from_learning()` translates a `LearningEvent` into XP for a named skill:

- If the skill exists, it receives XP directly.
- If the skill does not exist, it is auto-created (`test_auto_creates_skill`).
- Falls back to domain name if no explicit `skill_id` is provided.
- XP scales with both evaluation score and confidence: `xp ∝ score × confidence`.
- Minimum 1 XP is always granted, preventing zero-XP events from having no effect.
- `None` evaluation score defaults gracefully rather than crashing.
- A level-up returns `True`, enabling callers to surface milestone notifications.

## Soul.learn() Integration (`TestSoulLearn`)

`Soul.learn()` is a convenience wrapper that calls the evaluator and skill registry in sequence:

```python
async def test_learn_high_score_creates_event(soul):
    ...
async def test_learn_stores_in_learning_events(soul):
    ...
async def test_learn_grants_skill_xp(soul):
    ...
```

`test_learning_events_property_returns_copy` verifies that the property returns a copy rather than the live list, preventing accidental external mutation of the soul's internal state.

`test_learn_without_domain` confirms that omitting a domain falls back to the soul's self-model domain.

## Spec Exportability (`TestSpecExport`)

`test_learning_event_importable_from_spec` and `test_learning_event_in_spec_all` verify that `LearningEvent` is accessible from `soul_protocol.spec.learning` and included in the module's `__all__`. This ensures the public API surface is stable.

## Known Gaps

- No tests for concurrent `learn()` calls on the same soul (thread-safety of the XP accumulator).
- The domain-defaulting behaviour in `test_learn_without_domain` is not fully documented — the exact fallback chain is implied but not specified.