---
{
  "title": "Heuristic Sentiment Detection for Somatic Memory Markers",
  "summary": "Provides zero-dependency emotion detection using curated word lists and a valence-arousal coordinate model, returning a SomaticMarker that the memory pipeline attaches to entries for emotional recall prioritization. Implements Damasio's Somatic Marker Hypothesis without requiring an LLM call.",
  "concepts": [
    "sentiment analysis",
    "somatic marker",
    "valence arousal",
    "emotion detection",
    "word lists",
    "Damasio",
    "SomaticMarker",
    "memory tagging",
    "heuristic NLP",
    "activation boost"
  ],
  "categories": [
    "memory",
    "emotion",
    "NLP",
    "personality"
  ],
  "source_docs": [
    "8a254d3bd28ccfd1"
  ],
  "backlinks": null,
  "word_count": 481,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Damasio's Somatic Marker Hypothesis

Damasio proposed that emotions are not separate from cognition — they are markers attached to memories that influence future decision-making. Soul Protocol applies this to AI companions: memories are tagged with emotional valence (positive/negative) and arousal (intensity), and the ACT-R activation scorer uses these tags to boost emotionally significant memories.

`sentiment.py` provides the detection layer: given raw text from an interaction, it returns a `SomaticMarker` with the emotional fingerprint of that text.

## Why Word Lists Instead of a Model?

The soul observation pipeline runs on every interaction in the hot path. An LLM sentiment call would add 200–500ms of latency and token cost per message. Word-list heuristics run in microseconds with no external dependencies — a critical property for Soul Protocol's goal of being embeddable in any Python runtime.

The tradeoff is accuracy. Word lists miss sarcasm, context, and nuance. The design accepts this in exchange for zero latency and zero cost.

## Valence-Arousal Model

Emotions are represented in a two-dimensional space:
- **Valence** (-1.0 to +1.0): negative to positive
- **Arousal** (0.0 to 1.0): calm to intense

`_classify_label()` maps coordinates to a named emotion label used for human-readable display:

```
high valence + high arousal → "excitement"  
high valence + low arousal  → "contentment"
low valence + high arousal  → "anxiety"
low valence + low arousal   → "sadness"
```

The 2026-03-12 update decoupled arousal from valence — previously arousal was derived from valence magnitude, causing joy and excitement to be indistinguishable from frustration and panic. A separate `AROUSAL_HINTS` word list now drives arousal independently.

## Word List Architecture

```python
POSITIVE_WORDS: dict[str, float] = {
    "love": 0.9, "great": 0.7, "calm": 0.4, ...
}
NEGATIVE_WORDS: dict[str, float] = {
    "hate": -0.9, "frustrated": -0.7, ...
}
```

Values represent intensity within their polarity. Intensity modifiers ("very", "extremely", "a bit") scale adjacent word scores. The ~200-word vocabulary was curated to cover the most common emotion signals without creating false positives on neutral technical text.

A neutral floor threshold was added in 2026-03-12: very mild signals (e.g., a single weak positive word in a long technical message) produce `SomaticMarker(valence=0.0, arousal=0.0, label="neutral")` rather than falsely tagging memories as emotionally significant.

## Integration with Memory Recall

`SomaticMarker` objects are attached to `MemoryEntry` at observation time and persist through serialization. During recall, the activation scorer applies an emotional boost to high-arousal or high-magnitude-valence entries. This means intense emotional memories (a big win, a serious argument) are more likely to surface than bland ones with equivalent recency.

## Known Gaps

- No context window: sentiment is scored per-sentence in isolation. "I don't love this" correctly scores negatively, but "I used to love this but not anymore" would extract the "love" signal from the subordinate clause.
- The vocabulary is English-only. Non-English deployments receive neutral markers on all text.
- No negation handling beyond intensity modifiers (e.g., "not happy" would score positively on "happy").
