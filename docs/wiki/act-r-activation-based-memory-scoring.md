---
{
  "title": "ACT-R Activation-Based Memory Scoring",
  "summary": "Implements Anderson's ACT-R cognitive model for memory recall scoring. Combines power-law recency/frequency decay, query-spreading activation, emotional boost from somatic markers, and personality-modulated ranking to produce a single activation score per memory candidate.",
  "concepts": [
    "ACT-R",
    "base-level activation",
    "spreading activation",
    "memory decay",
    "somatic marker",
    "personality modulation",
    "OCEAN",
    "recall scoring",
    "BM25",
    "emotional boost"
  ],
  "categories": [
    "memory",
    "cognitive-architecture",
    "recall"
  ],
  "source_docs": [
    "10a848da89f53548"
  ],
  "backlinks": null,
  "word_count": 366,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Why ACT-R?

Simple recency-based retrieval favors the most recent memories regardless of relevance. ACT-R (Adaptive Control of Thought — Rational) models how human memory works: frequently accessed memories stay active longer, and the relevance of a query "spreads" activation to related memories. Soul Protocol uses ACT-R to make recall feel natural — important but old memories can still surface when the query is sufficiently related.

## Component Breakdown

### Base-Level Activation

```python
B_i = ln(sum(t_j ^ (-DECAY_RATE)))
```

Each access timestamp contributes `t^(-0.5)` where `t` is seconds since that access. Summing across all accesses then taking the natural log gives a score that rises with frequency and recency. Very old, rarely accessed memories yield negative values — they are not forgotten, just deprioritized.

### Spreading Activation

Query relevance is computed via a pluggable `SearchStrategy` (defaulting to token-overlap). The weight `W_SPREAD = 2.0` is deliberately higher than `W_BASE = 1.0` because BM25-style relevance is the primary recall signal in practice.

### Emotional Boost

`SomaticMarker` objects carry an `arousal` float. When arousal exceeds a threshold, activation gets an additive boost (not multiplicative — v0.3.4 fix). The multiplicative approach amplified negative base activations, making emotionally charged but old memories rank *worse*. The additive formula ensures high arousal always helps.

### Personality Modulation (v0.3.3)

`compute_personality_boost()` uses the soul's OCEAN profile to shift activation. A soul high in Openness may weight novel or creative memories differently than one high in Conscientiousness. The parameter is optional — `personality=None` produces identical scores to pre-v0.3.3 behavior.

### Stochastic Noise

A small Gaussian-like noise term (`NOISE_SCALE = 0.1`) is added to prevent identical memories from always ranking in the same order. This mirrors the natural variability in human memory retrieval.

## Final Score Formula

```
activation = W_BASE * base + W_SPREAD * spread + W_EMOTION * emotion + salience_boost + noise
```

Salience (a per-memory field, default 0.5) is an additive boost derived from the importance/significance score computed at storage time.

## Known Gaps

- `DECAY_RATE` is fixed at 0.5. ACT-R research suggests optimal decay varies by domain; there is no per-soul tuning mechanism yet.
- Stochastic noise uses Python's `random` module, not a seeded generator — results are not reproducible across runs.