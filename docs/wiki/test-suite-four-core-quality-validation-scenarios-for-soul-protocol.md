---
{
  "title": "Test Suite: Four Core Quality Validation Scenarios for Soul Protocol",
  "summary": "This test suite implements the four hardest quality probes for Soul Protocol — response quality uplift, personality consistency across OCEAN profiles, hard recall after 30 filler interactions, and emotional continuity via somatic markers — using paired LLM comparisons with a `ResponseJudge` to score soul-enriched versus baseline responses.",
  "concepts": [
    "test_response_quality",
    "test_personality_consistency",
    "test_hard_recall",
    "test_emotional_continuity",
    "ResponseJudge",
    "SoulResponder",
    "somatic markers",
    "OCEAN profiles",
    "planted facts",
    "filler interactions",
    "soul_score",
    "baseline_score"
  ],
  "categories": [
    "research",
    "quality-evaluation",
    "testing",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "d0f9e7ba7c48be8a"
  ],
  "backlinks": null,
  "word_count": 445,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

This is the test suite for the Soul Protocol quality validation system. Each of the four test functions (`test_response_quality`, `test_personality_consistency`, `test_hard_recall`, `test_emotional_continuity`) is designed to answer one specific claim about soul value. Passing all four is the bar for asserting that a soul produces measurably better agent behavior.

## Test 1: Response Quality

Runs a warm-up conversation so the soul accumulates context, then poses a challenge message. The `SoulResponder` generates two responses — one with full soul context, one with bare baseline — and `ResponseJudge.compare_pair()` scores them.

The warm-up is critical: without prior interactions the soul has no memories to recall, making it indistinguishable from the baseline. The warm-up ensures the test measures soul recall and personality application, not just system prompt differences.

## Test 2: Personality Consistency

Creates multiple souls with distinct OCEAN profiles (e.g., high-openness artist vs. low-openness accountant), runs identical `shared_turns` through each, and uses a judge prompt that asks: "do these responses reflect clearly different personalities?" A single soul with a fixed system prompt could pass this test by accident; requiring divergence across profiles makes it a genuine personality signal check.

## Test 3: Hard Recall

Plants a specific fact (e.g., a technical detail about GraphQL) in early turns, then floods the conversation with 30 unrelated filler interactions on random topics. The recall probe queries for the planted fact directly.

This test is named "hard" because naive memory implementations fail it in two ways: they either store nothing (0% recall) or store everything and drown the fact in noise (low precision). The 30-filler buffer is calibrated to bury the fact below typical recency-weighted retrieval windows.

```python
def _filler_interactions() -> list[tuple[str, str]]:
    # 30 intentionally unrelated (user, agent) pairs
    # Topics: weather, cooking, movies, cats, traffic, etc.
```

## Test 4: Emotional Continuity

Drives the soul through a multi-stage emotional arc and checks that somatic markers tracked by the soul's affect system reflect the arc trajectory. The probe message asks the soul to comment on how it is feeling, and the judge evaluates whether the response is congruent with the arc.

## API Fixes Applied

The source comment documents a bug fix: `judge.evaluate()` was renamed to `judge.compare_pair()` and `bond.strength` became `bond.bond_strength`. These fields surface in the `soul_score`/`baseline_score` keys returned to the runner. Keeping this history in the source prevents re-introducing the old API names.

## Known Gaps

- `_parse_personality_scores(raw)` parses structured judgment output from the LLM using string parsing rather than a typed schema. If the judge model changes its output format, parsing silently produces zeros rather than raising an error.
- All four tests share `HaikuCognitiveEngine` instances via parameters, but there is no rate-limit coordination between concurrent test runs.
