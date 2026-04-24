---
{
  "title": "ThreeLevelCompactor: Escalating Context Window Management",
  "summary": "`ThreeLevelCompactor` keeps the active context window within a token budget using three escalating strategies: LLM-generated prose summaries, LLM-generated bullet-point compressions, and deterministic head truncation. The compactor always applies the least aggressive level that achieves the budget, and guarantees convergence even without an LLM.",
  "concepts": [
    "ThreeLevelCompactor",
    "context compaction",
    "SUMMARY",
    "BULLETS",
    "TRUNCATED",
    "token budget",
    "ContextNode",
    "compaction DAG",
    "CognitiveEngine",
    "escalation"
  ],
  "categories": [
    "context management",
    "LCM",
    "compaction",
    "runtime"
  ],
  "source_docs": [
    "dac4601b1c846383"
  ],
  "backlinks": null,
  "word_count": 409,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

LLM context windows have hard token limits. When a conversation grows beyond those limits, naive truncation loses history that may be critical for accurate responses. `ThreeLevelCompactor` solves this by progressively compressing older messages rather than deleting them, preserving the most information possible within the constraint.

## The Three Levels

| Level | Name | Method | LLM Required |
|-------|------|--------|--------------|
| 0 | Zero-cost | No action needed (within budget) | No |
| 1 | SUMMARY | LLM summarizes a batch of verbatim messages into prose | Yes |
| 2 | BULLETS | LLM re-compacts existing SUMMARY nodes into bullets | Yes |
| 3 | TRUNCATED | Head-truncation of oldest content | No |

The compactor always starts at the lowest applicable level and escalates only if needed. If no `CognitiveEngine` is provided, it skips straight to Level 3.

## Escalation Logic

```python
async def compact(self, token_budget: int) -> int:
    # Check if already within budget
    current = await self._current_context_tokens()
    if current <= token_budget:
        return 0  # Level 0: no-op

    # Try Level 1: summarize verbatim messages
    removed = await self._compact_level1(token_budget)
    if await self._current_context_tokens() <= token_budget:
        return removed

    # Try Level 2: compress existing summaries to bullets
    removed += await self._compact_level2(token_budget)
    if await self._current_context_tokens() <= token_budget:
        return removed

    # Level 3: deterministic truncation (always converges)
    removed += await self._compact_level3(token_budget)
    return removed
```

## Token Estimation

```python
def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
```

The ~4 chars/token estimate is intentionally rough. Precise tokenization would require loading a tokenizer (adding a dependency), while the heuristic only needs to be accurate enough for compaction decisions. Over-compacting by 10-20% is harmless; under-compacting triggers a retry at the next level.

## Compaction DAG

Each compaction operation creates a `ContextNode` in the SQLite store that references its source messages or child nodes. This DAG structure enables the `expand()` retrieval function to recover original verbatim messages from any compacted node — no data is ever deleted, only summarized.

## Batch Size Tuning

`summary_batch_size` (default configurable) controls how many messages are grouped per Level 1 summary. Larger batches mean fewer LLM calls but more information loss per call. The default balances latency against fidelity.

## Known Gaps

No maximum retry count on Level 3 — if the token estimate function is systematically wrong, Level 3 may not converge on pathological inputs. The `max(1, ...)` guard in `_estimate_tokens` prevents division-by-zero but does not bound the number of truncation iterations.