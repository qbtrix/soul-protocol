---
{
  "title": "Test Suite: OCEAN Personality-Modulated Memory Retrieval",
  "summary": "Comprehensive tests for the personality modulation layer that adjusts memory recall scores based on OCEAN (Big Five) personality traits, covering per-trait signal functions, the composite boost calculation, and end-to-end recall ranking changes.",
  "concepts": [
    "OCEAN personality",
    "Big Five",
    "compute_personality_boost",
    "trait_delta",
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
    "SomaticMarker",
    "compute_activation",
    "memory recall ranking"
  ],
  "categories": [
    "personality",
    "memory",
    "testing",
    "recall",
    "test"
  ],
  "source_docs": [
    "7e3079f7806fd428"
  ],
  "backlinks": null,
  "word_count": 503,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: OCEAN Personality-Modulated Memory Retrieval

`test_personality_modulation.py` validates `compute_personality_boost()` and its integration with `compute_activation()` and `RecallEngine`. This test suite (added in v0.3.3) ensures that a soul's OCEAN personality traits predictably tilt which memories surface during recall — a high-openness soul surfaces more semantic/conceptual memories, while a high-extraversion soul prioritizes episodic social memories.

### Why Personality Modulation Matters

Without modulation, all souls with identical memories would recall the same results for the same query. Personality modulation makes recall subjective — the same question yields different memory priorities depending on who is asking. This is foundational to soul individuation.

### Trait Delta: The Baseline Calculation

```python
def _trait_delta(trait_value: float) -> float:
    # Returns 0 at 0.5 (neutral), positive above, negative below
```

`_trait_delta` maps a trait's 0.0–1.0 value to a signed delta centered at 0.5. A neutral personality (all traits = 0.5) produces zero delta for every trait, resulting in zero boost — confirmed by `test_boost_neutral_personality_returns_zero`. This ensures personality modulation is a pure additive layer that doesn't disturb existing behavior for souls without a configured personality.

### Per-Trait Signal Functions

Each of the five OCEAN traits has a private `_<trait>_signal()` function that maps a `MemoryEntry` to a float signal in [-1, 1]:

| Trait | Boosts | Penalizes |
|-------|--------|-----------|
| Openness | Semantic memories, procedural memories | — |
| Conscientiousness | Procedural memories, high-importance entries | Low-importance non-procedural |
| Extraversion | Episodic memories, entries with named entities | — |
| Agreeableness | Positive-valence memories | Negative-valence memories |
| Neuroticism | High-arousal entries, strong-negative-valence entries | — |

Tests for each trait verify:
- The signal is positive for the matching memory type
- The signal respects valence/arousal fields from `SomaticMarker`
- Capping behavior (e.g., extraversion signal caps at 1.0 even with many entities)

### Composite Boost: compute_personality_boost

```python
boost = compute_personality_boost(entry, personality)
# Sums all five trait contributions; clamped to reasonable bounds
```

Key test scenarios:
- `test_boost_none_personality_returns_zero` — `personality=None` always returns 0 (backwards compat)
- `test_boost_combined_traits` — multiple high traits stack additively
- `test_boost_bounded_range` — extreme trait values (0.0 / 1.0) don't produce unbounded boosts

### Integration with compute_activation

`test_activation_personality_modulates_score` verifies that `compute_activation()` with a high-openness personality returns a different activation score for a semantic memory than without personality. The test compares scores to ensure the boost is actually applied at the activation layer.

### Integration with RecallEngine

End-to-end tests seed identical memories, configure two `RecallEngine` instances (one with high-openness personality, one neutral), run the same recall query, and verify that the ranking order differs. This ensures the personality boost flows correctly from `compute_personality_boost` → `compute_activation` → recall scoring → final sort order.

### Backwards Compatibility

Several tests explicitly verify that `personality=None` produces results identical to the pre-modulation baseline, ensuring no regressions for souls that don't configure personality traits.

### Known Gaps

Signal functions operate on `MemoryEntry.type` and `SomaticMarker` fields. Entries without somatic markers (no sentiment analysis run yet) produce zero agreeableness/neuroticism signals. There is no fallback signal for entries with missing somatic data beyond the zero default.
