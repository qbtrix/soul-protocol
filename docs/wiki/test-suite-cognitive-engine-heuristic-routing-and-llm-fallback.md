---
{
  "title": "Test Suite: Cognitive Engine, Heuristic Routing, and LLM Fallback",
  "summary": "Comprehensive test suite for the Soul Protocol cognitive processing layer, covering HeuristicEngine task routing, CognitiveProcessor LLM integration, JSON parsing helpers, and graceful fallback when LLMs fail or return garbage. Also includes regression tests for the heuristic-only mode bug.",
  "concepts": [
    "CognitiveEngine",
    "HeuristicEngine",
    "CognitiveProcessor",
    "sentiment",
    "significance",
    "fact extraction",
    "entity extraction",
    "reflection",
    "LLM fallback",
    "_parse_json",
    "task marker",
    "heuristic-only mode",
    "MockLLMEngine",
    "FailingEngine",
    "GarbageEngine"
  ],
  "categories": [
    "testing",
    "cognitive processing",
    "LLM integration",
    "fallback resilience",
    "test"
  ],
  "source_docs": [
    "7ee94d7e7fe37ed8"
  ],
  "backlinks": null,
  "word_count": 466,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_engine.py` validates the cognitive processing subsystem responsible for turning raw conversation interactions into structured insights: sentiment scores, significance ratings, extracted facts, entities, and reflections. The suite uses protocol-compliant mock engines to test each processing path in isolation.

## Test Infrastructure

Three mock engine types cover the failure surface:

```python
class MockLLMEngine:
    """Returns predefined JSON responses keyed by task marker."""
    async def think(self, prompt: str) -> str: ...

class FailingEngine:
    """Always raises RuntimeError -- simulates LLM unavailability."""
    async def think(self, prompt: str) -> str: raise RuntimeError("LLM unavailable")

class GarbageEngine:
    """Returns non-JSON -- simulates malformed LLM responses."""
    async def think(self, prompt: str) -> str: return "not JSON"
```

These three classes cover the three real-world failure modes: success, total failure, and partial failure (bad output format).

## HeuristicEngine Routing

`TestHeuristicEngine` validates that the rule-based engine correctly routes each task type and returns well-structured JSON:

- `[TASK:sentiment]` returns `{valence, arousal, label}` with correct polarity
- `[TASK:significance]` returns `{novelty, emotional_intensity, goal_relevance}`
- `[TASK:extract_facts]` returns a list; 'My name is Alice' produces a fact containing 'Alice'
- `[TASK:extract_entities]` returns a list of entity objects
- `[TASK:self_reflection]` and `[TASK:reflect]` return structured reflection results
- Unknown or missing task marker returns an error response, not a crash

## JSON Parsing Helpers

`TestParseJson` covers `_parse_json`, which must handle the variety of formats LLMs actually produce:

| Input Format | Expected Behavior |
|--------------|-------------------|
| Clean JSON object | Parsed directly |
| JSON array | Parsed as list |
| Markdown fenced (```json) | Fence stripped, parsed |
| Preamble text before JSON | Preamble discarded, JSON parsed |
| Invalid JSON | ValueError raised |
| Empty string | ValueError raised |

The preamble and fence-stripping cases exist because models frequently wrap their JSON in prose or code fences when prompted in natural language.

## CognitiveProcessor with LLM

`TestCognitiveProcessorLLM` wires `MockLLMEngine` into `CognitiveProcessor` and verifies end-to-end output for each cognitive task. The mock returns predefined JSON so tests are deterministic.

## Fallback Behavior

`TestFallback` is critical for resilience in production:

```python
async def test_failing_engine_falls_back_sentiment(self):
    # FailingEngine -> CognitiveProcessor falls back to heuristic sentiment

async def test_garbage_engine_falls_back_sentiment(self):
    # GarbageEngine -> parse fails -> falls back to heuristic

async def test_failing_engine_no_fallback_returns_default(self):
    # When no fallback extractor is configured, returns a safe default value
```

The fallback chain ensures that a broken LLM does not crash observation sessions.

## Heuristic-Only Mode Regression

```python
class TestHeuristicOnlyMode:
    """Heuristic-only processor should call v0.2.0 detect_sentiment directly."""
    async def test_sentiment_matches_v020(self):
        # Passing engine=HeuristicEngine() explicitly must preserve heuristic self-model path
```

This test was added (2026-03-04) to fix a regression where passing `engine=HeuristicEngine()` explicitly caused the processor to use a different code path than the implicit heuristic mode, producing inconsistent sentiment scores.

## Known Gaps

No TODOs flagged. The regression tests added in 2026-03-04 are the most recently added coverage.