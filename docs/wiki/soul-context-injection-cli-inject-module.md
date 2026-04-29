---
{
  "title": "Soul Context Injection — CLI Inject Module",
  "summary": "Provides functions to write or replace a soul's identity, state, and recent memories into agent platform configuration files (CLAUDE.md, .cursorrules, etc.) using idempotent HTML comment markers. Supports six platforms and runs without MCP.",
  "concepts": [
    "soul inject",
    "context injection",
    "CLAUDE.md",
    "idempotency",
    "marker comments",
    "agent platform config",
    "MCP alternative",
    "CLI",
    "SOUL-CONTEXT-START",
    "episodic memory",
    "platform config files",
    "soul context block"
  ],
  "categories": [
    "cli",
    "integration",
    "memory-system"
  ],
  "source_docs": [
    "9468619e4fe3beb8"
  ],
  "backlinks": null,
  "word_count": 416,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`cli/inject.py` implements the low-level mechanics of the `soul inject` CLI command. It resolves the correct config file path for a given platform, builds a markdown context block from a live soul, and writes it into that file — replacing any prior block if one exists.

## Why It Exists

MCP-based soul recall requires a running server and a connected client. Many workflows (CI, offline development, fresh machine setup) cannot use MCP. `inject.py` provides a CLI-first alternative: it writes soul context directly into the config files that agent platforms read at startup, so the agent receives the soul's identity and recent memories without any runtime dependency on MCP.

## Supported Platforms

| Platform slug | Config file |
|--------------|-------------|
| `claude-code` | `.claude/CLAUDE.md` |
| `cursor` | `.cursorrules` |
| `vscode` | `.github/copilot-instructions.md` |
| `windsurf` | `.windsurfrules` |
| `cline` | `.clinerules` |
| `continue` | `.continuerules` |

## Idempotency via Marker Comments

The injected block is wrapped in two HTML comment markers:

```html
<!-- SOUL-CONTEXT-START -->
... soul context markdown ...
<!-- SOUL-CONTEXT-END -->
```

`inject_context_block()` searches for these markers on every call. If found, it replaces the content between them. If not found, it appends a new block. This means re-running `soul inject` after new memories accumulate is safe — it updates in place without duplicating content.

Without this guard, repeated injection would grow the config file unboundedly, eventually overwhelming the agent's context window with stale memories.

## Context Block Contents

`build_context_block()` assembles:

- **Identity**: name, archetype, DID, core values
- **State**: mood, energy percentage, lifecycle stage
- **Core memory**: persona block and human-knowledge block
- **Recent episodic memories**: up to `memory_limit` entries, each truncated at 120 characters

Each memory line is formatted as:
```
- [episodic] content here (importance: 8)
```

## Key Functions

```python
resolve_target_path(target: str, cwd: Path) -> Path
inject_context_block(file_path: Path, block: str) -> bool
find_soul(soul_dir: Path, soul_name: str) -> Path
```

`find_soul` searches a directory for a `.soul` file or `.soul/` directory matching a given name, supporting both zip-archive and directory-format souls.

## Known Gaps

- Memory truncation at 120 characters is hardcoded; there is no option to pass a custom limit per platform.
- The `soul inject` flow only includes episodic memories. Semantic and procedural memories are omitted, which may miss high-importance facts.
- The injected instructions block includes MCP tool call guidance (`soul_recall`, `soul_state`, `soul_observe`), but these tools may not be available if MCP is not configured — creating a mismatch between instructions and available tools.
