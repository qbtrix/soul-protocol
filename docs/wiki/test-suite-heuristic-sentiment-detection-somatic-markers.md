---
{
  "title": "Test Suite: Heuristic Sentiment Detection (Somatic Markers)",
  "summary": "Tests for the heuristic sentiment detector that produces Damasio-style somatic markers (valence, arousal, label) from raw text, covering neutral text, positive/negative words, intensifiers, negation, mixed emotions, and label accuracy.",
  "concepts": [
    "detect_sentiment",
    "SomaticMarker",
    "valence",
    "arousal",
    "sentiment label",
    "heuristic emotion",
    "intensifiers",
    "negation",
    "Damasio somatic markers",
    "emotion detection",
    "neutral baseline"
  ],
  "categories": [
    "sentiment",
    "memory",
    "testing",
    "emotion",
    "test"
  ],
  "source_docs": [
    "af5b3cf3d2f54b39"
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

## Test Suite: Heuristic Sentiment Detection (Somatic Markers)

`test_sentiment.py` validates `detect_sentiment()`, soul-protocol's heuristic emotion engine that produces `SomaticMarker` values — a valence (positive/negative), arousal (intensity), and label (neutral, joy, excitement, frustration, sadness, gratitude) from free-form text. These markers feed into the personality modulation layer and memory activation scoring.

### Why Heuristic Rather Than ML?

Soul-protocol runs entirely locally without a network call on the critical path. A lexicon-based heuristic produces deterministic, testable results with zero latency and no API dependency, making it suitable for real-time memory observation. The trade-off is coverage (unknown words return neutral), which `test_sentiment_gaps.py` explicitly documents.

### Neutral Baseline

The neutral baseline is the most important invariant:

```python
detect_sentiment("The sky is blue and the water is clear.")
# → SomaticMarker(label="neutral", valence≈0.0, arousal≈0.0)
```

Three separate tests verify that neutral text returns `label="neutral"`, near-zero valence, and near-zero arousal. The empty string and stop-word-only text also return the neutral marker immediately without processing. These tests prevent regressions where adding new emotion words inadvertently give false-positive emotion to mundane text.

### Positive Emotion

- A strong positive word (`love`) produces valence close to its word-list score
- High valence + high arousal → `excitement` label
- Lower arousal positive words → `joy` label
- Tests use a `_within(value, expected, tolerance=0.05)` helper to avoid brittle exact-value assertions on floating-point scores

### Negative Emotion

- `terrible` (score 0.8) produces high arousal → `frustration` label (not `sadness`)
- `frustrated` alone maps to the `frustration` label
- The distinction between frustration (high arousal) and sadness (low arousal) is tested explicitly

### Intensifiers

```python
# "very happy" > "happy" alone
assert detect_sentiment("very happy").valence > detect_sentiment("happy").valence
```

Intensifiers (`very`, `extremely`, `really`) multiply the base word score. Tests verify they raise both valence and arousal without flipping sign.

### Negation

```python
detect_sentiment("not happy").valence  # → negative
detect_sentiment("not bad").valence    # → mildly positive
```

Negation (`not`, `never`, `don't`) flips the following word's valence sign and applies a reduction factor (negating a negative yields mild positive, not strong positive). The tests confirm sign flipping and the asymmetry between negating positives vs. negating negatives.

### Mixed Emotions

When both positive and negative words appear, the dominant score wins. Tests verify directional correctness:
- `test_mixed_emotion_net_valence_direction` — net valence sign tracks the stronger word
- `test_strong_positive_dominates_weak_negative` — high-score positive overrides weak negative
- `test_strong_negative_dominates_weak_positive` — vice versa

### Known Gaps

The heuristic is entirely word-list based. Context-dependent phrases, named events ("promotion", "married"), and idiomatic expressions are not in the word list. These known failures are documented and tested separately in `test_sentiment_gaps.py`.
