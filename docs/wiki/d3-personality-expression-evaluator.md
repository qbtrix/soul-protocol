---
{
  "title": "D3 Personality Expression Evaluator",
  "summary": "Tests that a soul's OCEAN personality traits and communication style are faithfully encoded in its system prompt, influence goal relevance scoring, remain stable under sustained interactions, and produce meaningfully different outputs for contrasting profiles. Contributes 15% of the Soul Health Score.",
  "concepts": [
    "OCEAN model",
    "personality expression",
    "system prompt fidelity",
    "value alignment",
    "goal_relevance",
    "compute_significance",
    "personality stability",
    "prompt differentiation",
    "Big Five",
    "communication style"
  ],
  "categories": [
    "evaluation",
    "personality",
    "soul-health-score"
  ],
  "source_docs": [
    "6c9c0749cb9ef8ef"
  ],
  "backlinks": null,
  "word_count": 370,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Personality Expression verifies that the OCEAN model is not just stored data—it actively shapes how the soul communicates. A soul with high openness should produce a different system prompt and behave differently than one with low openness. If personality traits are ignored at inference time, the whole identity model is decorative.

## Four Scenarios

### PE-1: Prompt Fidelity
Births a soul with extreme OCEAN values (openness 0.9, conscientiousness 0.2, extraversion 0.8, agreeableness 0.3, neuroticism 0.7) and checks that `to_system_prompt()` contains all five trait names and four communication style fields (warmth, verbosity, humor, emoji). Returns two metrics: `prompt_fidelity` (0–1) and `comm_coverage` (0–1).

### PE-2: Value-Weighted Significance
Tests that `compute_significance()` scores differently based on core values. Two value sets are compared:
- Soul-A: `["empathy", "compassion", "listening"]` → should score higher on emotional turns
- Soul-B: `["efficiency", "speed", "precision"]` → should score higher on technical turns

The interaction texts were hand-crafted to contain the exact keywords from each value list, making the test sensitive to the `goal_relevance` component of the significance formula. Returns `1.0` only if both souls prefer their matching domain.

### PE-3: Personality Contrast
Creates two souls with opposite OCEAN profiles (all traits 0.9 vs all traits 0.1) and counts differing lines between their system prompts. A differentiation score of `min(1.0, diff_count / 5.0)` requires at least 5 differing lines for full credit.

### PE-4: OCEAN Stability
Observes 50–100 corpus-drawn interactions at regular intervals, checking that personality scores have not drifted by more than `0.001` on any trait. Personality should be immutable through observation—only deliberate `dna.personality` writes should change it.

Corpus turns are loaded from `topic_turns.json`; if the corpus is empty, a hardcoded fallback turn is used to prevent test failure.

## Score Formula

```
score = (prompt_fidelity * 30)
      + (comm_coverage * 10)
      + (value_alignment * 25)
      + (personality_stability * 25)
      + (prompt_differentiation * 10)
```

## Known Gaps

- PE-2 is a binary pass/fail (1.0 or 0.0), creating a cliff effect in the score—partial credit for one soul passing is not possible.
- The `emoji_usage` field was previously named `emoji_use` in the soul birth API; the fix comment notes this was corrected in 2026-03-12. Any callers using the old field name will silently produce incomplete system prompts.