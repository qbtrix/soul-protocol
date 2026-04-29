---
{
  "title": "Test Suite for MCP Sampling Engine (LLM Think with Heuristic Fallback)",
  "summary": "Validates the MCPSamplingEngine, which wraps the MCP context's sampling capability to give souls LLM-powered reflection, with graceful fallback to the HeuristicEngine when the MCP context is unavailable or raises. Tests cover the success path, three failure scenarios, the no-context path, and the server's engine wiring lifecycle.",
  "concepts": [
    "MCPSamplingEngine",
    "HeuristicEngine",
    "ctx.sample",
    "SamplingResult",
    "think fallback",
    "MCP context",
    "engine wiring",
    "lifespan reset",
    "singleton",
    "LLM reflection",
    "NotImplementedError fallback"
  ],
  "categories": [
    "testing",
    "MCP",
    "sampling engine",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "56103537706bdc81"
  ],
  "backlinks": null,
  "word_count": 501,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_mcp_sampling_engine.py` verifies the `MCPSamplingEngine`, soul-protocol's bridge between the soul's `think()` call and the LLM inference provided by the MCP host. Because the MCP sampling capability is not always available (some hosts don't implement it, some calls time out), the engine must silently fall back to a rule-based `HeuristicEngine` rather than propagating errors.

## Why a Sampling Engine?

Souls can reflect on interactions to consolidate memories and update their emotional state. That reflection requires LLM inference. When running inside an MCP host (e.g., Claude Desktop), the host can provide sampling via `ctx.sample()` — this lets the soul use the same model the user is already talking to, without requiring a separate API key or model configuration. The `MCPSamplingEngine` makes `ctx.sample()` the preferred path when available.

## Success Path (TestMCPSamplingEngineThinkSuccess)

```python
async def test_think_returns_text_from_sampling_result():
    # ctx.sample() returns SamplingResult with .text = "some reflection"
    # engine.think(prompt) must return that text verbatim

async def test_think_handles_none_text_falls_back_to_result():
    # SamplingResult.text is None → fall back to str(result)
```

The `None` text test handles MCP host implementations that return a result object without a `.text` field populated — a real-world edge case in some Claude Desktop versions.

## Fallback on Error (TestMCPSamplingEngineFallbackOnError)

Three failure modes are tested, all of which must produce a silent fallback to `HeuristicEngine`:

| Failure | Why it can happen |
|---|---|
| `NotImplementedError` | Host declares sampling support but hasn't implemented it |
| Generic exception | Unexpected errors in the sampling call |
| Timeout | Long-running model inference in the host |

The silent fallback design is intentional: a soul should not crash or surface an error to the user just because the reflection step couldn't use the best available engine. Degraded-but-functional is better than broken.

## No-Context Path (TestMCPSamplingEngineFallbackWhenNoCtx)

When `ctx=None` (the engine was constructed without an MCP context, e.g., in CLI mode), the engine must:
1. Use `HeuristicEngine` immediately — no attempt to call `ctx.sample()`
2. Not attempt any sample call (verified via mock assertion)

This test prevents a regression where a `None` context check is missing and the engine attempts `None.sample(...)`, causing an `AttributeError`.

## Server Wiring (TestServerWiresEngineOnToolCall)

These tests verify the server-level lifecycle management of the engine:

- `test_get_or_create_engine_creates_engine_with_ctx` — `_get_or_create_engine()` constructs a fresh `MCPSamplingEngine` on first call
- `test_get_or_create_engine_returns_same_instance` — subsequent calls return the cached instance (singleton pattern per MCP session)
- `test_get_or_create_engine_wires_into_loaded_souls` — when souls are already loaded at engine creation time, the engine is injected into each soul's runtime
- `test_lifespan_resets_engine_cache` — when the MCP server's lifespan restarts (e.g., reconnection), the engine cache is cleared so a fresh engine is created with the new context

The singleton pattern (create once, reuse) is important because the MCP context object is only valid for the duration of a single server session. Caching it prevents unnecessary reconstruction overhead on every tool call.

## Known Gaps

No TODOs flagged. The timeout fallback test mocks `asyncio.TimeoutError` but does not test `asyncio.CancelledError` — a related failure mode that could occur if the MCP host cancels an in-flight sampling request.