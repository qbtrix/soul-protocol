---
{
  "title": "MCPSamplingEngine: Host-LLM Cognitive Routing via MCP",
  "summary": "MCPSamplingEngine routes cognitive prompts to the host LLM (Claude, GPT-4, etc.) through the Model Context Protocol sampling API, so soul-protocol tools embedded in Claude Code or Claude Desktop can leverage the host model without needing a separate API key. It falls back to HeuristicEngine whenever the MCP client does not support sampling or when called outside an MCP context.",
  "concepts": [
    "MCPSamplingEngine",
    "CognitiveEngine",
    "MCP sampling",
    "HeuristicEngine",
    "FastMCP",
    "Context injection",
    "LLM routing",
    "fallback engine",
    "soul-protocol adapters",
    "host LLM"
  ],
  "categories": [
    "cognitive engine",
    "MCP integration",
    "adapters",
    "runtime"
  ],
  "source_docs": [
    "18b3778aafbf5440"
  ],
  "backlinks": null,
  "word_count": 512,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

When soul-protocol runs as an MCP server embedded inside Claude Code or Claude Desktop, it needs a way to run LLM inference for memory tasks — sentiment analysis, significance gating, fact extraction — without requiring a separate API key or billing account. `MCPSamplingEngine` solves this by routing every `think()` call back to the host model through MCP's sampling API. The host LLM pays; soul-protocol just asks.

## How It Works

```python
from soul_protocol.runtime.cognitive.adapters.mcp_sampling import MCPSamplingEngine

@mcp.tool
async def my_tool(ctx: Context) -> str:
    engine = MCPSamplingEngine(ctx)
    result = await engine.think("[TASK:sentiment] Analyze: I love this")
    return result
```

The `ctx` parameter is a `fastmcp.Context` instance that FastMCP injects into any tool handler that declares it via type annotation. `MCPSamplingEngine` wraps this context and calls its sampling methods to forward prompts to the host LLM. The host model processes the prompt and returns text — no separate API credentials required on the soul-protocol side.

## Fallback Chain

Reliability is baked in at three levels:

1. **None context**: If `ctx=None` (tests, non-MCP usage), the engine immediately delegates to `HeuristicEngine` — no exception raised.
2. **NotImplementedError**: If the MCP client does not support sampling (older clients or clients that have not opted into sampling), the engine catches this and falls back to `HeuristicEngine`.
3. **Any other error**: All exceptions during sampling are caught and trigger the heuristic fallback, ensuring the soul never crashes due to a cognitive routing failure.

This guarantees that soul-protocol remains functional even when its runtime environment cannot provide LLM access. The soul degrades gracefully to heuristic behavior rather than breaking entirely.

## Why HeuristicEngine as Fallback

`HeuristicEngine` uses regex-based heuristics that ship with soul-protocol and require zero external dependencies. It produces lower-quality results than an LLM, but it always works — making it the ideal safety net for degraded environments, test suites, and older MCP clients.

## Class Interface

`MCPSamplingEngine` satisfies the `CognitiveEngine` protocol with a single async method:

```python
class MCPSamplingEngine:
    def __init__(self, ctx: object | None) -> None: ...
    async def think(self, prompt: str) -> str: ...
```

The `ctx` type annotation is `object | None` rather than `fastmcp.Context` to avoid a hard dependency on FastMCP at the adapter level. Any object with the sampling interface will work.

## Data Flow

```
Tool handler receives ctx → MCPSamplingEngine(ctx) →
  think(prompt) → ctx.sample(prompt) → host LLM →
  response text returned
        ↓ (on any failure)
  HeuristicEngine.think(prompt) → regex-based result
```

## Deployment Context

This adapter is only meaningful when soul-protocol is deployed as an MCP server — i.e., registered in Claude Code's or Claude Desktop's MCP configuration. In standalone deployments (CLI, embedded library), use `OllamaEngine`, `OpenAIEngine`, or a custom `CognitiveEngine` implementation instead.

## Known Gaps

No known TODOs or FIXMEs in this file. The fallback chain covers all documented failure modes, but the quality gap between MCP sampling and the heuristic fallback is significant — callers that care about accuracy should ensure they run inside a sampling-capable MCP client. There is also no timeout on the sampling call, so a slow or unresponsive host model could stall the tool handler indefinitely.