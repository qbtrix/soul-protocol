---
{
  "title": "Test Suite: Phase 1 Ablation Fixes",
  "summary": "Tests for five Phase 1 ablation fixes: the significance gate short-message penalty, mundane-interaction rejection, select_top_k attention selection, BM25Index scoring and the BM25SearchStrategy protocol, and logarithmic bond growth with diminishing returns.",
  "concepts": [
    "significance gate",
    "short message penalty",
    "select_top_k",
    "BM25Index",
    "BM25SearchStrategy",
    "logarithmic bond growth",
    "compute_significance",
    "is_significant",
    "attention selection",
    "bond strength",
    "diminishing returns"
  ],
  "categories": [
    "memory",
    "testing",
    "phase-1",
    "bond",
    "test"
  ],
  "source_docs": [
    "50bdd5f24ad8b95d"
  ],
  "backlinks": null,
  "word_count": 487,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Phase 1 Ablation Fixes

`test_phase1_fixes.py` validates the Phase 1 ablation improvements — targeted fixes identified by ablation testing that showed memory quality degraded without them. The suite covers five distinct fixes: significance gating, attention selection, BM25 search, and bond growth modeling.

### Fix 1: Significance Gate Rejects Short Messages

Short messages produce noise in the memory store because greetings and acknowledgments carry no lasting information.

```python
# "hello" (1 token) → significance score below threshold → rejected
assert is_significant(make_interaction("hello")) is False

# "hello" gets -0.3 penalty for being under 20 tokens
score = compute_significance(make_interaction("hello"))
assert score < overall_significance(...)  # penalized
```

`TestSignificanceGateShortMessages` verifies:
- Single-word inputs (`hello`, `thanks`) are rejected
- The -0.3 penalty is applied for inputs under 20 tokens
- Long messages (above the threshold) receive no penalty

`TestSignificanceGateMundane` tests a complementary filter:
- Pure weather-observation messages (no emotion, no goal relevance) are rejected
- Emotionally loaded messages pass the gate

Without these gates, trivial exchanges like "ok" would consume storage and pollute recall results.

### Fix 2: select_top_k Attention Selection

```python
scores = {"a": 0.9, "b": 0.5, "c": 0.3, "d": 0.1}
result = select_top_k(scores, fraction=0.5)
# marks top 50%: a and b are selected
```

`TestSelectTopK` verifies that only the top `fraction` of scored candidates are marked as significant. This prevents the system from storing every interaction during a highly active session — only the most salient exchanges persist.

Edge cases: empty score dict, single-element dict, all-equal scores.

### Fix 3: BM25Index Scoring

```python
index = BM25Index()
index.add("e1", "postgresql database connection")
results = index.search("database")
# e1 ranks higher than entries without "database"
```

`TestBM25Index` validates:
- TF-IDF-style saturation (BM25's k1 parameter prevents term-frequency explosion)
- IDF weighting (rare terms score higher than common terms)
- `search()` returns results sorted by score
- `remove()` correctly evicts a document from the index
- `corpus_size` tracks the document count

`TestBM25SearchStrategy` verifies that `BM25SearchStrategy` satisfies the `SearchStrategy` protocol and that `score()` returns a normalized float.

### Fix 4: Logarithmic Bond Growth

```python
# Bond strength follows: strength = log(1 + interactions) / log(1 + max_interactions)
```

`TestLogarithmicBondGrowth` verifies three properties:
- At 90 interactions, bond growth has substantially slowed (diminishing returns)
- The bond never reaches 100 even after 100 interactions (asymptotic ceiling)
- Growth rate slows monotonically over time

This models realistic relationship dynamics — the jump from 0 to 10 interactions has a much larger effect on bond strength than the jump from 90 to 100. Without the logarithmic curve, bonds would either plateau too quickly (linear/step) or grow indefinitely (no ceiling).

`test_weaken_still_linear` confirms that bond weakening (`Bond.weaken()`) remains linear, not logarithmic — forgetting is abrupt, bonding is gradual.

### Known Gaps

The mundane-rejection test uses a single example phrase. A broader vocabulary of mundane patterns (small talk, filler words) is not tested. The BM25 parameter values (k1, b) are not tested for optimal calibration — their defaults are accepted as implementation details.
