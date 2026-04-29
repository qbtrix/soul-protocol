---
{
  "title": "FastMCP Server: 28-Tool Soul Protocol Agent Integration",
  "summary": "Implements the full soul-protocol MCP server using FastMCP, exposing 28 tools, 3 resources, and 2 prompts for AI agent integration. Manages a registry of multiple souls, handles auto-reload from disk, lazy cognitive engine wiring, and graceful shutdown with auto-save.",
  "concepts": [
    "FastMCP",
    "MCP server",
    "SoulRegistry",
    "MCPSamplingEngine",
    "lifespan",
    "auto-reload",
    "file watcher",
    "soul tools",
    "LCM context",
    "soul_observe",
    "soul_reflect",
    "soul_dream",
    "soul_health",
    "lazy engine wiring",
    "multi-soul"
  ],
  "categories": [
    "mcp",
    "server",
    "integration",
    "memory",
    "cognitive"
  ],
  "source_docs": [
    "1dd939e2c05703a0"
  ],
  "backlinks": null,
  "word_count": 444,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Architecture Overview

The MCP server is the primary integration surface for AI agents — it makes soul identity, memory, emotion, and evolution available as MCP tools that any MCP-compatible host (Claude Desktop, Claude Code, etc.) can call.

## SoulRegistry

`SoulRegistry` manages multiple named souls in a single server process:

- Each soul is keyed by lowercase name.
- One soul is "active" at any time; tools that omit the `soul` parameter operate on the active soul.
- Per-key `asyncio.Lock` instances prevent concurrent reloads of the same soul (e.g., background watcher and a tool call racing).
- A `_modified` set tracks which souls need saving on shutdown.

## Lifecycle and Auto-Reload

The `_lifespan` async context manager runs on server start/stop:

1. **Startup**: Scans `SOUL_DIR` for `.soul` files and subdirectories with `soul.json`, or loads a single soul from `SOUL_PATH`. Auto-detects `.soul/` in CWD or `~/.soul/` if no env vars are set.
2. **File watcher**: A background task polls soul file `mtime` every 2 seconds (configurable via `SOUL_POLL_INTERVAL`). When an external process modifies a `.soul` file, the in-memory soul is replaced before the next tool call.
3. **Shutdown**: Cancels the file watcher, auto-saves all modified souls, closes LCM contexts, and resets module-level state for clean restarts.

## Lazy MCPSamplingEngine Wiring

Cognitive tools (`soul_observe`, `soul_reflect`, `soul_birth`, `soul_state`) accept an optional `ctx: Context` parameter. On the first such call, `_get_or_create_engine(ctx)` constructs an `MCPSamplingEngine` that routes LLM calls back to the host (Claude Desktop, Claude Code) via MCP sampling — no separate API key needed. The engine is cached and pushed to all loaded souls and LCM contexts.

## Tool Catalog

**Core soul tools**: `soul_birth`, `soul_list`, `soul_switch`, `soul_state`, `soul_feel`, `soul_prompt`, `soul_save`, `soul_export`, `soul_reload`

**Memory tools**: `soul_remember`, `soul_recall`, `soul_observe`, `soul_reflect`, `soul_dream`

**Psychology pipeline**: `soul_skills`, `soul_evaluate`, `soul_learn`, `soul_evolve`, `soul_bond`

**Maintenance**: `soul_forget`, `soul_edit_core`, `soul_health`, `soul_cleanup`

**Lossless Context Management**: `soul_context_ingest`, `soul_context_assemble`, `soul_context_grep`, `soul_context_expand`, `soul_context_describe`

## Notable Design Patterns

- **Dry-run gates**: `soul_forget` and `soul_cleanup` default to preview mode (`confirm=False`, `dry_run=True`) to prevent accidental data loss.
- **Input validation helpers**: `_validate_memory_type()` and `_validate_mood()` reject invalid strings with actionable error messages before touching soul state.
- **`_resolve_soul()`**: Every tool calls this before operating, which both resolves the soul by name and triggers auto-reload if the file changed on disk since last access.

## Resources and Prompts

Three resources expose soul state as URI-addressable data: `soul://identity`, `soul://memory/core`, `soul://state`. Two prompts (`soul_system_prompt_template`, `soul_introduction`) return fallback strings when no soul is loaded, preventing hard failures during MCP negotiation.

## Known Gaps

- File watcher uses polling (mtime), not OS inotify/FSEvents — adds up to `SOUL_POLL_INTERVAL` latency for external changes.
- `_engine` and `_registry` are module-level globals, which means a single process can only host one MCP server instance.