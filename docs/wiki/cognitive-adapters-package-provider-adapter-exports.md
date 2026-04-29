---
{
  "title": "Cognitive Adapters Package: Provider Adapter Exports",
  "summary": "Package init for the cognitive adapters subpackage, re-exporting all provider-specific engine implementations and the `engine_from_env()` auto-detection helper. All adapters use soft imports that raise only at instantiation time, not on module load.",
  "concepts": [
    "cognitive adapters",
    "soft imports",
    "AnthropicEngine",
    "OpenAIEngine",
    "OllamaEngine",
    "LiteLLMEngine",
    "CallableEngine",
    "engine_from_env",
    "optional dependencies",
    "provider adapters"
  ],
  "categories": [
    "cognitive",
    "adapters",
    "api",
    "providers"
  ],
  "source_docs": [
    "4636166bb3fad425"
  ],
  "backlinks": null,
  "word_count": 347,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

This `__init__.py` is the single public entry point for all cognitive engine adapters. It exists to flatten the import path (callers write `from soul_protocol.runtime.cognitive.adapters import AnthropicEngine` rather than reaching into individual adapter files) and to document which adapters exist.

## Soft Import Strategy

Every adapter in this package defers its optional dependency import to instantiation time, not module load time:

```python
# AnthropicEngine.__init__() does:
try:
    import anthropic  # noqa: F401
except ImportError as exc:
    raise ImportError("Install with: pip install soul-protocol[anthropic]") from exc
```

This means `from soul_protocol.runtime.cognitive.adapters import AnthropicEngine` always succeeds, even if the `anthropic` package is not installed. The failure surfaces only when you try to create an instance. This pattern prevents import errors from cascading: a user who only has Ollama installed should not see an `ImportError` for the `anthropic` package just because they imported the adapters package.

## Exported Adapters

| Class | Provider | Extra Required |
|---|---|---|
| `AnthropicEngine` | Claude API | `soul-protocol[anthropic]` |
| `OpenAIEngine` | OpenAI API | `soul-protocol[openai]` |
| `OllamaEngine` | Local Ollama | None (HTTP only) |
| `LiteLLMEngine` | 100+ providers | `soul-protocol[litellm]` |
| `CallableEngine` | Any callable | None |
| `engine_from_env` | Auto-detect | Whichever is installed |

## Design Decisions

Keeping each adapter in its own file (`_auto.py`, `_callable.py`, `anthropic.py`, `litellm.py`, `ollama.py`, `openai.py`) means:

1. Each file has exactly one concern and one optional dependency.
2. Tests can mock individual adapters without affecting others.
3. The `__init__.py` can be updated to add new adapters without touching existing files.

The underscore prefix on `_auto.py` and `_callable.py` signals these are special-purpose adapters (auto-detection logic and the callable wrapper) rather than direct provider integrations.

## Data Flow

```
Soul.birth(engine=engine_from_env())
    -> engine_from_env() checks env vars
    -> returns AnthropicEngine() / OpenAIEngine() / OllamaEngine() / HeuristicEngine()
    -> soul.reflect() calls engine.think(prompt)
    -> engine sends prompt to provider API
    -> returns text response for soul to process
```

## Known Gaps

- No `VertexEngine`, `GeminiEngine`, or `BedrockEngine` adapters. Native adapters for these providers would be cleaner than routing through LiteLLM, but LiteLLM covers them adequately for now.