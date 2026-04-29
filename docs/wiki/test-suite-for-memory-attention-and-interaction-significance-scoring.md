---
{
  "title": "Test Suite for Memory Attention and Interaction Significance Scoring",
  "summary": "Validates the attention system that decides whether an interaction is significant enough to trigger memory storage. Tests cover novelty scoring, emotional intensity detection, goal-relevance matching against core values, and the composite SignificanceScore type.",
  "concepts": [
    "compute_significance",
    "SignificanceScore",
    "novelty scoring",
    "emotional intensity",
    "goal relevance",
    "attention gate",
    "interaction significance",
    "memory threshold",
    "core values",
    "text similarity"
  ],
  "categories": [
    "testing",
    "memory",
    "attention",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "67a4484067f60980"
  ],
  "backlinks": null,
  "word_count": 458,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_attention.py` verifies `compute_significance`, the gate function that determines whether an observed interaction is worth storing in memory. Not every conversation turn is memorable — the attention system filters interactions by novelty, emotional intensity, and relevance to the soul's goals, preventing memory bloat from routine exchanges.

## Test Fixtures

The file defines several factory fixtures that keep test bodies concise:

- `neutral_interaction()` — no emotional words, no proper nouns, no numbers; the baseline low-significance input
- `emotional_interaction()` — contains strong positive emotional language (words like "love", "amazing", "wonderful")
- `meaningful_interaction()` — multi-sentence, covers the soul's core domain
- `core_values()` — a sample list of values used in goal-relevance tests

Using named fixtures rather than inline construction prevents tests from becoming implementation-specific (if the `Interaction` constructor signature changes, only the fixture needs updating).

## Novelty Scoring

```python
def test_first_interaction_novelty_is_max():
    # No prior interactions → novelty == 1.0 (plus any length bonus)
    # A fresh soul has seen nothing, so everything is new

def test_repeated_content_yields_low_novelty():
    # An interaction identical to a recent one → near-zero novelty

def test_repeated_content_multiple_times_stays_low():
    # Repeated exposure does not inflate novelty back up
```

The novelty system compares the current interaction against recent history using text similarity. The "repeated content stays low" test prevents a bug where a sliding-window comparison could accidentally treat old content as novel once it falls out of the window.

## Significance Score Type

`test_first_interaction_score_is_signifance_score_type` [note: typo in test name is in original source] verifies that `compute_significance` always returns a `SignificanceScore` instance, never a raw float. This type contract ensures callers can always access individual components (novelty, intensity, goal_relevance) rather than treating significance as an opaque scalar.

## Emotional Intensity

```python
def test_emotional_input_raises_intensity():
    # Strongly emotional words push emotional_intensity noticeably above zero

def test_emotional_input_stays_within_bounds():
    # emotional_intensity never exceeds 1.0

def test_neutral_input_has_low_emotional_intensity():
    # Plain factual text → near-zero intensity
```

The bounding test matters because intensity feeds into the memory storage decision threshold. Values above 1.0 would break the threshold comparison logic.

## First-Interaction Threshold Behavior

`test_first_interaction_neutral_below_raised_threshold` verifies that a first interaction with neutral tone falls below the `0.5` threshold. This reflects a deliberate design choice: the attention system uses a raised threshold for the very first interaction because there is no baseline to compare against, and novelty alone (which is 1.0 for all first interactions) should not guarantee storage.

## Goal-Relevance

Goal-relevance tests (implied by the `core_values` fixture) measure how well the interaction content aligns with the soul's declared core values. High alignment means the interaction is worth remembering even if it scores low on novelty and emotional intensity.

## Known Gaps

The test name `test_first_interaction_score_is_signifance_score_type` contains a typo (`signifance` instead of `significance`) — a cosmetic issue in the original source, not a behavioral gap. No TODOs or FIXMEs are present.