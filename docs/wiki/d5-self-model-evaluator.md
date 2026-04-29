---
{
  "title": "D5 Self-Model Evaluator",
  "summary": "Measures the soul's ability to dynamically classify user interaction domains, emerge topic confidence quickly, isolate domains without cross-contamination, and extract relationship metadata from conversation. Contributes 15% of the Soul Health Score.",
  "concepts": [
    "self-model",
    "domain classification",
    "domain emergence",
    "confidence threshold",
    "cross-domain isolation",
    "relationship notes",
    "self-image",
    "topic_turns corpus",
    "NER",
    "keyword matching"
  ],
  "categories": [
    "evaluation",
    "self-model",
    "soul-health-score"
  ],
  "source_docs": [
    "8ba96aaa2ac2f274"
  ],
  "backlinks": null,
  "word_count": 447,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The self-model is how a soul understands "what kind of assistant am I becoming for this user." A soul interacting mostly with programming questions should develop high confidence in a technical domain; one discussing emotional topics should develop an emotional companion domain. D5 verifies this emergence is accurate, fast, isolated, and extracting structured data correctly.

## Four Scenarios

### SM-1: Domain Classification
Creates three single-topic souls (technical, writing, emotional), feeds each 30–50 on-topic interactions from `topic_turns.json` corpus, and checks if any of the top-3 self-image domains match the expected topic via keyword matching.

Keyword sets (`_TECH_KEYWORDS`, `_WRITING_KEYWORDS`, `_EMOTION_KEYWORDS`) check for semantic overlap rather than exact domain names, because the self-model generates dynamic domain names from conversation content. A domain named `python_debugging_helper` should match `_TECH_KEYWORDS` even though it was never hard-coded.

### SM-2: Emergence Speed
Feeds technical interactions one at a time and tracks when the first domain's confidence crosses the `0.4` threshold. The turn number at which this happens is the `emergence_turn`. Score penalizes slow emergence: `max(0, 25 - emergence_turn)`. A soul that takes 25+ turns has zero emergence score.

Also tracks confidence values at each turn and computes a Pearson r against the theoretical confidence formula:
```
theoretical = min(0.95, 0.1 + 0.85 * (1 - 1 / (1 + evidence_count * 0.1)))
```

### SM-3: Cross-Domain Isolation
Feeds 30 technical interactions to a soul and then checks that no emotional domain (`emotional_companion` seed domain or any dynamically created emotion domain) has appeared with confidence ≥ 0.3.

This prevents the pathological case where a soul interacting about code gradually develops an emotional companion identity just from accumulated interaction volume. The test specifically checks the seed domain name `"emotional_companion"` because that is the domain initialized at soul birth for companion use cases.

Skipped in `quick=True` mode (returns 1.0).

### SM-4: Relationship Note Extraction
Observes a single interaction: "My boss is named Sarah Chen and I work at Acme Corp." and checks that `soul.self_model.relationship_notes` contains "sarah", "chen", or "boss".

This validates that Named Entity Recognition (NER) or equivalent structured extraction is running and persisting relationship data to the self-model.

## Score Formula

```
score = (domain_accuracy * 35)
      + max(0, 25 - emergence_speed)
      + (domain_specificity * 20)
      + (relationship_note * 10)
      + (confidence_curve_fit * 10)
```

## Known Gaps

- `pearson_r` is duplicated here from `d4_bond.py`—both files define the same function rather than sharing a utility.
- SM-3 is skipped in quick mode, so fast CI runs never catch cross-domain contamination regressions.
- The `writing` domain has no hardcoded fallback interaction set (unlike tech and emotional), so if the corpus is missing writing entries, the SM-1 test silently decrements the total count rather than failing explicitly.