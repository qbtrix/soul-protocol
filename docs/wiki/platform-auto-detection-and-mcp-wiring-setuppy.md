---
{
  "title": "Platform Auto-Detection and MCP Wiring — `setup.py`",
  "summary": "Detects installed AI coding platforms (Claude Code, Cursor, VS Code, Windsurf, and 8 others), generates platform-appropriate MCP server config, and writes soul memory instructions into each platform's instruction file. Designed to be run once during `soul init --setup-targets`.",
  "concepts": [
    "platform setup",
    "MCP server config",
    "Claude Code",
    "Cursor",
    "VS Code",
    "agent platform integration",
    "AGENTS.md",
    "Platform dataclass",
    "is_installed",
    "soul init",
    "uvx",
    "MCP wiring",
    "gitignore",
    "multi-soul directory"
  ],
  "categories": [
    "cli",
    "integration",
    "platform-support"
  ],
  "source_docs": [
    "95770a4780150f4f"
  ],
  "backlinks": null,
  "word_count": 536,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`cli/setup.py` solves the cold-start problem: after `soul init` creates a soul, how does each AI agent platform actually know about it? The answer is a single setup pass that writes MCP JSON/TOML configs and injects soul usage instructions into every detected platform's config files.

## Supported Platforms

| Platform | Config Format | Scope |
|----------|--------------|-------|
| Claude Code | JSON (`.claude/mcp.json`) | project |
| Cursor | JSON (`.cursor/mcp.json`) | project |
| VS Code / Copilot | JSON (`.vscode/mcp.json`) | project |
| Windsurf | JSON (`.windsurf/mcp.json`) | project |
| Cline | JSON | project |
| Continue | JSON | project |
| Gemini CLI | JSON | project |
| Codex CLI | TOML | project |
| Amazon Q | JSON | project |
| Zed | JSON | global |
| Claude Desktop | JSON | global |

Additionally, a universal `AGENTS.md` file is written for platforms that support it (5+ platforms read `AGENTS.md` as shared instructions).

## `Platform` Dataclass

```python
@dataclass
class Platform:
    name: str
    slug: str
    mcp_config_paths: list[Path]
    mcp_key: str = "mcpServers"
    instruction_files: list[Path]
    detect_paths: list[Path]
    config_format: str = "json"   # or "toml"
    scope: str = "project"        # or "global"

    def is_installed(self) -> bool: ...
```

`is_installed()` checks three signals in order: explicit detection paths (binary or config dir that proves the platform is present), existing MCP config files, and existing instruction files. Any hit returns `True`.

## Key Functions

### `get_platforms(cwd)` vs `detect_platforms(cwd)`

- `get_platforms()` returns all 11 platforms regardless of installation state — used when the user wants to configure everything explicitly.
- `detect_platforms()` filters to only platforms where `is_installed()` returns `True` — used during `soul init` to auto-wire only what is actually present.

### `_mcp_server_entry(soul_path)`

Generates the standard MCP server config block:

```json
{
  "command": "uvx",
  "args": ["soul-protocol", "mcp-server", "<soul_path>"]
}
```

For multi-soul directories (detected by `_is_multi_soul()`), the `soul_path` argument is the directory rather than a single file, enabling the MCP server to serve multiple souls.

### `_write_mcp_json()` and `_write_mcp_toml()`

Both functions are idempotent: they read existing config, merge the `soul-protocol` server entry under the appropriate key, and write back. Existing entries from other MCP servers are preserved.

### `_append_instructions(file_path, header)`

Checks whether `_SOUL_MARKER` already appears in the target file before appending. This prevents duplicate instruction blocks on repeated `soul init` runs.

### `_update_gitignore(cwd)`

Adds `.soul/` to `.gitignore` if not already present, preventing accidental commits of soul archives which may contain sensitive memories.

## Soul Instructions Template

The injected `_SOUL_INSTRUCTIONS` block teaches the agent three behaviours:

1. Call `soul_recall` on session start with current task context
2. Call `soul_observe` after key decisions during work
3. Trust the auto-save on session end

This is injected into `AGENTS.md` and platform-specific instruction files.

## Known Gaps

- Global-scope platforms (Zed, Claude Desktop) write to `~/Library/Application Support/...` on macOS; on Linux the paths are hardcoded differently and may not be correct for all distributions.
- `_resolve_uvx()` resolves the absolute path to `uvx` at setup time; if the user later changes their Python environment, the MCP command path in saved configs will be stale.
- The TOML writer for Codex CLI is simpler than the JSON writer and does not handle existing config merging as robustly.
