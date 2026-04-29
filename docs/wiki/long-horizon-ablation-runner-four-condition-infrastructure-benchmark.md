---
{
  "title": "Long-Horizon Ablation Runner — Four-Condition Infrastructure Benchmark",
  "summary": "The `LongHorizonRunner` executes 100+ turn synthetic conversation scenarios through four ablation conditions (Full Soul, RAG Only, Personality Only, Bare Baseline) and collects infrastructure metrics — recall precision, memory count, memory efficiency, bond trajectory — without requiring an LLM for response generation. It optionally integrates DSPy query expansion and significance gating.",
  "concepts": [
    "ablation runner",
    "FULL_SOUL",
    "RAG_ONLY",
    "PERSONALITY_ONLY",
    "BARE_BASELINE",
    "recall precision",
    "memory efficiency",
    "bond trajectory",
    "DSPy query expansion",
    "Soul.birth",
    "observe",
    "significance gating",
    "ConditionResult",
    "LongHorizonResults",
    "infrastructure metrics"
  ],
  "categories": [
    "research",
    "ablation-study",
    "memory",
    "soul-protocol"
  ],
  "source_docs": [
    "f0ab1f4a7de9f91d"
  ],
  "backlinks": null,
  "word_count": 411,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Design Philosophy

The runner was deliberately designed to work without an LLM API key. Infrastructure metrics (how many memories were stored, how precisely can they be recalled, how does bond evolve) do not require generated text. Separating infrastructure measurement from quality measurement keeps the benchmark fast and cost-free by default.

## Four Ablation Conditions

```python
class ConditionType:
    FULL_SOUL = "full_soul"       # OCEAN + memory + significance gating + bond
    RAG_ONLY = "rag_only"         # OCEAN personality, but stores everything flat
    PERSONALITY_ONLY = "personality_only"  # OCEAN only, no memory storage
    BARE_BASELINE = "bare_baseline"         # no personality, no memory
```

For FULL_SOUL, every `observe()` call runs the psychology pipeline (significance scoring, emotional tagging, tier routing). For RAG_ONLY, content is stored directly via `soul.remember()` bypassing the pipeline — this isolates the effect of selectivity. PERSONALITY_ONLY and BARE_BASELINE skip memory entirely, so they always score 0 on recall.

## Soul Creation Per Condition

`_create_soul(condition)` spawns a fresh `Soul` instance for each condition to ensure no shared state. The FULL_SOUL condition optionally enables `use_dspy=True` for the DSPy-optimized significance gate. RAG_ONLY and FULL_SOUL share the same OCEAN personality so comparisons reflect only the pipeline difference, not personality differences.

## Metrics Collected

`ConditionResult` tracks per condition per scenario:

- `recall_hits` / `recall_misses` → `recall_precision` property
- `total_memories`, `episodic_count`, `semantic_count` — accessed via `soul._memory._episodic._memories` and `soul._memory._semantic._facts` (private attribute access, noted explicitly in comments)
- `bond_trajectory` — list of bond strength values sampled each turn (FULL_SOUL only)
- `memory_growth` — (turn_index, memory_count) pairs every 10 turns

## DSPy Query Expansion

When `use_dspy_recall=True`, the runner initializes a `DSPyCognitiveProcessor`. At each test point it calls `expand_query(tp.query)` to generate multiple query variations, then deduplicates recalled memories across all variations before checking for expected content. If DSPy init fails, the runner falls back silently to single-query mode.

## Recall Evaluation

For each `TestPoint` with `test_type == "recall"`, the runner retrieves up to 10 memories, checks whether the expected substring appears in any recalled content (case-insensitive), and records the result in `recall_results` for the analyzer.

## Result Flattening

`LongHorizonResults.to_rows()` flattens the nested scenario/condition structure to a list of dicts suitable for pandas or the `LongHorizonAnalyzer`.

## Known Gaps

- **Private attribute access**: `soul._memory._episodic._memories` and `soul._memory._semantic._facts` break encapsulation. A public `memory_counts()` API on `Soul` would be cleaner.
- **Sequential condition execution**: conditions run sequentially per scenario. Parallelizing across conditions would significantly speed up large studies.
- Bond trajectory is only recorded for FULL_SOUL; RAG_ONLY's bond field is always 0, which may be misleading in analysis output.