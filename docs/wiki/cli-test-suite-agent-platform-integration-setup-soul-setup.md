---
{
  "title": "CLI Test Suite: Agent Platform Integration Setup (`soul setup`)",
  "summary": "Test suite for `soul setup`, which wires a Soul Protocol MCP server into AI coding platforms (Cursor, VS Code, Claude Code, Continue, Windsurf). Covers platform auto-detection, MCP config file writing and merging, instruction file injection, `.gitignore` updates, and `uvx` path resolution.",
  "concepts": [
    "soul setup",
    "MCP server",
    "platform detection",
    "Cursor",
    "VS Code",
    "Claude Code",
    "Continue",
    "Windsurf",
    "uvx",
    "MCP JSON",
    "MCP TOML",
    "drop-in format",
    "gitignore",
    "setup_integrations",
    "idempotency"
  ],
  "categories": [
    "testing",
    "CLI",
    "MCP integration",
    "platform setup",
    "test"
  ],
  "source_docs": [
    "75b841f174ba3e4f"
  ],
  "backlinks": null,
  "word_count": 421,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_setup.py` validates the `setup_integrations` function and its helpers, which automate the multi-step process of registering Soul Protocol's MCP server with one or more AI coding assistant platforms. Without this, users would need to manually edit JSON/TOML config files for each tool.

## Platform Detection

```python
def test_detect_platforms_empty_dir(tmp_path):
    # No known config files -> empty platform list

def test_detect_platforms_with_cursor(tmp_path):
    # .cursor/ directory present -> Cursor detected

def test_detect_platforms_with_claude_md(tmp_path):
    # .claude/CLAUDE.md present -> Claude Code detected
```

Auto-detection scans the project directory for platform-specific markers. The empty-dir case ensures no false positives when none of the markers are present.

## MCP JSON Config Writing and Merging

Two platforms (Cursor, VS Code) use JSON config files for MCP servers. Tests cover:

- **Create**: new file written with correct structure and server entry
- **Merge**: existing file updated to add the soul server without clobbering other entries
- **VS Code key variant**: VS Code uses `"servers"` as the top-level key rather than `"mcpServers"`

```python
def test_write_mcp_json_merges_existing(tmp_path):
    existing = {"mcpServers": {"other-tool": {}}}
    write_mcp_json(config_path, server_entry)
    result = json.loads(config_path.read_text())
    assert "other-tool" in result["mcpServers"]  # preserved
    assert "soul" in result["mcpServers"]         # added
```

The merge test prevents a regression where setup would overwrite a user's entire MCP config.

## MCP TOML Config (Claude Code / Continue)

TOML-based configs require append-based writing:

- `test_write_mcp_toml_creates_file`: fresh file created correctly
- `test_write_mcp_toml_appends_to_existing`: new server entry appended without disturbing existing content
- `test_write_mcp_toml_idempotent`: running setup twice does not duplicate the entry

The idempotency test is critical -- re-running `soul setup` must be safe.

## Continue Drop-in Format

```python
def test_setup_continue_dropin_format(tmp_path):
    # Continue uses drop-in format: each file = one server entry
```

Continue uses a per-server file model in a drop-in directory rather than a single merged config. The test verifies that soul setup creates the correct per-server file.

## Instruction File and .gitignore

- `test_append_instructions_*`: instruction text is appended to the platform system prompt file, with idempotency
- `test_update_gitignore_*`: `.soul` files are added to `.gitignore`, idempotently, to prevent accidental commits of soul archives

## uvx Path Resolution

```python
def test_resolve_uvx_returns_absolute_path():
    # uvx resolves to an absolute path when available on PATH

def test_resolve_uvx_fallback():
    # When uvx is not on PATH, fall back to bare 'uvx'
```

MCP server entries must reference the `uvx` executable. Absolute path resolution ensures the correct `uvx` is used in environments with multiple Python version managers. The fallback handles systems where uvx is not on PATH at setup time.

## Known Gaps

No TODOs flagged. Test was updated 2026-03-13 to add `_resolve_uvx` absolute path resolution coverage.