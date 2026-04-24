---
{
  "title": "Semantic Memory Deduplication and Fact Reconciliation",
  "summary": "Implements `reconcile_fact()`, the gating function that decides whether a new semantic fact should be created, merged into an existing entry, or skipped as a near-duplicate. Uses an enhanced Jaccard similarity with a containment coefficient to handle enriched/superset facts correctly.",
  "concepts": [
    "deduplication",
    "reconcile_fact",
    "Jaccard similarity",
    "containment coefficient",
    "SKIP MERGE CREATE",
    "semantic memory",
    "fact reconciliation",
    "token overlap",
    "stopwords",
    "superset detection"
  ],
  "categories": [
    "memory",
    "deduplication",
    "semantic"
  ],
  "source_docs": [
    "29552e5cccef6598"
  ],
  "backlinks": null,
  "word_count": 340,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Why Deduplication Matters

Every time the soul observes an interaction, it extracts facts and attempts to store them as semantic memories. Without deduplication, the same fact phrased slightly differently would accumulate indefinitely. `reconcile_fact()` enforces three outcomes: **CREATE** (new information), **SKIP** (near-duplicate, drop it), or **MERGE** (enriched version of an existing fact, update in place).

## Enhanced Jaccard Similarity

Standard Jaccard similarity dilutes the score when one fact is a superset of another. For example, `"User is a Python developer"` vs `"User is a senior Python developer at Acme"` share few tokens relative to their union — Jaccard ~0.4 — which would incorrectly trigger CREATE.

The **containment coefficient** addresses this:

```python
min_size = min(len(tokens_a), len(tokens_b))
if min_size >= 3:
    containment = len(intersection) / min_size
    return max(jaccard, containment * 0.75)
```

The containment score measures what fraction of the *smaller* set is present in the larger. Scaled by 0.75 to stay below the SKIP threshold (0.85), it pushes superset relationships into the MERGE range (0.6–0.85).

## Decision Thresholds

| Score Range | Decision |
|---|---|
| > 0.85 | SKIP — near-duplicate, discard |
| 0.6 – 0.85 | MERGE — update existing entry |
| < 0.6 | CREATE — genuinely new fact |

## Tokenization for Dedup

Dedup uses `min_length=2` tokenization (via `search.tokenize()`) to preserve short meaningful tokens like `go`, `js`, `ai`, `ml`, `ui`. The default `min_length=3` would discard these. A curated `_STOP_WORDS_2` frozenset removes common 2-letter function words (`"is"`, `"at"`, `"by"`) that would otherwise inflate overlap scores.

## reconcile_fact() Integration

`MemoryManager.observe()` calls `reconcile_fact()` for each extracted fact. On MERGE, the existing `MemoryEntry` content is updated and its importance may be elevated. On SKIP, the new fact is silently dropped. On CREATE, a new entry is stored in `SemanticStore`.

## Known Gaps

- The containment boost only activates when `min_size >= 3`. Very short facts (1-2 tokens after stopword removal) fall back to pure Jaccard, which may under-detect duplicates.
- MERGE updates the content string but does not merge entity lists or other structured fields from the original entry.