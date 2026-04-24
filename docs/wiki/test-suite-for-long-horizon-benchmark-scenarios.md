---
{
  "title": "Test Suite for Long-Horizon Benchmark Scenarios",
  "summary": "Validates the three benchmark scenario generators (Life Updates, Emotional Rollercoaster, Adversarial Burial) that produce 100+ turn conversation scripts with planted facts, test points, and recall challenges. Tests verify determinism, scenario structure, seeded variation, and the TestPoint dataclass.",
  "concepts": [
    "LongHorizonScenario",
    "Life Updates",
    "Emotional Rollercoaster",
    "Adversarial Burial",
    "planted facts",
    "test points",
    "recall challenge",
    "determinism",
    "seeded generation",
    "TestPoint",
    "generate_all_scenarios",
    "turn count"
  ],
  "categories": [
    "testing",
    "long-horizon benchmark",
    "scenarios",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "f11a36f4c0c1cfcb"
  ],
  "backlinks": null,
  "word_count": 483,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_scenarios.py` validates the scenario generators that power the long-horizon benchmark. Each scenario produces a scripted multi-turn conversation containing deliberately planted facts and test points — the raw material the runner uses to measure how well different soul configurations retain and recall information over time.

## Why Three Scenarios?

The three scenarios test different memory stress patterns:

| Scenario | Stress Pattern |
|---|---|
| **Life Updates** | Organic information accumulation over casual conversation |
| **Emotional Rollercoaster** | High-arousal content that may bias storage toward emotional memories |
| **Adversarial Burial** | Facts planted early then buried under unrelated noise before recall tests |

Together they reveal whether a memory system handles recency bias, emotional salience weighting, and interference correctly.

## Structural Invariants

All scenarios are tested for:

- **Turn count ≥ 100** — ensures the scenario is long enough to challenge memory, not just a trivial short exchange
- **Has test points** — at least one recall challenge must exist
- **Has planted facts** — facts must be injected at specific turn indices within valid range
- **Determinism** — calling the generator twice with the same seed produces identical output; this prevents flaky benchmark comparisons
- **Seed variation** — different seeds produce different turn content (checks against an accidentally hard-coded generator)

## Scenario-Specific Tests

### Life Updates (TestLifeUpdatesScenario)
- `test_turns_are_tuples` — each turn is a `(role, text)` tuple, not a raw string
- `test_buried_callback_test_points` — some test points appear well after the fact was planted, simulating long-delay recall

### Emotional Rollercoaster (TestEmotionalRollercoasterScenario)
- `test_planted_facts_cover_emotional_range` — planted facts span positive and negative emotional valence, ensuring the scenario exercises the full emotional spectrum

### Adversarial Burial (TestAdversarialBurialScenario)
```python
def test_five_planted_facts():     # exactly 5 facts planted
def test_facts_planted_early():    # all facts in first 20% of turns
def test_recall_tests_are_late():  # recall happens after 80% of turns
def test_sufficient_noise_between_facts_and_tests()  # meaningful gap exists
def test_recall_tests_cover_all_facts()  # every planted fact has a recall test
```
The adversarial scenario's structure is the most precisely specified because its entire value comes from the timing relationship between planting and testing. These tests enforce that the scenario generator cannot accidentally produce a trivially easy version (e.g., recall test one turn after planting).

## generate_all_scenarios Helper

`TestGenerateAllScenarios` verifies the convenience function that returns all three scenarios:
- Returns exactly three scenarios
- All have 100+ turns
- All have unique scenario IDs (prevents ID collisions in result aggregation)
- All have test points

## TestPoint Dataclass

`TestTestPointDataclass` verifies the `TestPoint` dataclass itself — creation with required fields, and that the optional `description` field defaults gracefully. This is a low-level contract test ensuring the data structure used throughout the benchmark pipeline remains stable.

## Known Gaps

No TODOs flagged. The scenarios use seeded random generation, but there are no tests verifying that specific fact content (the actual text of planted facts) remains stable across library version upgrades to the underlying random module.