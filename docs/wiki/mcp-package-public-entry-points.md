---
{
  "title": "MCP Package Public Entry Points",
  "summary": "Thin package init that re-exports `create_server` and `run_server` from the MCP server module, providing a stable public surface for consumers who integrate soul-protocol's FastMCP server. Keeps the import path short (`from soul_protocol.mcp import create_server`) regardless of internal module organization.",
  "concepts": [
    "MCP",
    "FastMCP",
    "create_server",
    "run_server",
    "entry point",
    "console script",
    "soul-mcp",
    "optional dependency",
    "package init",
    "API surface"
  ],
  "categories": [
    "mcp",
    "integration",
    "server",
    "api"
  ],
  "source_docs": [
    "292cdc9faf9077bf"
  ],
  "backlinks": null,
  "word_count": 372,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`soul_protocol.mcp` is the namespace that external consumers import when wiring up the FastMCP server. This `__init__.py` exists primarily as an API stability layer: by re-exporting the two public entry points here, the internal implementation can be reorganized without changing the public import path.

## Exported API

```python
from soul_protocol.mcp.server import create_server, run_server

__all__ = ["create_server", "run_server"]
```

- **`create_server()`** — Constructs and returns the configured `FastMCP` instance. Useful for programmatic embedding: a host application that wants to mount the soul MCP tools alongside its own tools can call `create_server()` and compose the result.
- **`run_server()`** — Entry point for the `soul-mcp` console script. Calls `mcp.run()` which starts the FastMCP event loop. This is the typical production invocation: `soul-mcp` in a shell, or as an MCP server declared in a host application's MCP configuration.

## Design Rationale

Keeping the `__init__.py` minimal has several benefits:

1. **Import cost**: Importing `soul_protocol.mcp` does not drag in all of FastMCP, asyncio infrastructure, or soul runtime types unless the caller actually instantiates a server. FastMCP itself is an optional dependency (`pip install soul-protocol[mcp]`), so import failures surface only when the server is actually constructed.
2. **Testability**: Unit tests can import from `soul_protocol.mcp.server` directly to access internal helpers without going through the public surface.
3. **Composability**: A downstream package that wraps soul-protocol can re-export `create_server` under its own namespace without coupling to `server.py`'s internal structure.

## Integration Pattern

For standard MCP server usage:

```python
# In shell or process manager
# SOUL_DIR=.soul/ soul-mcp
```

For programmatic use:

```python
from soul_protocol.mcp import create_server

mcp = create_server()
mcp.run()
```

Both paths ultimately invoke the same `FastMCP` instance defined in `server.py`, with the lifespan hook handling soul loading, auto-save, and the background file watcher.

## Data Flow

```
console script (soul-mcp)
  -> run_server()
    -> mcp.run()  [FastMCP event loop]
      -> _lifespan() on startup
        -> load souls from SOUL_DIR / SOUL_PATH
        -> start file watcher
      -> serve tool/resource/prompt requests
      -> _lifespan() on shutdown
        -> auto-save modified souls
        -> close LCM contexts
```

## Known Gaps

No known gaps in the init module itself. The optional dependency on `fastmcp` means importing from `soul_protocol.mcp.server` will raise `ImportError` if the `[mcp]` extra is not installed — this is by design (optional feature, explicit install required).