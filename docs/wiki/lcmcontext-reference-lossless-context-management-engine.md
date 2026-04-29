---
{
  "title": "LCMContext: Reference Lossless Context Management Engine",
  "summary": "`LCMContext` is soul-protocol's reference implementation of the `ContextEngine` protocol. It ingests conversation messages into an append-only SQLite store, assembles token-bounded context windows with automatic three-level compaction, and exposes grep/expand/describe retrieval tools — all without requiring a `Soul` instance.",
  "concepts": [
    "LCMContext",
    "ContextEngine",
    "Lossless Context Management",
    "ingest",
    "assemble",
    "grep",
    "expand",
    "describe",
    "SQLiteContextStore",
    "ThreeLevelCompactor"
  ],
  "categories": [
    "context management",
    "LCM",
    "runtime",
    "core architecture"
  ],
  "source_docs": [
    "350dd2fd824987b3"
  ],
  "backlinks": null,
  "word_count": 411,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Intra-session context management is the problem of maintaining a coherent conversation history that fits within an LLM's context window. `LCMContext` solves this with a lossless approach: nothing is ever deleted, only progressively compressed. The original messages remain recoverable via `expand()` no matter how many compaction rounds have occurred.

## Standalone Usage

`LCMContext` works without a `Soul` — it can be used as a general-purpose context manager for any LLM-powered application:

```python
from soul_protocol.runtime.context import LCMContext

lcm = LCMContext(db_path="session.db")
await lcm.initialize()

await lcm.ingest("user", "What's the plan for today?")
await lcm.ingest("assistant", "We'll start with the architecture review...")

result = await lcm.assemble(max_tokens=4096)
# result.messages: ready-to-send message list
# result.was_compacted: True if compaction ran this call
```

## Core Operations

### ingest(role, content, **metadata)
Appends a message to the immutable store. Assigns a monotonically increasing sequence number that determines ordering in `assemble()` and `expand()`. Returns the assigned message ID. Accepts arbitrary `metadata` kwargs for caller-specific tagging (e.g., model name, tool call ID).

### assemble(max_tokens, *, system_reserve)
The central operation. Loads messages newest-first until the token budget is exhausted, then triggers compaction if the full history exceeds the budget. Returns an `AssembleResult` containing the message list and compaction statistics.

`system_reserve` (default 256) subtracts tokens from `max_tokens` before assembly, reserving headroom for system prompts that the caller will prepend to the assembled context.

### Retrieval Tools

| Method | Description |
|--------|-------------|
| `grep(pattern)` | Regex search across all stored messages |
| `expand(node_id)` | Recover original messages from any compacted node |
| `describe()` | Metadata snapshot: message count, token totals, compaction statistics |

These mirror the MCP tools exposed by soul-protocol's MCP server, giving agents programmatic access to the same context inspection capabilities available through the tool interface.

## Initialization Guard

Every public method calls `_ensure_initialized()` before touching the store. If `initialize()` was not called, callers get a clear `RuntimeError` with instructions rather than a cryptic SQLite error about accessing an uninitialized connection.

## Compaction Threshold

`compaction_threshold` (default 0.9) determines when compaction runs during `assemble()`. If the assembled token count exceeds `max_tokens * compaction_threshold`, compaction is triggered proactively before the window is completely exhausted. This prevents waiting until the absolute limit before compacting, which would produce more aggressive (lower quality) compaction than earlier, gentler compression.

## Known Gaps

No cross-session context linkage — each `LCMContext` instance manages one session's history independently. Connecting multiple sessions into a longer-term narrative is left to the soul's episodic memory layer, which operates at a different time scale.