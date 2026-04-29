---
{
  "title": "Quality Scenario Generator: Randomized Test Variations for Statistical Validity",
  "summary": "The scenario generator produces 10 randomized but reproducible variations of each of the four quality test types, enabling error bars and statistical significance checks rather than single-point measurements. A fixed seed (`SEED = 42`) ensures results are reproducible across runs while the random variation catches edge cases a single hardcoded scenario would miss.",
  "concepts": [
    "scenario generator",
    "SEED",
    "ResponseQualityScenario",
    "PersonalityScenario",
    "HardRecallScenario",
    "EmotionalContinuityScenario",
    "OCEAN traits",
    "statistical variation",
    "reproducibility",
    "error bars",
    "planted facts"
  ],
  "categories": [
    "research",
    "quality-evaluation",
    "scenario-generation",
    "soul-protocol"
  ],
  "source_docs": [
    "dae71de6019bb00f"
  ],
  "backlinks": null,
  "word_count": 359,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

A quality test that runs a single fixed scenario tells you whether the soul works for one specific persona, topic, and phrasing — not whether it generalizes. `scenario_generator.py` addresses this by generating `n` unique variations per test type. With 10 variations, researchers can report mean + standard deviation, apply statistical tests, and detect regressions that a single scenario would mask.

The fixed `SEED = 42` is not an arbitrary convention — it guarantees that "run 1 on Monday" and "run 2 on Thursday" use identical scenarios, making cross-run comparisons valid.

## Scenario Types

### ResponseQualityScenario
Tests whether soul context improves replies to a challenge message after conversational warm-up.

```python
@dataclass
class ResponseQualityScenario:
    user_name: str
    user_profession: str
    soul_name: str
    soul_archetype: str
    soul_ocean: dict[str, float]
    conversation_turns: list[tuple[str, str]]
    challenge_message: str
    expected_references: list[str]
    communication: dict[str, str]
    values: list[str]
    personality: str
```

`expected_references` lists concepts the soul-enriched response should mention (e.g., the user's profession), giving the judge concrete criteria rather than relying on pure LLM opinion.

### PersonalityScenario
Presents the same `shared_turns` to multiple souls with different OCEAN profiles and checks that responses differ in character.

### HardRecallScenario
Plants one specific fact in a warm-up turn, then buries it under 25-30 filler interactions before querying for it. `planted_fact_keywords` gives the judge anchors to check.

### EmotionalContinuityScenario
Drives a soul through a defined emotional arc (e.g., `"excited->devastated->recovering"`) and checks that somatic markers reflect the arc. `_ocean_distance(a, b)` computes Euclidean distance between two OCEAN trait dictionaries — a higher distance means more distinct personalities, useful for ensuring test agents are genuinely different.

## Randomization Strategy

Each generator draws from pools of names, professions, archetypes, and OCEAN values, then shuffles and slices to produce `n` unique combinations. The RNG is seeded at function entry so successive calls with the same `n` return the same scenarios.

## Known Gaps

- The filler turns in `HardRecallScenario` are drawn from a shared pool, so at `n > pool_size` some scenarios will share identical fillers. This weakens the independence assumption across variations.
- `_ocean_distance` is defined on `EmotionalContinuityScenario` as an instance method despite having no dependency on `self`. It should be a module-level helper or `@staticmethod` for clarity.
