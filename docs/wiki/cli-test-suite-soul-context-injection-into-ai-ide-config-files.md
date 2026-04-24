---
{
  "title": "CLI Test Suite: Soul Context Injection into AI IDE Config Files",
  "summary": "Test suite for `soul inject`, which writes a soul's identity and recent memories into AI IDE configuration files (Claude Code, Cursor, VS Code, Windsurf, Cline, Continue). Covers target path resolution, idempotent section replacement, context block formatting, memory truncation, and auto-discovery of soul directories.",
  "concepts": [
    "soul inject",
    "context injection",
    "IDE integration",
    "Claude Code",
    "Cursor",
    "VS Code",
    "Windsurf",
    "Cline",
    "Continue",
    "idempotent injection",
    "marker-based replacement",
    "build_context_block",
    "find_soul",
    "memory truncation",
    "config file"
  ],
  "categories": [
    "testing",
    "CLI",
    "IDE integration",
    "soul inject",
    "test"
  ],
  "source_docs": [
    "bffaba7ab9f1bfad"
  ],
  "backlinks": null,
  "word_count": 438,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_inject.py` validates the mechanism by which Soul Protocol injects a soul's live context into the configuration files that AI coding assistants read on startup. The goal is to give tools like Claude Code or Cursor persistent awareness of a companion soul's identity, state, and recent memories -- without manual copy-paste.

## Target Path Resolution

Each supported IDE/tool maps to a specific config file path:

| Target | Config File |
|--------|-------------|
| `claude-code` | `.claude/CLAUDE.md` |
| `cursor` | `.cursorrules` |
| `vscode` | `.github/copilot-instructions.md` |
| `windsurf` | `.windsurfrules` |
| `cline` | `.clinerules` |
| `continue` | `.continuerules` |

Tests verify each mapping and also confirm that an unknown target raises `ValueError` with a message that lists all supported targets -- so users get actionable feedback rather than a cryptic error.

## Idempotent Injection

The injection system uses sentinel markers to delimit the soul context block within the config file:

```python
def test_inject_replaces_existing_section(tmp_path):
    # Running inject twice must replace the section, not append a duplicate
    inject_context_block(soul_dir, target_file)
    inject_context_block(soul_dir, target_file)
    assert target_file.read_text().count("<!-- soul:start -->") == 1
```

This idempotency guarantee is essential: users often re-run `soul inject` after a soul evolves. Without marker-based replacement, the config file would accumulate stale blocks on every run.

When a file exists but has no markers, the block is appended. Surrounding content outside the markers is always preserved -- inject is non-destructive to user-authored content.

## File and Directory Creation

- Parent directories are created automatically (e.g., `.github/` for VS Code)
- Non-existent target files are created fresh
- Nested paths work correctly (tested explicitly for VS Code's deep path)

## Context Block Formatting

`build_context_block()` generates the markdown injected into config files:

```python
async def test_format_soul_context(tmp_path):
    block = await build_context_block(soul_dir)
    assert "**Identity**" in block
    assert "**State**" in block
    assert "**Core Memory**" in block
```

The function is tested across several conditions:
- **Zero memories**: handles gracefully, no crash
- **With episodic memories**: memories appear in the output
- **Custom limit**: `memory_limit` parameter caps how many memories are included
- **Long memory truncation**: content longer than 120 characters is truncated with ellipsis

## Soul Auto-Discovery

`find_soul()` locates a soul directory without requiring an explicit path:

```python
def test_find_soul_returns_dir_with_soul_json(tmp_path):
    # Returns the dir itself when soul.json is present inside it

def test_find_soul_searches_subdirectories(tmp_path):
    # Searches recursively when the root does not directly contain soul.json
```

This supports the common workflow where `soul inject` is run from a project root and finds the soul automatically.

## Known Gaps

No TODOs or FIXMEs in source. The test suite was introduced alongside the inject feature and has been extended as new IDE targets were added.