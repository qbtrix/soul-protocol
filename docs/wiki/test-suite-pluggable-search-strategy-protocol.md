---
{
  "title": "Test Suite: Pluggable Search Strategy Protocol",
  "summary": "Tests for the SearchStrategy protocol and its propagation through the full memory stack — from Soul.birth() down through MemoryManager, RecallEngine, spreading_activation(), and compute_activation() — verifying that custom scoring functions can replace the default token-overlap approach at every layer.",
  "concepts": [
    "SearchStrategy",
    "TokenOverlapStrategy",
    "BM25SearchStrategy",
    "pluggable search",
    "spreading_activation",
    "compute_activation",
    "MemoryManager",
    "RecallEngine",
    "Soul lifecycle",
    "runtime_checkable protocol",
    "custom scoring"
  ],
  "categories": [
    "search",
    "memory",
    "testing",
    "strategy-pattern",
    "test"
  ],
  "source_docs": [
    "b41ffd965a5aea43"
  ],
  "backlinks": null,
  "word_count": 428,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Test Suite: Pluggable Search Strategy Protocol

`test_strategy.py` (introduced in v0.2.2) validates that soul-protocol's memory search is pluggable end-to-end. The `SearchStrategy` protocol allows any object with a `score(query: str, content: str) -> float` method to replace the built-in token-overlap scoring — enabling BM25, embedding similarity, or domain-specific ranking to be wired in without changing the core memory stack.

### Why a Strategy Protocol?

Different applications need different relevance models. A code assistant benefits from exact-identifier matching; a creative companion might prefer semantic similarity. Hard-coding a single algorithm into the memory stack would require forking the library to change retrieval behavior. The strategy protocol makes scoring an injection point.

### Protocol Compliance (TestSearchStrategyProtocol)

`SearchStrategy` is `@runtime_checkable`, so `isinstance()` can verify compliance at runtime. Tests confirm:
- `TokenOverlapStrategy` satisfies the protocol
- Custom `ConstantStrategy` (always returns `0.99`) satisfies the protocol
- `InvertedStrategy` (reverses ranking order) satisfies the protocol
- Lambda-style objects with a `score` method satisfy the protocol
- Objects with a `rank` method (wrong name) do **not** satisfy the protocol

This guards against accidental duck-typing where a `score` method with the wrong signature silently passes.

### TokenOverlapStrategy Parity

`TestTokenOverlapStrategy` verifies that `TokenOverlapStrategy().score(q, c)` returns identical results to the standalone `relevance_score(q, c)` function. This ensures the strategy wrapper is a true delegate, not a reimplementation with subtle differences.

### spreading_activation Integration

```python
# ConstantStrategy overrides scoring in spreading_activation
results = spreading_activation(entries, query, strategy=ConstantStrategy(0.99))
```

`TestSpreadingActivationStrategy` confirms:
- Without a strategy, `spreading_activation` uses `relevance_score`
- With a custom strategy, the custom `score()` method is called
- `strategy=None` behaves identically to no strategy (explicit None is safe)

### compute_activation Integration

`TestComputeActivationStrategy` verifies that `compute_activation()` passes the strategy through to the underlying spreading activation call, changing the resulting activation score when a custom strategy is used.

### MemoryManager → RecallEngine Flow

```python
@pytest.fixture
def manager_with_strategy(strategy):
    return MemoryManager(..., search_strategy=strategy)
```

`TestRecallWithStrategy` seeds memories, runs `manager.recall()`, and asserts that the `ConstantStrategy.call_count` incremented — proving the strategy was actually invoked rather than bypassed somewhere in the call chain.

### Soul Lifecycle Integration (TestSoulWithStrategy)

Four tests verify that `search_strategy` survives the full `Soul` lifecycle:
- `test_birth_with_strategy` — `Soul.birth(config, search_strategy=...)` stores the strategy
- `test_birth_without_strategy` — `Soul.birth(config)` uses the default (no regression)
- `test_awaken_with_strategy` — loading a soul from disk and rewiring the strategy works
- `test_strategy_preserved_after_clear` — `soul.memory.clear()` does not drop the strategy

### Known Gaps

The test suite uses `ConstantStrategy` and `InvertedStrategy` as test doubles. There are no integration tests for `BM25SearchStrategy` in this file (those live in `test_phase1_fixes.py`). No test covers strategy serialization — strategies are runtime-only and are not persisted in the `.soul` file.
