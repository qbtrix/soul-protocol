---
{
  "title": "Test Suite for Memory Activation Functions (ACT-R Base-Level, Spreading, Emotional Boost)",
  "summary": "Validates the three activation components that determine how retrievable a memory is at query time: the ACT-R base-level activation formula (recency and frequency), spreading activation (query-content token overlap), and emotional boost (somatic marker arousal and valence). Together these tests pin the mathematical contracts that underlie memory retrieval scoring.",
  "concepts": [
    "ACT-R",
    "base-level activation",
    "spreading activation",
    "emotional boost",
    "somatic marker",
    "memory retrieval",
    "recency bias",
    "frequency bias",
    "token overlap",
    "arousal",
    "valence",
    "decay formula"
  ],
  "categories": [
    "testing",
    "memory",
    "activation",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "37e07c1f3c723a80"
  ],
  "backlinks": null,
  "word_count": 525,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_activation.py` verifies the activation functions that score how retrievable each memory is when the soul performs a recall operation. Activation combines three signals: how recently and frequently a memory was accessed (base-level), how relevant it is to the current query (spreading), and how emotionally charged it is (boost). These tests ensure the mathematical contracts of each signal are correct.

## Base-Level Activation (ACT-R Formula)

The base-level activation implements the ACT-R cognitive model formula:

```
BLA = ln( sum(t_j ^ -0.5) )
```

where `t_j` is the time elapsed since each past access in seconds.

Key tests:
- **Empty timestamps → 0.0** — no access history means no activation; prevents `ln(0)` errors
- **Single recent timestamp is positive** — a memory accessed 10 seconds ago has positive activation
- **Recent > old** — a recently accessed memory scores higher than a rarely accessed old one (recency bias)
- **Many accesses > few** — 10 access timestamps produce higher activation than 1 (frequency bias)
- **Formula correctness** — `test_base_level_activation_formula_correctness` computes the exact expected value for two known timestamps and asserts equality within floating-point tolerance. This is a regression anchor that will catch any accidental change to the decay exponent (0.5).
- **`now=None` uses current time** — passing `None` for the reference time must not raise; it defaults to `datetime.now()`

The ACT-R formula was chosen because it naturally captures both recency and frequency effects without requiring separate tuning parameters — the same formula that models human memory decay.

## Spreading Activation

Spreading activation measures semantic relevance via token overlap between the query and the memory's content:

```python
def test_spreading_activation_full_match_returns_one():
    # When every query token appears in content, score == 1.0

def test_spreading_activation_no_overlap_returns_zero():
    # Zero shared tokens → score == 0.0

def test_spreading_activation_bounded_between_zero_and_one():
    # Score always in [0.0, 1.0] regardless of inputs
```

The bounding test is critical: downstream code that combines activation components assumes all scores are in [0, 1]. If spreading activation ever returned a value > 1, combined scores would be miscalibrated.

## Emotional Boost

The emotional boost adds extra retrievability for emotionally significant memories, modeled via somatic markers:

- **No somatic marker → 0.0** — absence of emotion contributes nothing
- **High arousal → high boost** — maximum arousal (1.0) with neutral valence produces a large boost. High arousal memories (surprising, exciting, alarming events) should be more retrievable.
- **High absolute valence contributes** — both strongly positive and strongly negative valence increase the boost; emotional intensity is about magnitude, not direction

The emotional boost reflects the psychological finding that emotionally charged events are recalled more reliably than neutral ones — a deliberate design choice to make souls feel more human in their memory behavior.

## Combined Activation

These three components are additive inputs to the final retrieval score. No combined-activation tests appear here — those live in higher-level integration tests — but these unit tests provide the mathematical foundation that integration tests depend on.

## Known Gaps

No TODOs flagged. The formula correctness test uses hardcoded expected values computed manually — if the decay exponent is intentionally changed in the future, this test will fail and require updating, which is the intended behavior.