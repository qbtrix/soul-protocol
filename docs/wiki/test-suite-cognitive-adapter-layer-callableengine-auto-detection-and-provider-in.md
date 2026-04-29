---
{
  "title": "Test Suite: Cognitive Adapter Layer -- CallableEngine, Auto-Detection, and Provider Integration",
  "summary": "Tests for the adapter layer that bridges Soul Protocol's `CognitiveEngine` protocol with real LLM providers (Anthropic, OpenAI, Ollama) and user-supplied callables. Covers callable wrapping, environment-variable-driven auto-detection, Soul factory integration, import safety for optional dependencies, and HTTP-level mocking for Ollama.",
  "concepts": [
    "CallableEngine",
    "engine_from_env",
    "AnthropicEngine",
    "OpenAIEngine",
    "OllamaEngine",
    "HeuristicEngine",
    "CognitiveEngine",
    "Soul.birth",
    "Soul.awaken",
    "deferred import",
    "auto-detection",
    "TrackingEngine",
    "cognitive adapters",
    "sync executor",
    "async callable"
  ],
  "categories": [
    "testing",
    "cognitive processing",
    "LLM adapters",
    "provider integration",
    "test"
  ],
  "source_docs": [
    "8ef05a963244e4e9"
  ],
  "backlinks": null,
  "word_count": 425,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_cognitive_adapters.py` validates the adapter layer that lets Soul Protocol work with any LLM backend without coupling the core runtime to a specific provider. The adapters translate the `CognitiveEngine.think()` protocol into provider-specific API calls.

## CallableEngine -- Wrapping User Functions

`TestCallableEngine` covers the simplest adapter: wrapping an arbitrary Python callable as a `CognitiveEngine`:

```python
engine = CallableEngine(lambda prompt: f"echo:{prompt}")
result = await engine.think("hello")
assert result == "echo:hello"
```

Key behaviors tested:
- **Sync callables**: executed in a thread pool executor to avoid blocking the event loop
- **Async callables**: awaited directly
- **Detection**: `_is_async` flag correctly distinguishes coroutine functions from sync functions
- **Executor path correctness**: sync functions return the correct value via the executor path

This adapter is the primary integration point for developers who want to bring their own LLM function without implementing the full `CognitiveEngine` protocol.

## engine_from_env -- Automatic Provider Selection

`TestEngineFromEnv` tests environment variable detection:

| Environment Variable | Selected Adapter |
|---------------------|------------------|
| `ANTHROPIC_API_KEY` | `AnthropicEngine` |
| `OPENAI_API_KEY` | `OpenAIEngine` |
| `OLLAMA_HOST` | `OllamaEngine` |
| None of the above | `HeuristicEngine` (fallback) |

The fallback to `HeuristicEngine` is critical: it means Soul Protocol works offline and without API keys -- essential for onboarding and testing.

```python
def test_engine_from_env_anthropic_missing_package(monkeypatch):
    # ANTHROPIC_API_KEY set but anthropic package not installed
    # -> ImportError at instantiation, not at import time
```

Optional LLM packages are not imported at module level -- they are deferred to instantiation. This keeps the package lightweight for users who only need heuristic processing.

## Soul Factory Integration

`TestSoulEngineIntegration` verifies that `Soul.birth()` and `Soul.awaken()` correctly accept all engine forms:

```python
async def test_soul_birth_engine_callable():
    soul = await Soul.birth(name="Test", engine=lambda p: "{}")

async def test_soul_birth_engine_none():
    soul = await Soul.birth(name="Test", engine=None)  # -> HeuristicEngine

async def test_soul_birth_engine_auto(monkeypatch):
    soul = await Soul.birth(name="Test", engine="auto")  # -> env var detection
```

## CognitiveProcessor with Tracked Engine

`TrackingEngine` records every prompt sent to `think()`, enabling verification of what the processor actually asks the LLM:

```python
async def test_cognitive_processor_calls_engine_for_sentiment():
    engine = TrackingEngine(response=json.dumps({...}))
    processor = CognitiveProcessor(engine=engine)
    await processor.detect_sentiment(interaction)
    assert any("[TASK:sentiment]" in call for call in engine.calls)
```

## Import Safety

`TestAdapterImportSafety` confirms that adapters for optional packages (`anthropic`, `openai`, `litellm`) raise `ImportError` only at instantiation -- not at import time. This is the deferred-import pattern that keeps `soul_protocol` installable without optional dependencies.

## OllamaEngine HTTP Mocking

`TestOllamaEngine` uses `unittest.mock` to intercept HTTP requests and verify the correct endpoint URL is targeted, the request body matches Ollama's API spec, and the response is correctly deserialized.

## Known Gaps

No TODOs flagged. Suite was introduced with `feat/cognitive-adapters`.