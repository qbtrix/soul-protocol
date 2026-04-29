---
{
  "title": "AnthropicEngine: Claude API Cognitive Adapter",
  "summary": "Implements `CognitiveEngine` using Anthropic's Claude API, defaulting to `claude-haiku-4-5-20251001` for fast, cost-effective cognitive processing. Uses a soft import pattern so the module loads without errors even when the `anthropic` package is not installed.",
  "concepts": [
    "AnthropicEngine",
    "Claude API",
    "claude-haiku",
    "soft import",
    "AsyncAnthropic",
    "ANTHROPIC_API_KEY",
    "cognitive engine",
    "think method",
    "max_tokens",
    "optional dependency"
  ],
  "categories": [
    "cognitive",
    "adapters",
    "anthropic",
    "llm"
  ],
  "source_docs": [
    "4ca8a82612a10115"
  ],
  "backlinks": null,
  "word_count": 376,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`AnthropicEngine` connects a soul's cognitive pipeline to Anthropic's Claude API. It is the primary recommended engine for production soul deployments — Claude's instruction-following and JSON output reliability make it well-suited for the structured reflection, evaluation, and self-model update tasks that the cognitive pipeline performs.

## Soft Import Pattern

```python
def __init__(self, api_key=None, model="claude-haiku-4-5-20251001") -> None:
    try:
        import anthropic  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "AnthropicEngine requires the 'anthropic' package. "
            "Install it with: pip install soul-protocol[anthropic]"
        ) from exc

    import anthropic as _anthropic
    self._client = _anthropic.AsyncAnthropic(
        api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
    )
```

The `import anthropic` check runs at construction time, not at module load. This means:
- `from soul_protocol.runtime.cognitive.adapters import AnthropicEngine` always succeeds.
- The `ImportError` with installation instructions only surfaces when actually instantiating the engine.
- `engine_from_env()` can safely attempt `AnthropicEngine()` and fall through to the next engine on `ImportError`.

## Model Choice

Default model: `claude-haiku-4-5-20251001`. Haiku is chosen over Sonnet or Opus because:
- Cognitive operations (reflection, observation, evaluation) send many small prompts.
- Speed and cost matter more than maximum reasoning depth for these tasks.
- The structured JSON outputs required are well within Haiku's capabilities.

Callers can override by passing `model="claude-sonnet-4-5"` or any other Claude model string.

## Think Implementation

```python
async def think(self, prompt: str) -> str:
    message = await self._client.messages.create(
        model=self._model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    block = message.content[0]
    if hasattr(block, "text"):
        return block.text
    return str(block)
```

`max_tokens=1024` caps responses at a reasonable length for cognitive outputs. The `hasattr(block, "text")` check handles both text blocks (the common case) and tool-use blocks (returned in some edge cases when the model misinterprets the prompt as a tool call) — falling back to `str(block)` rather than raising.

## Configuration

- **API key**: Read from `ANTHROPIC_API_KEY` env var by default, or passed explicitly.
- **Model**: Overridable at construction time.
- **Async client**: `AsyncAnthropic` is used throughout — no sync wrapper needed since the `think()` method is `async`.

## Known Gaps

- No retry logic on rate limits or transient API errors. The caller (cognitive engine dispatcher) handles failures by falling back to `HeuristicEngine` in some code paths, but `AnthropicEngine.think()` itself will raise on API errors.
- `max_tokens=1024` is hardcoded. Very long reflection outputs (large memory sets) may be truncated.