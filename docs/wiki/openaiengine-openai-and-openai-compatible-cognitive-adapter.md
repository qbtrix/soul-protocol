---
{
  "title": "OpenAIEngine: OpenAI and OpenAI-Compatible Cognitive Adapter",
  "summary": "OpenAIEngine connects soul-protocol's cognitive pipeline to OpenAI's chat completions API, or any OpenAI-compatible endpoint such as a local Ollama server in OpenAI mode, vLLM, or LM Studio. The adapter is an optional extra that requires `pip install soul-protocol[openai]` and performs a soft import to avoid breaking the core package for users who don't need it.",
  "concepts": [
    "OpenAIEngine",
    "OpenAI",
    "CognitiveEngine",
    "base_url",
    "soft import",
    "vLLM",
    "Ollama OpenAI mode",
    "OPENAI_API_KEY",
    "optional extras",
    "cognitive adapter"
  ],
  "categories": [
    "cognitive engine",
    "OpenAI",
    "adapters",
    "runtime"
  ],
  "source_docs": [
    "bfea742c98d19642"
  ],
  "backlinks": null,
  "word_count": 461,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`OpenAIEngine` gives soul-protocol access to GPT-4o-mini (and other OpenAI-compatible models) for its memory cognition pipeline. Because the `openai` Python client is not a core dependency, this adapter uses a soft import pattern — the import only happens at instantiation time, not when the module loads. Environments that never instantiate `OpenAIEngine` pay zero import cost.

## Why a Separate Adapter

Soul-protocol is designed to work with any LLM through the `CognitiveEngine` protocol. Bundling the OpenAI client in the core package would bloat it for users running against Ollama, Anthropic, or MCP sampling. The optional extras pattern (`soul-protocol[openai]`) lets users opt in explicitly.

## Usage

```python
from soul_protocol.runtime.cognitive.adapters import OpenAIEngine
from soul_protocol import Soul

# Standard OpenAI
soul = await Soul.birth(name="Aria", engine=OpenAIEngine())

# Local Ollama via OpenAI-compatible endpoint
engine = OpenAIEngine(
    model="llama3.2",
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # Ollama ignores this but the client requires a value
)
```

## The `base_url` Parameter

The `base_url` parameter is the key to provider portability. The OpenAI Python client supports arbitrary base URLs, making `OpenAIEngine` compatible with:

- **Ollama in OpenAI mode** — `http://localhost:11434/v1`
- **vLLM** — any hosted endpoint that mirrors OpenAI's API
- **LM Studio** — `http://localhost:1234/v1`
- **Azure OpenAI** — with appropriate `api_key` and endpoint URL

This is why both `OllamaEngine` and `OpenAIEngine` exist in the adapters package: `OllamaEngine` targets Ollama's native REST API with no key required, while `OpenAIEngine` via `base_url` targets the OpenAI-compatible shim that Ollama also provides — useful when code must stay provider-neutral.

## API Key Handling

```python
client_kwargs = {
    "api_key": api_key or os.environ.get("OPENAI_API_KEY"),
}
```

The key falls back to `OPENAI_API_KEY` from the environment. For local endpoints that ignore the key, a dummy value like `"ollama"` must still be passed because `AsyncOpenAI`'s constructor validates that `api_key` is not `None`.

## Soft Import Pattern

```python
def __init__(self, ...):
    try:
        import openai
    except ImportError as exc:
        raise ImportError(
            "OpenAIEngine requires the 'openai' package. "
            "Install it with: pip install soul-protocol[openai]"
        ) from exc
```

The `ImportError` is raised with a helpful install hint, chaining the original exception with `from exc` so the traceback shows both errors. Raising at instantiation (not module load) means the rest of soul-protocol continues to work even if `openai` is absent from the environment.

## Async Client

The adapter uses `openai.AsyncOpenAI` — the async variant of the official client — so `think()` is a true coroutine that does not block the event loop during the HTTP round-trip.

## Known Gaps

No streaming, retry logic, or rate-limit handling is implemented. The `max_tokens=1024` cap is hardcoded — appropriate for short cognitive task responses but may truncate verbose model outputs on complex reflection prompts. A future enhancement could expose `max_tokens` as a constructor parameter. There is also no timeout configuration; very slow responses will block the calling coroutine indefinitely.