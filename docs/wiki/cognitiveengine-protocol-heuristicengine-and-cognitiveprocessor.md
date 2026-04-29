---
{
  "title": "CognitiveEngine Protocol, HeuristicEngine, and CognitiveProcessor",
  "summary": "This module defines the core cognitive abstraction layer for soul-protocol: the `CognitiveEngine` protocol (the one interface consumers implement), `HeuristicEngine` (the zero-dependency regex fallback), and `CognitiveProcessor` (the internal orchestrator that turns raw LLM responses into typed memory objects). Together they decouple memory pipeline logic from any specific LLM provider.",
  "concepts": [
    "CognitiveEngine",
    "HeuristicEngine",
    "CognitiveProcessor",
    "Protocol",
    "detect_sentiment",
    "assess_significance",
    "extract_facts",
    "extract_entities",
    "SomaticMarker",
    "SignificanceScore"
  ],
  "categories": [
    "cognitive engine",
    "memory pipeline",
    "runtime",
    "core architecture"
  ],
  "source_docs": [
    "30e4975681ce73a1"
  ],
  "backlinks": null,
  "word_count": 432,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul-protocol's memory system needs to analyze conversation turns for emotional tone, decide what is worth storing, extract discrete facts, identify named entities, and update the soul's self-model. `engine.py` is where all of this is orchestrated — it defines the CognitiveEngine interface that any LLM can satisfy, the HeuristicEngine fallback that needs no LLM, and the CognitiveProcessor that ties them together.

## CognitiveEngine Protocol

```python
@runtime_checkable
class CognitiveEngine(Protocol):
    async def think(self, prompt: str) -> str: ...
```

One method. Any object with an async `think(prompt)` satisfies the protocol. This keeps the bar for custom integrations very low and makes the entire cognitive stack swappable at runtime. The `@runtime_checkable` decorator enables `isinstance(obj, CognitiveEngine)` checks, useful for adapter validation code.

## HeuristicEngine

`HeuristicEngine` is the zero-dependency fallback that ships as part of soul-protocol's core package. It routes incoming prompts by their `[TASK:xxx]` marker and applies regex-based heuristics:

| Task marker | Method | Technique |
|-------------|--------|-----------|
| `[TASK:sentiment]` | `_sentiment` | Keyword lists for positive/negative/arousal |
| `[TASK:significance]` | `_significance` | Event/profile keywords + question detection |
| `[TASK:extract_facts]` | `_extract_facts` | Pattern matching for personal statements |
| `[TASK:extract_entities]` | `_extract_entities` | Capitalized noun detection |
| `[TASK:self_reflection]` | `_self_reflection` | Template-based summary generation |

`HeuristicEngine` never calls an external API, making it suitable for tests, CI, and air-gapped environments where accuracy matters less than reliability.

## CognitiveProcessor

`CognitiveProcessor` is the internal orchestrator. It constructs prompts from templates in `cognitive/prompts.py`, sends them to the configured `CognitiveEngine`, parses JSON responses into typed objects, and falls back to heuristics when the LLM returns malformed JSON.

Key methods and their return types:

- `detect_sentiment(text)` → `SomaticMarker`
- `assess_significance(interaction, core_values, recent_contents)` → `SignificanceScore`
- `extract_facts(interaction, existing_facts, significance)` → `list[MemoryEntry]`
- `extract_entities(interaction, source_memory_id)` → `list[dict]`
- `update_self_model(interaction, facts, self_model)` → mutates `SelfModelManager` in place

## Utility Exports

- `generate_abstract(content)` — generates a short L0 abstract (~400 chars) from memory content, used to populate the `abstract` field of new `MemoryEntry` objects for quick scanning without loading full content.
- `compute_salience(significance)` — maps a `SignificanceScore` to a single `[0.0, 1.0]` float for attention-weighting in the memory retrieval pipeline.

## Keyword Tuning History

The keyword lists in `HeuristicEngine` have been manually tuned to remove false positives — specifically, "from" was removed from `_PROFILE_KEYWORDS` and "may" from `_EVENT_KEYWORDS` because they were triggering significance scores on innocuous messages. This is documented in the file's update history.

## Known Gaps

Heuristic keyword lists are not exhaustive and require ongoing manual tuning. More sophisticated NLP (POS tagging, dependency parsing) would improve precision but would add dependencies that conflict with the zero-dependency goal of `HeuristicEngine`.