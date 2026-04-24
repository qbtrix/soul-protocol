---
{
  "title": "Cognitive Engine Package: Public API and Adapter Exports",
  "summary": "Package init for the cognitive engine subsystem, exporting the base `CognitiveEngine` and `HeuristicEngine` protocols alongside all provider-specific adapters (Anthropic, OpenAI, Ollama, LiteLLM, Callable) and the `engine_from_env()` auto-detection helper.",
  "concepts": [
    "CognitiveEngine",
    "HeuristicEngine",
    "AnthropicEngine",
    "OpenAIEngine",
    "OllamaEngine",
    "LiteLLMEngine",
    "CallableEngine",
    "engine_from_env",
    "cognitive adapters",
    "think protocol",
    "zero-dependency"
  ],
  "categories": [
    "cognitive",
    "engine",
    "adapters",
    "api"
  ],
  "source_docs": [
    "93c0e73dbfed7d07"
  ],
  "backlinks": null,
  "word_count": 285,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The cognitive engine subsystem is how a soul "thinks" — it provides the LLM or heuristic backend that powers memory reflection, interaction analysis, and self-model updates. This `__init__.py` consolidates the public API from two submodules into a single import point.

## Architecture

The cognitive subsystem has two layers:

1. **Engine protocol** (`cognitive.engine`): Defines `CognitiveEngine` (the abstract interface all adapters implement) and `HeuristicEngine` (the zero-dependency fallback).
2. **Adapters** (`cognitive.adapters`): Provider-specific implementations that satisfy the `CognitiveEngine` protocol.

## Exported Names

```python
from soul_protocol.runtime.cognitive.engine import (
    CognitiveEngine,
    HeuristicEngine,
)
from soul_protocol.runtime.cognitive.adapters import (
    AnthropicEngine,
    OpenAIEngine,
    OllamaEngine,
    LiteLLMEngine,
    CallableEngine,
    engine_from_env,
)
```

- **`CognitiveEngine`** — The protocol/interface. Implement `async think(prompt: str) -> str` to create a custom engine.
- **`HeuristicEngine`** — Pattern-matching fallback. Works without any LLM or internet connection.
- **`AnthropicEngine`** — Claude API adapter (requires `soul-protocol[anthropic]`).
- **`OpenAIEngine`** — OpenAI API adapter (requires `soul-protocol[openai]`).
- **`OllamaEngine`** — Local Ollama adapter (requires a running Ollama host).
- **`LiteLLMEngine`** — Universal adapter covering 100+ providers (requires `soul-protocol[litellm]`).
- **`CallableEngine`** — Wraps any sync or async callable. Zero additional dependencies.
- **`engine_from_env()`** — Auto-detects the best available engine from environment variables.

## API History

In v0.2.1, `CognitiveProcessor` and `_parse_json` were removed from the public API. These were internal implementation details that leaked into the exports. The cleanup reduced the public surface to the two consumer-facing types: `CognitiveEngine` (for implementers) and `HeuristicEngine` (for zero-dep use).

## Usage Pattern

```python
from soul_protocol.runtime.cognitive import engine_from_env, AnthropicEngine
from soul_protocol import Soul

# Auto-detect from environment
soul = await Soul.birth(name="Aria", engine=engine_from_env())

# Or pick explicitly
soul = await Soul.birth(name="Aria", engine=AnthropicEngine())
```

## Known Gaps

- No `GeminiEngine` or `BedrockEngine` adapter yet — callers who need these providers should use `LiteLLMEngine` as a bridge.