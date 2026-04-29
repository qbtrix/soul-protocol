---
{
  "title": "Test Suite: Known Sentiment Detector Gaps",
  "summary": "A bug-documenting test suite that captures known failure modes in the heuristic sentiment detector — missing vocabulary, joy/excitement confusion, sadness/frustration confusion, gratitude misclassification, and neutral false positives — intended to go green once the corresponding fixes land in sentiment.py.",
  "concepts": [
    "sentiment gaps",
    "detect_sentiment",
    "missing vocabulary",
    "joy excitement confusion",
    "sadness frustration confusion",
    "gratitude misclassification",
    "neutral false positive",
    "bug documentation",
    "SomaticMarker",
    "arousal threshold"
  ],
  "categories": [
    "sentiment",
    "testing",
    "known-gaps",
    "emotion",
    "test"
  ],
  "source_docs": [
    "2ad72132592c621f"
  ],
  "backlinks": null,
  "word_count": 525,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Known Sentiment Detector Gaps

`test_sentiment_gaps.py` is a deliberate failure-documenting test suite. Created 2026-03-12, it captures real bugs in `detect_sentiment()` that exist in the current implementation. Unlike a normal test suite, these tests are **expected to fail against the current code** — they serve as a regression baseline that turns green once the corresponding fixes land.

### Purpose and Philosophy

This pattern ("failing tests as bug documentation") prevents two common failure modes:
1. **Silently unfixed bugs** — without a test, a known gap may never be addressed
2. **Regression after a fix** — once fixed, the test suite stays green as a permanent guard

The file explicitly states: "DO NOT fix the bugs in this file — fix them in sentiment.py, then these tests go green."

### Gap Category 1: Missing Vocabulary

Many emotionally loaded sentences return `label="neutral"` because the trigger words aren't in the emotion word list:

```python
"I GOT PROMOTED!!!"          # missing: promoted
"We won the championship!"   # missing: won
"They said yes! I'm getting married!"  # missing: married
"This is the best day of my life!"     # missing: best
```

The tests assert these are **not neutral** — they should produce joy or excitement. The underlying fix requires expanding the emotion word list.

### Gap Category 2: Joy/Excitement Confusion

The current arousal scoring tends to push calm joy into excitement because the arousal component is weighted too heavily:

```python
"Baking cookies with grandma always makes me happy"  # should be joy, not excitement
"Everything just clicked perfectly today, feeling great"  # should be joy
"Found my favorite childhood book at a yard sale, delighted"  # should be joy
```

These are warm, low-arousal positive experiences that shouldn't map to the high-arousal `excitement` label. The fix likely requires a lower arousal threshold for the joy/excitement boundary.

### Gap Category 3: Sadness/Frustration Confusion

High-arousal words in negative sentences incorrectly trigger `frustration` when `sadness` is the correct label:

```python
"I lost my job today and I feel hopeless"  # should be sadness
"Feeling really depressed about how things turned out"  # should be sadness
"They broke up with me out of nowhere, I'm heartbroken"  # should be sadness
```

The root cause is that strong negative words have high arousal scores, pushing them above the frustration threshold even for grief/despair contexts.

### Gap Category 4: Gratitude Misclassification

Intensifiers applied to gratitude words overshoot into excitement or curiosity:

```python
"I'm really grateful for your help with this project"  # should be gratitude
"Thank you so much for everything you've done for me"  # should be gratitude
```

### Gap Category 5: Neutral False Positive

Low-intensity positive words can trigger a positive label for observations that carry no real emotion:

```python
"Nice weather today"  # should be neutral — it's an observation
```

### Known Gaps (Meta)

This file is itself a known-gap document — there is no test for emotional subtext (`"My daughter took her first steps today"`) that relies on world knowledge rather than word lists. That gap is acknowledged in the test docstring but not asserted (a test that can never pass with a heuristic approach is not useful as a target).
