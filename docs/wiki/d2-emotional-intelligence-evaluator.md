---
{
  "title": "D2 Emotional Intelligence Evaluator",
  "summary": "Evaluates four aspects of emotional intelligence: sentiment classification accuracy, significance gate calibration (emotional vs. neutral filtering), mood state responsiveness, and multi-phase emotional arc coherence. Contributes 20% of the Soul Health Score.",
  "concepts": [
    "emotional intelligence",
    "sentiment classification",
    "significance gate",
    "mood state machine",
    "emotional arc",
    "somatic markers",
    "detect_sentiment",
    "valence",
    "arousal",
    "cluster purity",
    "gate calibration"
  ],
  "categories": [
    "evaluation",
    "emotion",
    "soul-health-score"
  ],
  "source_docs": [
    "fdf94abd0fc64b7e"
  ],
  "backlinks": null,
  "word_count": 432,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Emotional intelligence is the soul's ability to sense, retain, and track emotional signals from user interactions. Without it, a companion treats "I'm heartbroken" and "The meeting is at 3" with equal weight—which destroys the relationship model.

## Four Evaluation Scenarios

### EI-1: Sentiment Classification Benchmark
Loads a labeled corpus from `research/eval/corpus/sentiment_labels.json` (61 entries) and measures how accurately `detect_sentiment()` classifies each text against ground-truth labels. Fuzzy matching handles synonyms—"excited" and "excitement" count as the same label via a stem map.

If the corpus file is missing, the function returns `0.0` and logs a warning rather than raising an exception. This prevents a missing file from breaking the entire eval run.

### EI-2: Gate Calibration
Tests the significance gate's ability to discriminate:
- **50 high-emotion interactions** (crafted with POSITIVE_WORDS/negative keywords) → expect ≥ 70% pass rate
- **50 neutral filler interactions** ("The meeting is at 3", "Got it") → expect ≥ 60% rejection rate

The neutral messages were carefully chosen to avoid *any* words in the sentiment detector's keyword lists. "Nice," "good," and "fine" were all excluded because they appear in POSITIVE_WORDS.

### EI-3: Mood State Machine
Feeds five consecutive frustration texts, checks the soul's mood has shifted toward the negative cluster (`CONCERNED`, `CONTEMPLATIVE`, `TIRED`), then feeds five excitement texts and checks for a positive shift (`EXCITED`, `SATISFIED`, `CURIOUS`).

Only two checks are performed (one per phase), so `mood_responsiveness` is binary in practice—either both phases shift correctly (1.0) or at least one fails (0.5 or 0.0).

### EI-4: Emotional Arc Coherence
60 interactions across three emotional phases (happy → sad → angry, 20 each). After all observations, memories are retrieved by phase index and their somatic labels are checked for cluster purity. A well-functioning system should store sad memories with sadness markers, not mix in excitement labels.

This test is skipped in `quick=True` mode and replaced with an estimated default of `0.6`.

## Score Formula

```
score = (sentiment_accuracy * 25)
      + (emotional_storage_rate * 25)
      + (neutral_rejection_rate * 20)
      + (mood_responsiveness * 15)
      + (emotional_arc_coherence * 15)
```

## Key Design Choice

All interaction text pools were deliberately engineered to produce unambiguous signals for the heuristic detector. High-emotion messages contain multiple high-valence keywords; neutral messages contain zero. This prevents test reliability from depending on the detector's ability to handle ambiguous language—that's what EI-1's labeled corpus tests.

## Known Gaps

- The `seed` parameter is accepted but unused—all tests are deterministic because they use fixed text pools rather than generated scenarios.
- EI-4 phase boundary tracking relies on episodic memory list order, which could break if the memory backend changes its insertion ordering.