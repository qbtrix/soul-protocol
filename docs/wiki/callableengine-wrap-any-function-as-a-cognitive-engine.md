---
{
  "title": "CallableEngine: Wrap Any Function as a Cognitive Engine",
  "summary": "Wraps any sync or async callable as a `CognitiveEngine`, letting developers pass a simple lambda or function to `Soul.birth()` without implementing the full protocol. Handles both sync and async callables transparently using `asyncio.iscoroutinefunction` and `run_in_executor`.",
  "concepts": [
    "CallableEngine",
    "callable adapter",
    "sync callable",
    "async callable",
    "run_in_executor",
    "iscoroutinefunction",
    "cognitive engine",
    "prototype",
    "testing",
    "zero-dependency"
  ],
  "categories": [
    "cognitive",
    "adapters",
    "testing",
    "integration"
  ],
  "source_docs": [
    "63b4d3b8d1833ebd"
  ],
  "backlinks": null,
  "word_count": 308,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Implementing the `CognitiveEngine` protocol requires creating a class with an `async think(prompt) -> str` method. For quick prototypes, tests, or situations where the caller already has an LLM function handy, that boilerplate is friction. `CallableEngine` eliminates it:

```python
soul = await Soul.birth(name="Aria", engine=lambda p: my_llm.complete(p))
```

This is the adapter equivalent of accepting a callback instead of requiring a full interface implementation.

## Implementation

```python
class CallableEngine:
    def __init__(self, fn: Callable) -> None:
        self._fn = fn
        self._is_async = asyncio.iscoroutinefunction(fn)

    async def think(self, prompt: str) -> str:
        if self._is_async:
            return await self._fn(prompt)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fn, prompt)
```

**Sync callables**: Run in the default thread pool executor via `loop.run_in_executor`. This prevents a blocking sync LLM call from blocking the entire asyncio event loop — critical when the server handles multiple concurrent soul operations.

**Async callables**: Detected at construction time using `asyncio.iscoroutinefunction()`. Awaited directly in `think()` with no executor overhead.

## Use Cases

1. **Testing**: Pass a `lambda prompt: "test response"` to get a deterministic engine without network calls.
2. **Custom LLM clients**: Wrap an existing LLM client method that doesn't implement `CognitiveEngine`.
3. **Middleware**: Wrap a function that adds logging, caching, or rate limiting around an underlying engine.
4. **Prototyping**: Try soul features without picking a specific adapter.

## Example

```python
from soul_protocol.runtime.cognitive.adapters import CallableEngine
from soul_protocol import Soul

# Sync callable
def my_llm(prompt: str) -> str:
    return requests.post("https://my-llm.com/complete", json={"prompt": prompt}).text

soul = await Soul.birth(name="Aria", engine=CallableEngine(my_llm))

# Or via Soul.birth directly (auto-wrapped)
soul = await Soul.birth(name="Aria", engine=my_llm)
```

## Known Gaps

- No error handling in `think()` — if `_fn` raises an exception, it propagates directly to the caller. Provider-specific adapters (AnthropicEngine, etc.) may add retry logic in the future; `CallableEngine` intentionally does not.
- `get_event_loop()` is deprecated in Python 3.10+ in favor of `asyncio.get_running_loop()`. This may produce deprecation warnings in newer Python versions.