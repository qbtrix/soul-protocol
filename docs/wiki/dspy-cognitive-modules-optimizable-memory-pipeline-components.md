---
{
  "title": "DSPy Cognitive Modules: Optimizable Memory Pipeline Components",
  "summary": "This module defines three DSPy-native modules — `SignificanceGate`, `QueryExpander`, and `FactExtractor` — that replace hand-written heuristics in soul-protocol's memory pipeline with learnable, optimizable LLM programs. All DSPy imports are lazy so the module loads safely in environments where DSPy is not installed.",
  "concepts": [
    "DSPy",
    "SignificanceGate",
    "QueryExpander",
    "FactExtractor",
    "ChainOfThought",
    "MIPROv2",
    "lazy import",
    "memory pipeline",
    "fact extraction",
    "query expansion"
  ],
  "categories": [
    "cognitive engine",
    "DSPy",
    "memory pipeline",
    "runtime"
  ],
  "source_docs": [
    "82fabd184924dac4"
  ],
  "backlinks": null,
  "word_count": 451,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul-protocol's memory pipeline originally used regex heuristics and fixed LLM prompts. These modules replace the three most accuracy-sensitive steps with DSPy's `ChainOfThought` modules — structured programs that can be automatically optimized using MIPROv2 against labeled training data. The result is a memory pipeline whose prompts improve over time as more training data is collected.

## Lazy Import Pattern

All DSPy imports are deferred through `_import_dspy()`:

```python
def _import_dspy():
    try:
        import dspy
        return dspy
    except ImportError:
        raise ImportError(
            "DSPy is required for optimizable cognitive modules. "
            "Install it with: pip install soul-protocol[dspy]"
        )
```

Every class constructor calls `_import_dspy()` rather than importing at module level. This means `import soul_protocol.runtime.cognitive.dspy_modules` never fails even without DSPy installed — only instantiation raises the helpful error. This keeps import overhead zero for the majority of soul-protocol users who do not use DSPy.

## SignificanceGate

```python
self._module = dspy.ChainOfThought(
    "user_input, agent_output, core_values: list[str], recent_context: str -> "
    "should_store: bool, novelty: float, emotional_intensity: float, "
    "factual_importance: float, reasoning: str"
)
```

Replaces the heuristic significance scorer. The `recent_context` field enables novelty detection — the module sees what has been discussed recently and can down-score repetitive interactions. The `reasoning` output field is intentional: it creates a chain-of-thought trace that MIPROv2 can use as a teaching signal during optimization.

## QueryExpander

BM25 and token-overlap recall engines miss semantic matches. Someone who talked about "my cat" yesterday will not recall that conversation if they ask "tell me about my pets" today. `QueryExpander` addresses this by generating semantically varied query alternatives:

```python
self._module = dspy.ChainOfThought(
    "query: str, personality_summary: str -> expanded_queries: list[str]"
)
```

The `personality_summary` input grounds expansion in the soul's known interests and vocabulary, avoiding generic expansions that would flood recall results with irrelevant memories.

## FactExtractor

Regex-based fact extraction produces structured but shallow results, frequently missing implicit facts stated conversationally. `FactExtractor` uses LLM comprehension:

```python
self._module = dspy.ChainOfThought(
    "user_input: str, agent_output: str, existing_facts: list[str] -> "
    "facts: list[str], importance_scores: list[float]"
)
```

The `existing_facts` parameter prevents re-extracting facts the soul already knows, keeping the memory store clean and reducing duplicate entries over long interactions.

## Why DSPy ChainOfThought

`dspy.ChainOfThought` adds an intermediate reasoning step before producing structured outputs. For memory tasks where the judgment call is subtle (is this interaction worth remembering?), the reasoning trace meaningfully improves accuracy over direct prediction. The trace also gives MIPROv2 more signal to optimize against during the offline training phase.

## Known Gaps

The modules assume DSPy's structured output parsing handles `list[str]` and `list[float]` fields correctly. In practice, some LMs return these as comma-separated strings that require post-processing. The `DSPyCognitiveProcessor` adapter handles some normalization, but edge cases remain, particularly for models that format lists with numbered bullets rather than JSON arrays.