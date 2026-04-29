---
{
  "title": "D4 Bond and Relationship Evaluator",
  "summary": "Validates the mathematical properties of the soul's bond growth system: logarithmic curve shape, emotional valence acceleration, milestone accuracy at N=50/100/200, and tier progression ordering. Contributes 15% of the Soul Health Score.",
  "concepts": [
    "bond system",
    "logarithmic growth",
    "Pearson correlation",
    "valence acceleration",
    "bond tiers",
    "milestone accuracy",
    "strengthen",
    "bond_strength",
    "interaction_count",
    "TIER_LABELS"
  ],
  "categories": [
    "evaluation",
    "relationship",
    "soul-health-score"
  ],
  "source_docs": [
    "d82fb9a4c5f72ffb"
  ],
  "backlinks": null,
  "word_count": 409,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The bond system models the deepening relationship between a soul and its user. D4 verifies that bonding is not arbitrary—it follows a predictable logarithmic decay curve, responds faster to positive emotion, reaches milestones accurately, and progresses through tiers in the correct order.

## Four Scenarios

### BD-1: Growth Curve Validation
Runs 50–200 neutral interactions and records the bond strength trajectory. The theoretical model is:

```
strength[t+1] = strength[t] + amount * (100 - strength[t]) / 100
```

This produces logarithmic growth that decelerates as bond approaches 100. The evaluator fits the observed trajectory against simulated theoretical curves (testing `amount` values from 0.1 to 3.0) and picks the highest Pearson r. A score of ≥ 0.95 indicates the implementation follows the model.

### BD-2: Valence Acceleration
Compares two souls after 30–75 interactions:
- **Soul A**: receives high-positive messages (crafted with POSITIVE_WORDS keywords)
- **Soul B**: receives neutral filler messages (zero-valence, no sentiment keywords)

At 75 turns, theoretical analysis predicts ~1.16x ratio. The threshold for passing is ≥ 1.15x. The comment explains why 75 turns was chosen: at very high turn counts both curves converge toward 100, compressing the ratio below detectable levels.

### BD-3: Milestone Accuracy
Runs the pure `Bond` model (no soul pipeline) with `strengthen(1.0)` for 200 steps and checks that actual values at N=50, N=100, N=200 match formula predictions within ±2 points. This is a pure math test—it catches rounding errors or formula drift in the Bond class implementation.

### BD-4: Tier Progression
Verifies that bond tiers (`Stranger → Acquaintance → Familiar → Friend → Bonded`) are never skipped. A tier jump of more than one step indicates either a bug in the tier boundary conditions or a bond strength discontinuity.

This scenario is skipped in `quick=True` mode (assumed pass) because it requires 100–300 interactions.

## Score Formula

```
score = (growth_curve_r * 40)
      + (accel_pass * 20)
      + (milestone_pass * 25)
      + (tier_pass * 15)
```

## Key Implementation Detail

The `_simulate_bond` helper replicates the bond formula externally. It exists because the evaluator cannot rely on the Bond class's internal formula remaining unchanged between versions. Having an independent simulation lets the test catch formula regressions.

## Known Gaps

- `pearson_r` is implemented inline rather than imported from a shared utility—the same function appears in `d5_self_model.py`, creating duplication.
- BD-2 result is sensitive to exact message wording. If the heuristic sentiment detector's POSITIVE_WORDS list changes, the test messages may no longer produce the expected valence difference.