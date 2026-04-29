---
{
  "title": "OllamaEngine: Local Model Cognitive Adapter",
  "summary": "OllamaEngine connects soul-protocol's cognitive pipeline to a locally running Ollama server, using the existing `httpx` dependency so no additional packages are required. It posts prompts to Ollama's REST API and returns the model response, enabling fully offline AI companion operation.",
  "concepts": [
    "OllamaEngine",
    "Ollama",
    "local LLM",
    "httpx",
    "CognitiveEngine",
    "offline inference",
    "REST API",
    "llama3.2",
    "cognitive adapter",
    "soul-protocol adapters"
  ],
  "categories": [
    "cognitive engine",
    "local inference",
    "adapters",
    "runtime"
  ],
  "source_docs": [
    "58bc726d96cb7c5b"
  ],
  "backlinks": null,
  "word_count": 485,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`OllamaEngine` is a lightweight cognitive adapter that lets soul-protocol run its memory and personality tasks against a locally running Ollama server. Privacy-conscious deployments and air-gapped environments benefit most — the soul never contacts an external API. Because the core soul-protocol package already depends on `httpx`, this adapter adds zero additional dependencies.

## Why This Adapter Exists

The soul-protocol package already depends on `httpx` for other HTTP operations. By building on that existing dependency rather than adding the `ollama` Python client (a heavier package with its own dependency tree), `OllamaEngine` achieves zero-additional-dependency status. The trade-off is a direct REST implementation instead of using an official SDK, but Ollama's `/api/generate` endpoint is stable and simple enough to target directly.

## Usage

```python
from soul_protocol.runtime.cognitive.adapters import OllamaEngine
from soul_protocol import Soul

soul = await Soul.birth(name="Aria", engine=OllamaEngine(model="llama3.2"))
```

Before use, start Ollama and pull the model:

```bash
ollama serve
ollama pull llama3.2
```

The Ollama server must be running before the soul is created. `OllamaEngine` does not attempt to start the server or poll for its availability.

## Implementation Details

```python
async def think(self, prompt: str) -> str:
    url = f"{self._host}/api/generate"
    payload = {"model": self._model, "prompt": prompt, "stream": False}
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
```

Key decisions:

- **`stream=False`**: Ollama supports streaming, but soul-protocol expects a complete string response from `think()`. Streaming would complicate the interface with no benefit for cognitive tasks.
- **`timeout=120.0`**: Local models can be slow, especially on CPU. A 2-minute timeout prevents indefinite hangs while still accommodating large models on modest hardware.
- **`raise_for_status()`**: HTTP errors surface immediately as exceptions rather than silently returning empty strings. Callers (typically `CognitiveProcessor`) can catch these and route to a fallback engine.
- **Lazy `httpx` import**: Although `httpx` is a core dependency and expected to be present, deferring the import to `think()` provides a clear error message if the environment is unusual.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `model` | `"llama3.2"` | Model name as known to Ollama |
| `host` | `"http://localhost:11434"` | Ollama server base URL |

The `host` parameter's trailing slash is stripped on assignment (`self._host = host.rstrip("/")`), ensuring the URL path construction works correctly regardless of whether the caller includes a trailing slash.

## Comparison with OpenAIEngine

`OllamaEngine` uses Ollama's native API, while `OpenAIEngine` with a `base_url` can also connect to Ollama's OpenAI-compatible endpoint. The native API path is preferred for Ollama-specific deployments because it requires no dummy API key and has a slightly simpler payload structure.

## Known Gaps

No retry logic is implemented — a single transient network error (e.g., Ollama restarting mid-request) will raise an exception. Production deployments may want to wrap `OllamaEngine` with retry middleware or catch exceptions at the `CognitiveProcessor` level. There is also no health check on initialization, so misconfigured `host` values are only discovered at the first `think()` call.