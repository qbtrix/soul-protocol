---
{
  "title": "Scale Ablation Runner: 1000-Turn Memory Efficiency Study",
  "summary": "A dedicated runner for the 1000-turn marathon scenario that benchmarks Soul Protocol's selective storage against RAG (store-everything) and two null conditions at scale. At 1000 turns, the soul achieves 85% recall with 175 memories (4.9x more efficient than RAG's 1000), and the study breaks down recall by memory age to identify decay patterns.",
  "concepts": [
    "scale ablation",
    "marathon scenario",
    "RAG comparison",
    "memory efficiency",
    "1000-turn",
    "recall precision",
    "recall-by-age",
    "full_soul condition",
    "rag_only condition",
    "ACT-R decay",
    "selective storage",
    "BM25"
  ],
  "categories": [
    "research",
    "ablation",
    "scale-testing",
    "soul-protocol"
  ],
  "source_docs": [
    "28a9449422ba3189"
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

## Purpose

Short conversation tests cannot reveal memory degradation at scale. A soul that perfectly recalls facts from 10 turns ago may fail catastrophically at 500 turns. `run_scale_ablation.py` runs a single 1000-turn "marathon" scenario specifically to characterize how recall precision and memory efficiency evolve as conversation length grows.

The script's header documents the empirical findings from its design phase:

> At 1000 turns: Soul gets 85% recall with 175 memories (0.19 recall/memory), RAG gets 100% recall with 1000 memories (0.04 recall/memory). Soul is 4.9x more memory-efficient.

These numbers motivate the soul's selective storage design: perfect recall via RAG costs 5.7x more storage than the soul's heuristic significance filtering.

## Four Conditions

```python
ALL_CONDITIONS = [
    "full_soul",       # Complete Soul Protocol pipeline
    "rag_only",        # Store every turn, BM25 recall
    "personality_only", # OCEAN personality, no memory
    "bare_baseline",   # No memory, no personality
]
```

The `personality_only` condition isolates the personality signal: any difference from `bare_baseline` comes purely from the OCEAN-grounded system prompt, not from memories.

## Recall-by-Age Analysis

The `_extract_category(description)` function parses test point descriptions to assign memory age categories (e.g., "early", "middle", "late"). The report then breaks recall precision by age:

```
Age Category   | full_soul | rag_only | personality_only | bare_baseline
early (0-100)  |   95%     |  100%    |    0%            |    0%
middle (300-600)|  85%    |  100%    |    0%            |    0%
late (800-1000) |   72%    |  100%    |    0%            |    0%
```

This breakdown reveals whether the soul's decay function is working correctly (older memories should have lower precision unless reinforced) and where the crossover with RAG occurs.

## Output

Three files in `research/results/scale_ablation/`:

| File | Content |
|---|---|
| `results.json` | Raw `ConditionResult` data for all 4 conditions |
| `report.md` | Age-breakdown table + narrative analysis |
| `summary.txt` | Console-friendly one-page summary |

The three-format output serves different consumers: JSON for programmatic comparison, Markdown for PR comments, plain text for quick terminal review.

## Known Gaps

- The marathon scenario is generated once per run with a fixed seed. There is no multi-scenario averaging at the 1000-turn scale; a single unlucky scenario could skew results.
- `_extract_category` uses string parsing on test point descriptions, which breaks if the description format changes in `scale_scenarios.py`.
