---
{
  "title": "Test Suite: LLM-Powered Memory Reranking and Smart Recall",
  "summary": "Covers `rerank_memories()`, the `_parse_indices()` helper, and `Soul.smart_recall()` — the optional LLM-driven reranking layer on top of heuristic memory retrieval. The suite validates correct ordering, fallback behavior on engine failure or timeout, opt-in flag semantics, and prompt injection defenses.",
  "concepts": [
    "rerank_memories",
    "smart_recall",
    "CognitiveEngine",
    "_parse_indices",
    "LLM reranking",
    "fallback heuristic",
    "engine timeout",
    "prompt injection",
    "memory fence",
    "angle bracket sanitization",
    "opt-in flag",
    "SimpleNamespace stub"
  ],
  "categories": [
    "testing",
    "memory retrieval",
    "LLM integration",
    "security",
    "test"
  ],
  "source_docs": [
    "06e6096b1d27beff"
  ],
  "backlinks": null,
  "word_count": 520,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul Protocol's default `recall()` uses heuristic scoring (BM25-style keyword matching plus recency). `smart_recall()` extends this by sending the top-N candidates to a `CognitiveEngine` (any LLM backend) and asking it to re-rank them by relevance to the query. This test file exists because LLM calls are inherently unreliable — they can fail, hang, return unparseable output, or be exploited via prompt injection — and all of these failure modes must degrade gracefully to the heuristic baseline.

## Core Components Tested

### `rerank_memories(candidates, query, engine, limit)`

This is the inner reranking function. The LLM returns a comma-separated list of 1-based indices (e.g., `"3,1,5"`). The function:
1. Sends a structured prompt with memory content fenced between `=== BEGIN MEMORIES` and `=== END MEMORIES ===` markers
2. Parses the returned indices with `_parse_indices()`
3. Returns memories in the LLM-specified order

Key edge cases tested:
- **Small candidate set**: If `len(candidates) <= limit`, skip the LLM call entirely and return all candidates. This prevents unnecessary API calls.
- **Engine failure**: `FailingEngine` always raises `RuntimeError`. The function must catch the error and fall back to the first N heuristic results.
- **Unparseable output**: If `_parse_indices()` returns an empty list (no numbers found), fall back to first N.
- **Timeout**: `HangingEngine` sleeps forever. `monkeypatch` lowers `_RERANK_TIMEOUT_SECONDS` to 0.1s; the function must cancel the coroutine and fall back rather than stalling recall.

### `_parse_indices(text, max_index)`

A pure parsing helper that extracts integers from LLM output, deduplicates them, and strips out-of-range values. Tests verify:
- Valid comma-separated input
- Numbers embedded in prose ("The top ones are: 3, 1, and 7")
- Duplicate removal preserves order of first occurrence
- Integers outside `[1, max_index]` are dropped
- Empty string returns `[]`

### `Soul.smart_recall()` Integration

```python
def _make_soul_stub(engine, *, smart_recall_enabled):
    return SimpleNamespace(
        _engine=engine,
        _memory=SimpleNamespace(
            settings=SimpleNamespace(smart_recall_enabled=smart_recall_enabled)
        ),
        recall=None,
    )
```

Because `AsyncMock(spec=Soul)` does not expose private attributes like `_memory`, the tests build a minimal `SimpleNamespace` stub. This is the recommended pattern when mocking classes that heavily use private state.

Opt-in semantics tested:
- `smart_recall_enabled=False` in settings skips reranking even if an engine is present
- A per-call `enabled=True` override forces reranking even when settings disable it
- A per-call `enabled=False` override skips reranking even when settings enable it

## Security: Prompt Injection Defenses

Four dedicated tests protect the reranking prompt from adversarial memory content:

1. **Memory fence**: The prompt must place memory content strictly between `BEGIN/END` markers, and the response instruction must appear after the `END` marker. This prevents memory content from being interpreted as instructions.
2. **Angle bracket stripping**: Memory content with `<` or `>` is sanitized before embedding, blocking tag-structure injection.
3. **Response marker neutralization**: A memory containing `"Selected IDs"` would prime the LLM to treat it as a prior response. The string must be replaced with `[redacted]`.
4. **Query sanitization**: The user query receives the same sanitization as memory content — angle brackets stripped and response markers neutralized.

## Known Gaps

No TODO or FIXME markers are present. The timeout test patches `_RERANK_TIMEOUT_SECONDS` directly, which couples the test to a module-level constant name. If that constant is renamed, the test will silently stop testing timeout behavior.