---
{
  "title": "DSPyCognitiveProcessor: Learnable Memory Cognition via DSPy",
  "summary": "DSPyCognitiveProcessor is a drop-in replacement for `CognitiveProcessor` that routes significance assessment, query expansion, and fact extraction through optimizable DSPy modules instead of hand-written prompts. It bridges DSPy's synchronous execution model to soul-protocol's async architecture via a thread pool executor.",
  "concepts": [
    "DSPyCognitiveProcessor",
    "DSPy",
    "SignificanceGate",
    "QueryExpander",
    "FactExtractor",
    "async sync bridge",
    "run_in_executor",
    "MIPROv2",
    "optimized modules",
    "CognitiveProcessor"
  ],
  "categories": [
    "cognitive engine",
    "DSPy",
    "memory pipeline",
    "runtime"
  ],
  "source_docs": [
    "775275276667bdce"
  ],
  "backlinks": null,
  "word_count": 442,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Hand-written LLM prompts for memory tasks are brittle — small wording changes can flip whether an interaction gets stored, which facts get extracted, or how many recall queries are generated. `DSPyCognitiveProcessor` replaces those fixed prompts with DSPy modules that can be optimized offline using labeled training data, then loaded at runtime for consistently better memory behavior.

## What It Replaces

Only three cognitive tasks are routed through DSPy:

| Task | DSPy module | Why |
|------|-------------|-----|
| Significance assessment | `SignificanceGate` | Most impactful — controls what enters long-term memory |
| Query expansion | `QueryExpander` | Directly affects recall quality |
| Fact extraction | `FactExtractor` | Accuracy-sensitive structured output |

All other tasks (sentiment, entities, self-model updates, reflection) still flow through the standard `CognitiveProcessor`. This targeted augmentation avoids over-engineering while capturing the highest-value improvements.

## Async/Sync Bridge

DSPy modules are synchronous. Soul-protocol is async. The adapter solves this with `asyncio.get_running_loop().run_in_executor()`:

```python
async def assess_significance(self, interaction, core_values, recent_contents):
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, self._run_significance, ...)
    return result
```

This was previously `asyncio.get_event_loop()`, which raised `DeprecationWarning` in Python 3.10+ and could return a different loop than the one currently running. The fix to `get_running_loop()` ensures the DSPy call is submitted to the correct running event loop's thread pool executor, preventing subtle cross-loop bugs in Python 3.12+.

## Loading Optimized Weights

```python
processor = DSPyCognitiveProcessor(
    lm_model="anthropic/claude-haiku-4-5-20251001",
    optimized_path="optimized_modules/"
)
```

If `optimized_path` is provided, the processor loads pre-trained module weights (saved by `SoulOptimizer`) instead of using default zero-shot prompts. This is the production deployment path — optimize offline with `SoulOptimizer`, ship the module files, load at startup.

## Fallback Behavior

If DSPy raises any exception during inference, the adapter falls back to the heuristic path identical to standard `CognitiveProcessor`. This ensures the soul keeps working even if the DSPy LLM call fails or the model is unavailable.

## Helper Functions

- `_safe_float(value)`: Converts DSPy prediction fields to float, handling string representations and `None` gracefully. DSPy's structured output parsing can return numeric fields as strings in some models.
- `_clamp(value, low, high)`: Bounds a float to a range, used to normalize DSPy outputs into the `[0.0, 1.0]` ranges expected by `SignificanceScore`.

## Drop-In Compatibility

`DSPyCognitiveProcessor` implements the same method signatures as `CognitiveProcessor`, making it a true drop-in replacement. Callers that construct a `Soul` with DSPy-enhanced cognition do not need to change any other code.

## Known Gaps

The `FactExtractor` integration is noted as preliminary — DSPy's structured output parsing for `list[str]` fields can be inconsistent with some LMs, returning comma-separated strings instead of proper Python lists. Robust post-processing of extracted facts list may require additional normalization in a future release.