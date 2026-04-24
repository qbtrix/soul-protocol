---
{
  "title": "LIDA Significance Gate for Episodic Memory Storage",
  "summary": "Implements a LIDA-inspired attention gate that decides whether an interaction is significant enough to store as an episodic memory. Four dimensions — novelty, emotional intensity, goal relevance, and content richness — are blended into a single score, filtered by a tunable threshold.",
  "concepts": [
    "LIDA",
    "attention gate",
    "significance score",
    "novelty",
    "emotional intensity",
    "goal relevance",
    "content richness",
    "episodic storage",
    "significance threshold",
    "proper noun detection"
  ],
  "categories": [
    "memory",
    "cognitive-architecture",
    "attention"
  ],
  "source_docs": [
    "956c034d7bb4557c"
  ],
  "backlinks": null,
  "word_count": 341,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Why a Significance Gate?

Without filtering, every interaction — including trivial greetings and filler messages — would be stored as an episodic memory. This bloats storage, degrades recall precision, and wastes context window space. The attention gate in `attention.py` is inspired by LIDA (Learning Intelligent Distribution Agent), which models human conscious attention as a competition among candidate memories for promotion to working memory.

## The Four Dimensions

### 1. Novelty
Measures how different the interaction is from recent episodic memories using token-overlap relevance scoring. High overlap → low novelty. If there are no recent memories, novelty defaults to 1.0 (everything is novel to an empty memory).

### 2. Emotional Intensity
Derived from `detect_sentiment()`. The sentiment score is mapped to an arousal float. The formula was tuned in `phase1-ablation-fixes` to avoid over-weighting neutral interactions that happen to contain one emotion word.

### 3. Goal Relevance
Checks how many of the soul's `core_values` appear as tokens in the interaction text. Normalized by the number of values to produce a 0–1 score.

### 4. Content Richness (added in phase1-tuning)
Counts proper nouns (via regex `[A-Z][a-z]{2,}`), numbers, and tokens from a curated `_SPECIFICITY_MARKERS` set (e.g. `"hired"`, `"allergic"`, `"university"`). This dimension was added because factual statements like "User was diagnosed with celiac disease" carry high long-term value but score low on novelty, emotion, and goal relevance.

## Scoring and Threshold

```
score = 0.3*novelty + 0.2*emotion + 0.2*goal + 0.3*richness
```

Weights sum to 1.0. Short messages (under 12 tokens) receive a 0.15 penalty. The threshold was lowered from 0.5 to 0.4 and then to **0.35** during tuning — the original threshold was too aggressive, discarding factual updates that lacked emotional language.

## Batch Filtering

`select_top_k()` applies the gate to a batch of interactions and returns the top-k by score, useful for bulk ingestion scenarios.

## Known Gaps

- Proper noun detection via `[A-Z][a-z]{2,}` generates false positives for sentence-initial words and common title-cased terms.
- `_SPECIFICITY_MARKERS` is a hard-coded set — there is no mechanism for a soul to declare its own domain-specific significant terms.