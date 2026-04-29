---
{
  "title": "Semantic Contradiction Detection for Memory Pipeline",
  "summary": "Detects when a new memory contradicts an existing one using heuristic pattern matching (negation pairs, entity-attribute assertions, verb-based fact patterns) and optional LLM delegation. When a contradiction is detected, the superseded memory is marked rather than deleted.",
  "concepts": [
    "contradiction detection",
    "negation patterns",
    "entity-attribute",
    "verb-fact patterns",
    "superseded memory",
    "Jaccard similarity",
    "CognitiveEngine",
    "heuristic detection",
    "LLM delegation",
    "semantic consistency"
  ],
  "categories": [
    "memory",
    "consistency",
    "cognitive-architecture"
  ],
  "source_docs": [
    "dc6ddc8957a17c78"
  ],
  "backlinks": null,
  "word_count": 292,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## The Problem

Without contradiction detection, a soul could simultaneously believe "User works at Acme" and "User left Acme" — storing both as valid facts. Over time, contradictory facts degrade recall quality and persona consistency.

## Detection Modes

### Heuristic Mode (`detect_heuristic()`)

Three passes:

**Pass 1 — Jaccard similarity filter.** Candidate memories with token overlap below 0.3 to the new content are skipped. This limits the comparison set to topically related memories.

**Pass 2 — Negation pairs.** Regex pairs check if one memory contains an affirmative pattern while the other contains its negation:

```python
(re.compile(r"\blikes?\b"), re.compile(r"\bhates?\b|\bdislikes?\b"))
(re.compile(r"\bis\b"), re.compile(r"\bisn'?t\b"))
```

**Pass 3 — Entity-attribute extraction.** Captures `"User's X is Y"` patterns and flags conflicts between different Y values for the same attribute X.

**Pass 4 — Verb-fact patterns (v0.4.x).** Jaccard alone misses location/employer changes like `"User moved to Amsterdam"` when the old memory says `"User lives in NYC"` — token overlap is too low (~0.15). Verb-fact patterns extract structured facts regardless of overlap and compare values directly:

```python
_VERB_FACT_PATTERNS = [
    (re.compile(r"(?:user|i)\s+(?:live?s?|resides?)\s+in\s+(.+?)"), "location"),
    (re.compile(r"(?:user|i)\s+(?:works?\s+(?:at|for)|joined?)\s+(.+?)"), "employer"),
    # ...
]
```

### LLM Mode (`detect_llm()`)

Delegates to `CognitiveEngine`, which retrieves the top-5 most similar existing memories via semantic search and asks the LLM to identify contradictions. More accurate but slower and requires an active engine.

## Contradiction Resolution

When a contradiction is found, the older memory's `superseded` flag is set to `True`. It is not deleted — this preserves auditability and allows the evolution timeline to show how facts changed over time.

## Known Gaps

- Negation regex pairs are English-only and brittle against paraphrasing (e.g., `"no longer employed"` is not caught by the `"left/quit"` pattern).
- The verb-fact role pattern (`role @ employer`) is a heuristic and may produce false positives for complex sentences.