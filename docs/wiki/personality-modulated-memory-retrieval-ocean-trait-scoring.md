---
{
  "title": "Personality-Modulated Memory Retrieval (OCEAN Trait Scoring)",
  "summary": "Maps each of the five OCEAN personality traits to a memory-scoring signal so that a soul's recall results reflect its character rather than pure relevance rank. The module injects per-trait weight deltas into the activation pipeline, remaining fully backwards-compatible when all traits sit at the default 0.5 midpoint.",
  "concepts": [
    "OCEAN personality model",
    "memory modulation",
    "trait delta",
    "activation scoring",
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
    "somatic marker",
    "recall scoring",
    "backwards compatibility"
  ],
  "categories": [
    "memory",
    "personality",
    "recall",
    "OCEAN"
  ],
  "source_docs": [
    "29ee0056dbb0527c"
  ],
  "backlinks": null,
  "word_count": 453,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`personality_modulation.py` answers a deceptively simple question: should two souls with different personalities remember the same event equally? The answer is no — a highly conscientious soul should surface procedural how-tos more readily than an agreeable one, which should prioritize emotionally positive memories. This module encodes that intuition as a scoring layer that sits on top of the ACT-R activation pipeline.

## The OCEAN Trait System

The OCEAN (Big Five) personality model represents five orthogonal dimensions on a 0.0–1.0 scale. Soul Protocol inherits these from `Personality`:

| Trait | What it biases |
|---|---|
| Openness | Semantic + procedural (knowledge-rich) memories |
| Conscientiousness | Procedural memories + high-importance (≥7) facts |
| Extraversion | Episodic memories, entity-dense content |
| Agreeableness | Positive-valence memories (via somatic marker) |
| Neuroticism | High-arousal / emotionally intense memories |

## How the Scoring Works

The core mechanic is a signed delta from neutral:

```python
def _trait_delta(trait_value: float) -> float:
    return trait_value - 0.5
```

A trait at 0.5 produces zero delta — no modulation. A trait at 0.8 produces +0.3; at 0.2, it produces -0.3. This design means that the **default soul (all traits at 0.5) is indistinguishable from a soul with no personality module at all**, which guarantees backwards compatibility for deployments that haven't set personality data.

Each of the five per-trait functions returns a signal in 0.0–1.0:

```python
def _conscientiousness_signal(entry: MemoryEntry) -> float:
    signal = 0.0
    if entry.type == MemoryType.PROCEDURAL:
        signal += 1.0
    if entry.importance >= 7:
        signal += (entry.importance - 6) / 4.0  # 7→0.25 … 10→1.0
    return min(1.0, signal)
```

The final modulation score is the sum of all five `(trait_delta * weight * signal)` terms. Weight caps (`W_* = 0.3`) ensure no single dimension can swing the total beyond ±0.75.

## Why Weight Caps Matter

Without caps, a soul with Neuroticism at 1.0 could flood recall with anxiety-laden memories even when the query is a neutral technical question. The `W_NEUROTICISM = 0.3` cap limits that trait's maximum contribution to ±0.15, so personality colors the result without drowning content-based relevance.

## Integration Point

The output of this module is added as a bonus score during ACT-R activation computation inside `RecallEngine`. It is passed as an optional `personality: Personality` argument so stores that do not need modulation skip the computation entirely.

## Known Gaps

- The weight constants (`W_OPENNESS`, etc.) are fixed at 0.3. There is no per-soul calibration mechanism — a soul cannot learn that its own openness should carry more weight than its neuroticism in its particular use context.
- Extraversion boosts episodic memories but has no signal for *social* entities specifically; it proxies social richness via `entities` count, which can include non-social entities like code modules.
