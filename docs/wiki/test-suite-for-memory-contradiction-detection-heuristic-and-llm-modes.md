---
{
  "title": "Test Suite for Memory Contradiction Detection (Heuristic and LLM Modes)",
  "summary": "Validates the contradiction detector that identifies when a new memory conflicts with existing ones — using both fast heuristic rules (negation patterns, entity-attribute conflicts) and LLM-powered analysis. Tests cover true-positive detection, false-positive prevention, superseded-memory exclusion, similarity thresholds, and graceful fallback when the LLM errors.",
  "concepts": [
    "contradiction detection",
    "heuristic negation",
    "entity-attribute conflict",
    "LLM mode",
    "HeuristicEngine",
    "superseded exclusion",
    "similarity threshold",
    "detect dispatch",
    "false positive prevention",
    "memory integrity"
  ],
  "categories": [
    "testing",
    "memory",
    "contradiction",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "35b5269b111bcf4f"
  ],
  "backlinks": null,
  "word_count": 569,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_contradiction.py` verifies the contradiction detection system, which prevents logically inconsistent facts from coexisting in a soul's memory. When a new memory is about to be stored, the detector checks whether it contradicts any existing memories. If a contradiction is found, the old fact can be superseded or a conflict warning can be raised.

## Heuristic Negation Detection (TestHeuristicNegation)

The heuristic detector uses pattern matching to identify negation-based contradictions without requiring an LLM:

| Test | Pattern |
|---|---|
| `test_likes_vs_dislikes` | "likes X" vs. "dislikes X" |
| `test_is_vs_is_not` | "is X" vs. "is not X" |
| `test_can_vs_cannot` | "can do X" vs. "cannot do X" |
| `test_has_vs_hasnt` | "has X" vs. "hasn't X" |
| `test_true_vs_false` | "X is true" vs. "X is false" |
| `test_works_at_vs_left` | "works at Acme" vs. "left Acme" |

These patterns cover the most common real-world contradictions that arise in conversational memory without requiring expensive LLM inference.

## Entity-Attribute Conflict Detection (TestHeuristicEntityAttribute)

Beyond negation, the heuristic layer detects when two facts assign different values to the same entity attribute:

- `test_different_values_same_attribute` — "Python is their language" vs. "Go is their language" → conflict
- `test_same_values_no_conflict` — identical attribute values → not a contradiction
- `test_different_attributes_no_conflict` — unrelated attributes of the same entity → not a contradiction

## False Positive Prevention (TestNoContradiction)

False positives — flagging contradictions where none exist — would degrade memory quality by refusing to store valid new information:

- `test_unrelated_memories` — facts about different topics must not conflict
- `test_complementary_facts` — related but compatible facts ("uses Python" and "also uses JavaScript") are not contradictions
- `test_superseded_memories_skipped` — memories already marked `superseded=True` are excluded from contradiction checking; a superseded fact no longer represents current truth
- `test_superseded_by_memories_skipped` — similarly, memories that have been superseded by another entry are excluded

The superseded exclusion tests are particularly important: without them, a supersession chain (A → B → C) would incorrectly detect B as contradicting C, even though B was already resolved.

## LLM Mode (TestLLMMode)

When an LLM engine is available, the detector can use it for richer semantic contradiction analysis:

```python
async def test_llm_detects_contradiction():
    # Mocked engine returns a contradiction response → conflict is reported

async def test_llm_no_contradiction():
    # Mocked engine returns "no contradiction" → no conflict raised

async def test_llm_multiple_contradictions():
    # Engine detects conflicts with multiple existing memories simultaneously

async def test_llm_fallback_on_error():
    # If the LLM engine raises, fall back to heuristic detection silently
    # Prevents LLM errors from blocking memory storage entirely
```

The fallback on error is a safety net: LLM availability should enhance contradiction detection but never gate it. A failure to detect via LLM degrades gracefully to heuristic detection.

## Auto-Selection (TestDetectDispatch)

The `detect()` method auto-selects the mode:
- `test_detect_uses_llm_when_available` — if an engine is present, use LLM mode
- `test_detect_uses_heuristic_when_no_engine` — without an engine, use heuristic mode

## Similarity Threshold (TestSimilarityThreshold)

Before running contradiction logic, candidates are pre-filtered by text similarity:

- `test_high_threshold_skips_distant` — a high threshold (e.g., 0.9) means only very similar memories are checked
- `test_low_threshold_catches_more` — a low threshold (e.g., 0.1) means more candidates are checked

The threshold controls the precision/recall tradeoff: lower thresholds catch more potential contradictions but also run more checks (higher cost for LLM mode).

## Known Gaps

No TODOs flagged. There are no tests for the case where both heuristic and LLM detectors are run simultaneously (if such a hybrid mode were ever added).