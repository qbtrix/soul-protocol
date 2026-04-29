---
{
  "title": "Rule-Based Memory Compressor",
  "summary": "Provides `MemoryCompressor`, a SimpleMem-inspired compression pipeline that reduces memory footprint through deduplication, importance-based pruning, and grouped summarization — entirely without LLM calls.",
  "concepts": [
    "memory compression",
    "deduplication",
    "Jaccard similarity",
    "token overlap",
    "importance pruning",
    "memory export",
    "SimpleMem",
    "rule-based",
    "soul file",
    "MemoryCompressor"
  ],
  "categories": [
    "memory",
    "compression",
    "soul-protocol-core"
  ],
  "source_docs": [
    "86140e8065826551"
  ],
  "backlinks": null,
  "word_count": 327,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Motivation

As a soul accumulates memories over months, raw storage grows unbounded. LLM-based summarization is effective but expensive and slow. `MemoryCompressor` handles the routine compression cases with deterministic rules, reserving LLM calls for genuinely complex consolidation.

## Core Operations

### summarize_memories()

Produces a text summary from a list of `MemoryEntry` objects:

1. Sort by importance descending, then by recency.
2. Deduplicate: skip any entry whose token overlap with an already-included entry exceeds 0.7 (Jaccard similarity).
3. Group by memory type label (`[episodic]`, `[semantic]`, etc.).
4. Concatenate entries until the `max_tokens` word budget is exhausted.

The output is a structured string like:

```
[semantic]
- User prefers dark mode
- User works at Acme Corp
[procedural]
- To reset password: click "Forgot password" on login page
```

### deduplicate()

Filters a list to remove near-duplicates using the same token-overlap metric. When two entries exceed `similarity_threshold` (default 0.8), the lower-importance one is dropped. Equal importance uses recency as the tiebreaker. This is more aggressive than the 0.7 threshold used internally in `summarize_memories()`.

### prune_by_importance()

Removes entries below a minimum importance level. Simple O(n) filter — used when storage limits are tight and importance is the primary pruning signal.

### split_for_export()

Partitions memories into chunks of at most `max_entries` for `.soul` file export. Preserves the importance-sorted order so that if only part of the archive is loaded, the most important memories are in the first chunk.

## Jaccard Similarity Helper

```python
def _token_overlap(a: str, b: str) -> float:
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
```

This is a simple implementation that does not use the enhanced containment coefficient from `dedup.py`. The compressor trades precision for speed — it is designed for bulk offline compression, not real-time ingestion.

## Known Gaps

- `_token_overlap` is a private reimplementation, not shared with `dedup.py`'s `_jaccard_similarity`. The two implementations diverge on short-token handling.
- `summarize_memories()` respects a word-count budget approximation (`len(content.split())`), not actual tokenizer token counts.