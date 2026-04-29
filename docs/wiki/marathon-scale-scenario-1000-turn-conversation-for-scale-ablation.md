---
{
  "title": "Marathon Scale Scenario — 1000-Turn Conversation for Scale Ablation",
  "summary": "Generates a fully deterministic 1000-turn synthetic conversation (`marathon_1000`) with 35 strategically planted facts and 40 recall test points designed to reveal the point at which Soul Protocol's selective memory corpus outperforms a naive RAG store. Facts are seeded across the full 1000-turn span — including deeply buried and callback facts — to stress-test long-range recall.",
  "concepts": [
    "1000-turn scenario",
    "scale ablation",
    "marathon test",
    "planted facts",
    "callback facts",
    "buried facts",
    "synthesis query",
    "BM25",
    "filler bank",
    "recall test points",
    "deterministic seed",
    "RAG degradation",
    "TestPoint",
    "LongHorizonScenario",
    "memory precision"
  ],
  "categories": [
    "research",
    "ablation-study",
    "scale-testing",
    "soul-protocol"
  ],
  "source_docs": [
    "2dc5ca306b4a42be"
  ],
  "backlinks": null,
  "word_count": 427,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`scale_scenarios.py` extends the long-horizon study from 100-160 turns to 1000 turns. The research hypothesis is that RAG wins at moderate scale (160 turns) because storing everything keeps recall comprehensive, but at 1000+ turns BM25 search precision degrades as the corpus grows noisier, while Soul's significance-gated corpus stays lean and precise.

## Scenario Structure

The 1000-turn marathon is divided into phases:

| Phase | Turns | Content |
|-------|-------|--------|
| Early facts | 1–100 | 10 planted facts (callback facts, never re-mentioned) |
| Mid facts | 100–500 | 15 planted facts across life events, relationships, preferences |
| Filler | Throughout | Daily updates, mundane topics, extended subjects |
| Professional facts | 500–750 | 5 planted facts (job, family, health, hobbies) |
| Late-game facts | 750–960 | 7 planted facts |
| Recall battery | 961–1000 | 40 recall test turns |

The fact embedding strategy uses three difficulty tiers:

- **Callback facts** — planted turns 10-50, never mentioned again, testing retrieval from the very start of a long conversation
- **Buried facts** — surrounded by 50+ filler turns on both sides, testing precision under maximum noise
- **Synthesis queries** — require cross-referencing multiple stored facts (e.g., "What breed is my dog and what surgery did he need?")

## Filler Banks

Three filler pools (`_DAILY_UPDATES`, `_MUNDANE_TOPICS`, `_EXTENDED_TOPICS`) provide 90+ unique mundane exchanges. Variety is critical: if filler turns are repetitive, BM25 may accidentally learn to ignore the repeated content pattern, giving the RAG condition an artificial advantage.

## Determinism

All filler selection uses `random.Random(seed)` with a fixed seed (default 42). This ensures the exact same 1000-turn sequence is generated on every run, making benchmark results reproducible across machines.

## Recall Test Points

40 `TestPoint` objects cover all 35 planted facts plus 5 synthesis queries. Expected content is a short substring (e.g., `"Camila"`, `"CCL"`, `"Chez Laurent"`) that should appear in any correctly recalled memory. The substring approach tolerates paraphrase in stored content without requiring exact-match scoring.

## Assertion Guard

```python
assert len(turns) == 1000, f"Expected 1000 turns, got {len(turns)}"
```

This assertion prevents silent scenario drift if filler generation or fact planting logic is modified — it would be easy to accidentally add or drop turns when editing the generator.

## Known Gaps

- Only one scenario (`marathon_1000`) is currently generated. `generate_scale_scenarios()` returns a single-element list, leaving room for additional scale scenarios at different turn counts.
- Synthesis queries test cross-fact recall but the current hit check is still a substring match on a single expected string, which does not fully verify multi-fact synthesis.