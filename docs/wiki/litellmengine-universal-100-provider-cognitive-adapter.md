---
{
  "title": "LiteLLMEngine: Universal 100+ Provider Cognitive Adapter",
  "summary": "Implements `CognitiveEngine` using LiteLLM, providing a single adapter that routes cognitive calls to any of 100+ LLM providers including Anthropic, OpenAI, Ollama, Bedrock, Vertex, and Cohere. Provider is selected by model string format (e.g., `anthropic/claude-haiku-4-5-20251001`).",
  "concepts": [
    "LiteLLMEngine",
    "LiteLLM",
    "multi-provider",
    "model string",
    "acompletion",
    "Bedrock",
    "Vertex",
    "Ollama",
    "OpenAI",
    "Anthropic",
    "cognitive engine",
    "universal adapter",
    "provider routing"
  ],
  "categories": [
    "cognitive",
    "adapters",
    "llm",
    "multi-provider"
  ],
  "source_docs": [
    "076beb3e434028e4"
  ],
  "backlinks": null,
  "word_count": 377,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`LiteLLMEngine` is the most flexible cognitive adapter — it delegates to LiteLLM's unified completion API, which handles provider-specific authentication, request formatting, and response parsing behind a consistent interface. This is the right choice when:

- The deployment environment changes between providers.
- Multiple providers need to be compared or load-balanced.
- A provider not covered by native adapters (Bedrock, Vertex, Cohere) is required.

## Provider Selection via Model String

LiteLLM uses a `provider/model-name` format:

```python
# Anthropic via LiteLLM
engine = LiteLLMEngine(model="anthropic/claude-haiku-4-5-20251001")

# OpenAI via LiteLLM
engine = LiteLLMEngine(model="openai/gpt-4o-mini")

# Local Ollama via LiteLLM
engine = LiteLLMEngine(model="ollama/llama3.2")

# AWS Bedrock via LiteLLM
engine = LiteLLMEngine(model="bedrock/anthropic.claude-3-haiku")
```

## Soft Import Pattern

```python
def __init__(self, model: str, **kwargs: Any) -> None:
    try:
        import litellm  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "LiteLLMEngine requires the 'litellm' package. "
            "Install it with: pip install soul-protocol[litellm]"
        ) from exc
    self._model = model
    self._kwargs = kwargs
```

The import check is deferred to `__init__`. The `**kwargs` forwarding gives callers full access to LiteLLM's parameter surface (temperature, timeout, custom headers, proxy settings) without `LiteLLMEngine` needing to enumerate them.

## Think Implementation

```python
async def think(self, prompt: str) -> str:
    import litellm
    response = await litellm.acompletion(
        model=self._model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        **self._kwargs,
    )
    content = response.choices[0].message.content
    return content or ""
```

`litellm.acompletion` is the async entry point. The response follows OpenAI's `choices[0].message.content` shape regardless of the underlying provider — LiteLLM normalizes this.

The `or ""` guard handles the rare case where `content` is `None` (can occur with some providers under certain finish reasons) without raising an exception.

## Trade-offs vs Native Adapters

| | Native Adapter | LiteLLMEngine |
|---|---|---|
| Dependencies | Minimal (one SDK) | LiteLLM (large) |
| Providers | One | 100+ |
| Configuration | Simple | Per-provider setup |
| Debugging | Straightforward | LiteLLM layer adds indirection |

For production single-provider deployments, a native adapter (`AnthropicEngine`, `OpenAIEngine`) is simpler. `LiteLLMEngine` shines for multi-provider routing and provider-agnostic code.

## Known Gaps

- `max_tokens=1024` is hardcoded. Long reflection outputs may be truncated.
- No retry or fallback logic — if the primary model fails, the exception propagates to the caller.
- LiteLLM's dependency footprint is large. Teams with strict dependency policies may prefer native adapters.