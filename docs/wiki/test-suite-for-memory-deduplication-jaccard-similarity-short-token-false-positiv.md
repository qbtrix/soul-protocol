---
{
  "title": "Test Suite for Memory Deduplication (Jaccard Similarity, Short-Token False Positives, and Containment Merge)",
  "summary": "Validates the deduplication system that prevents near-identical facts from being stored multiple times, covering the tokenizer, Jaccard similarity computation, short-token false-positive prevention (go vs. js, ai vs. ml), fact reconciliation decisions (CREATE/SKIP/MERGE), and the containment-merge logic for enriched facts.",
  "concepts": [
    "deduplication",
    "Jaccard similarity",
    "_dedup_tokenize",
    "reconcile_fact",
    "CREATE SKIP MERGE",
    "containment merge",
    "short token false positive",
    "stopwords",
    "fact reconciliation",
    "superseded facts",
    "memory dedup"
  ],
  "categories": [
    "testing",
    "memory",
    "deduplication",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "e2c4821df6440d91"
  ],
  "backlinks": null,
  "word_count": 558,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_dedup.py` verifies the deduplication layer that runs before a new semantic fact is stored. Its job is to decide whether the incoming fact is sufficiently different from existing facts to warrant storage. The three possible outcomes are:
- **CREATE** — the fact is novel; store it
- **SKIP** — the fact is a near-duplicate; discard it
- **MERGE** — the fact enriches an existing one; update the existing entry

## Tokenization (_dedup_tokenize)

The tokenizer underpins Jaccard similarity computation. Key design decisions validated here:

- **Preserves short meaningful tokens** — "go", "js", "ai", "ml", "ui", "ux", "ci", "cd" are kept even though they are only 2 characters. Standard stopword lists would drop all 2-character tokens, causing "Go developer" and "JS developer" to tokenize identically.
- **Drops stopwords** — common function words that carry no semantic meaning are removed
- **Drops single-character tokens** — single characters are too short to be meaningful

The short-token preservation is the most important design choice in the tokenizer. Without it, "I use Go" and "I use JS" would have identical token sets and be treated as duplicates — a false positive that would prevent legitimate facts from being stored.

## Jaccard Similarity

Standard Jaccard tests confirm:
- Identical strings → 1.0
- Completely different strings → 0.0
- Both empty → 0.0 (not undefined/error)
- One empty → 0.0
- Partial overlap → proportional score

## Short-Token False Positive Prevention (TestShortTokenFalsePositives)

This test class documents and prevents a specific regression bug: before the short-token fix, all of the following pairs would incorrectly trigger SKIP:

```
("Go developer", "JS developer")   → should CREATE
("AI tools", "ML tools")          → should CREATE
("UI design", "UX design")        → should CREATE
("CI pipeline", "CD pipeline")    → should CREATE
("Go API", "C# API")              → should CREATE
```

But:
```
("Go developer", "Go developer")  → should still SKIP (genuine duplicate)
```

The test class preserves the intent of the original bug fix as executable documentation.

## Fact Reconciliation (TestReconcileFact)

`reconcile_fact()` is the main decision function:

```python
def test_create_when_no_existing_facts():   # Empty store → always CREATE
def test_skip_near_duplicate():             # High similarity → SKIP
def test_create_unrelated_fact():           # Low similarity → CREATE
def test_skips_superseded_facts():          # Superseded facts are ignored during reconciliation
def test_picks_highest_similarity_match():  # When multiple similar facts exist, compare against the best match
```

The superseded-facts test ensures that an already-resolved fact (e.g., an old employer) does not block storage of the new, correct fact.

## Containment Merge (TestContainmentMerge)

Pure Jaccard similarity under-scores enriched facts because the enriched version contains all the tokens of the original plus additional tokens. For example:
- Original: "Uses Python"
- Enriched: "Uses Python for data science and machine learning"

Jaccard of these two is < 0.5, so naive dedup would CREATE instead of MERGE. The containment check detects when the incoming fact is a strict superset of an existing one:

```
test_python_enriched()       → MERGE, not CREATE
test_docker_enriched()       → MERGE, not CREATE
test_postgresql_enriched()   → MERGE, not CREATE
test_dark_mode_enriched()    → MERGE, not CREATE
test_containment_does_not_trigger_skip()  → MERGE ≠ SKIP
test_identical_still_skip()              → identical → SKIP, not MERGE
```

The MERGE outcome updates the existing memory entry rather than creating a parallel one, keeping the memory store clean.

## Known Gaps

No TODOs flagged. There are no tests for the case where both containment merge and supersession apply simultaneously (an enriched fact superseding a different fact with the same template prefix).