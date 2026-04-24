---
{
  "title": "Long-Horizon Conversation Scenario Generators — Three Ablation Test Cases",
  "summary": "Defines the `LongHorizonScenario` and `TestPoint` data structures and generates three distinct 100-160 turn synthetic conversation scenarios designed to stress different aspects of Soul Protocol's psychology stack: long-range recall, emotional continuity under extreme valence swings, and recall precision under adversarial fact burial.",
  "concepts": [
    "LongHorizonScenario",
    "TestPoint",
    "filler turns",
    "life updates scenario",
    "emotional rollercoaster",
    "adversarial burial",
    "planted facts",
    "long-range recall",
    "somatic markers",
    "seeded random",
    "recall test",
    "conversation simulation",
    "temporal distance",
    "significance scoring"
  ],
  "categories": [
    "research",
    "ablation-study",
    "scenario-generation",
    "soul-protocol"
  ],
  "source_docs": [
    "c74b4c2906fecb0b"
  ],
  "backlinks": null,
  "word_count": 405,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Data Model

```python
@dataclass
class TestPoint:
    turn_index: int
    query: str
    expected_content: str  # substring match
    test_type: str         # "recall", "emotion", "bond"
    description: str = ""

@dataclass
class LongHorizonScenario:
    scenario_id: str
    name: str
    description: str
    turns: list[tuple[str, str]]  # (user_input, agent_output) pairs
    test_points: list[TestPoint]
    planted_facts: list[tuple[int, str]]  # (turn_index, fact)
```

The `turn_count` property returns `len(self.turns)`, enabling scenario size checks without materializing the full list.

## Filler Strategy

`_filler_turns(rng, count)` samples from three pools — `_WEATHER_CHAT`, `_SMALL_TALK`, `_GENERIC_TOPICS` — to generate mundane conversation that separates planted facts. The pools use seeded `random.Random` so scenarios are fully deterministic and reproducible.

Filler serves a dual purpose: it creates retrieval noise (testing precision) and introduces temporal distance between a planted fact and its recall test (testing long-range memory access).

## Scenario A: Life Updates Over Time (160 turns)

Simulates a user sharing major life events across phases:
- **Turns 0-19**: New job at TechCorp as a product manager
- **Turns 20-49**: Relationship struggles with partner Alex
- **Turns 50-79**: New hiking hobby
- **Turns 80-100**: Mixed conversation
- **Turns 101-120**: Callbacks to early facts buried under 80+ turns of filler
- **Turns 150-159**: Explicit recall questions

This scenario tests whether the soul's significance scoring correctly flagged early job and relationship facts as important enough to survive 100+ turns of subsequent conversation.

## Scenario B: Emotional Rollercoaster (150 turns)

Alternates between high-positive (job promotion, engaged, puppy) and high-negative (father's cancer diagnosis, layoff, breakup) events, then pivots to neutral resolution. Test points check:
- Whether negative somatic markers were tagged correctly
- Whether the soul can recall emotionally significant events after emotional reset
- Bond strength trajectory through extremes

## Scenario C: Adversarial Burial (160 turns)

Plants 5 specific facts early (turns 0-20), then surrounds each with 20-30 turns of filler on both sides before a recall test. The adversarial design maximizes the chance that a naive RAG system retrieves the filler content instead of the planted facts.

Test points are placed at turn indices far from the facts (e.g., fact at turn 5, recall at turn 155), maximizing temporal distance.

## Known Gaps

- **Emotional test points** (`test_type == "emotion"`) are defined but the current runner only handles `test_type == "recall"`. Emotional accuracy scoring requires an LLM judge and is not yet implemented in the infrastructure runner.
- Filler pools are shared across all three scenarios, so similar mundane exchanges appear in each. Scenario-specific filler banks would improve independence.