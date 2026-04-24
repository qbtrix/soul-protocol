---
{
  "title": "engine_from_env: Auto-Detect Best Available Cognitive Engine",
  "summary": "Provides `engine_from_env()`, a zero-configuration helper that inspects environment variables to select the most capable available cognitive engine. Priority order is Anthropic, OpenAI, Ollama, then HeuristicEngine as the always-available fallback.",
  "concepts": [
    "engine_from_env",
    "auto-detection",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OLLAMA_HOST",
    "HeuristicEngine",
    "graceful degradation",
    "environment variables",
    "cognitive engine",
    "zero-dependency fallback"
  ],
  "categories": [
    "cognitive",
    "adapters",
    "configuration",
    "auto-detection"
  ],
  "source_docs": [
    "674a61aaa407738f"
  ],
  "backlinks": null,
  "word_count": 352,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Developers integrating soul-protocol into an application should not need to manually check which API keys are available and wire up the appropriate engine. `engine_from_env()` handles this automatically, making the common case ("use whatever LLM I have configured") a single function call.

## Priority Order

```python
def engine_from_env() -> CognitiveEngine:
    if os.environ.get("ANTHROPIC_API_KEY"):
        # Try AnthropicEngine first
    if os.environ.get("OPENAI_API_KEY"):
        # Try OpenAIEngine second
    if os.environ.get("OLLAMA_HOST"):
        # Try OllamaEngine third
    # Final fallback
    return HeuristicEngine()
```

1. **`ANTHROPIC_API_KEY` → `AnthropicEngine`** — Highest priority. Claude is the primary development target and provides the richest cognitive outputs for soul reflection and self-model updates.
2. **`OPENAI_API_KEY` → `OpenAIEngine`** — Second choice. Wide adoption in existing infrastructure.
3. **`OLLAMA_HOST` → `OllamaEngine`** — Third. Local inference with no external API calls or costs. Privacy-preserving.
4. **`HeuristicEngine`** — Always available. Zero dependencies, zero configuration, zero network calls. Returns pattern-matched responses rather than LLM-generated ones.

## Graceful Degradation on Missing Packages

For each LLM adapter, the function wraps instantiation in a `try/except ImportError`:

```python
if os.environ.get("ANTHROPIC_API_KEY"):
    try:
        from soul_protocol.runtime.cognitive.adapters.anthropic import AnthropicEngine
        return AnthropicEngine()
    except ImportError:
        pass  # anthropic package not installed; try next
```

This handles the case where a user has `ANTHROPIC_API_KEY` set in their environment (perhaps carried over from another project) but has not installed the `anthropic` package. Without this guard, the function would raise `ImportError` and prevent the soul from starting — even though a lower-priority engine (OpenAI, Ollama, Heuristic) might work fine.

## HeuristicEngine Guarantee

The final fallback is unconditional: `HeuristicEngine` is part of the core `soul_protocol` package and has no optional dependencies. Every soul-protocol installation can produce at least a `HeuristicEngine`. This means `engine_from_env()` never raises — it always returns a usable engine.

## Usage

```python
from soul_protocol.runtime.cognitive.adapters import engine_from_env
from soul_protocol import Soul

# Automatically picks up whichever LLM is configured in the environment
soul = await Soul.birth(name="Aria", engine=engine_from_env())
```

## Known Gaps

- No support for `OPENROUTER_API_KEY`, `COHERE_API_KEY`, or other provider-specific keys. Callers who use these providers should use `LiteLLMEngine` directly.
- Priority is hardcoded. There is no `SOUL_ENGINE` override that lets a user force a specific engine when multiple keys are present.