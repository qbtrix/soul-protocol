---
{
  "title": "Test Suite for MCP Server Core Tools (Birth, Observe, Memory, State, Lifecycle)",
  "summary": "Integration tests for the core soul_protocol MCP server tools, covering soul lifecycle (birth, save, export), memory operations (remember, recall), emotional state (feel), observation, reflection, and multi-soul management (list, switch). Uses a registry reset helper and in-process FastMCP client to achieve full isolation between tests.",
  "concepts": [
    "MCP server",
    "soul_birth",
    "soul_observe",
    "soul_remember",
    "soul_recall",
    "soul_feel",
    "soul_reflect",
    "soul_state",
    "soul_save",
    "soul_export",
    "soul_list",
    "soul_switch",
    "registry isolation",
    "FastMCP",
    "lifespan auto-detect"
  ],
  "categories": [
    "testing",
    "MCP",
    "soul lifecycle",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "5a226c56277e3741"
  ],
  "backlinks": null,
  "word_count": 526,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_server.py` is the primary integration test file for `soul_protocol.mcp.server`. It verifies every core MCP tool call works correctly end-to-end — from tool registration through argument validation to soul state mutation and retrieval. The tests are designed to run in isolation without touching real `.soul/` directories on disk.

## Registry Isolation (_reset_registry)

The `_reset_registry` fixture is the most important setup element in this file. It:
1. Resets the in-memory soul registry to empty
2. Uses `monkeypatch` to override `os.getcwd()` to `tmp_path` — preventing the server from auto-discovering real `.soul/` directories during test startup
3. Clears any environment variables that influence soul directory resolution

Without this reset, tests would bleed state into each other through the module-level registry, causing hard-to-diagnose ordering-dependent failures.

## Auto-Detection of .soul/ Directory (TestAutoDetectSoulDir)

The MCP server lifespan auto-detects soul files by looking in:
1. `.soul/` under `CWD`
2. `~/.soul/` as a fallback

These tests use `monkeypatch` to simulate both scenarios and verify the correct directory is selected. This prevents the server from silently using the wrong soul data if the working directory changes between invocations.

## Core Tool Tests

### Birth and Minimal Birth
```python
async def test_soul_birth():       # full birth with personality params
async def test_soul_birth_minimal(): # birth with only required fields
```
Two birth tests verify both the rich (with OCEAN traits, backstory) and minimal (name-only) creation paths. Birth must add the soul to the registry.

### Observe
`test_soul_observe` verifies that processing an interaction turn (`user_input` + `agent_output`) does not raise and returns a structured response — the core ingestion pipeline.

### Remember and Recall
- `test_soul_remember_and_recall` — round-trip: store a fact, retrieve it by query
- `test_soul_remember_with_emotion` — emotions can be attached to memories
- **Validation guards:**
  - `test_soul_remember_rejects_core_type` — `core` memory type cannot be added via the tool (reserved for system use)
  - `test_soul_remember_rejects_invalid_type` — unknown memory types are rejected
  - `test_soul_remember_clamps_importance` — importance values outside [1–10] are clamped, not rejected, preventing hard failures from off-by-one inputs
- `test_soul_recall_empty` — querying a fresh soul returns an empty list without error

### Emotional State (feel)
- `test_soul_feel` / `test_soul_feel_partial` — setting mood and energy; partial updates must not wipe unspecified fields
- `test_soul_feel_rejects_invalid_mood` — unknown mood values are rejected with a structured error
- `test_soul_feel_clamps_energy` — energy values outside [0–1] are clamped

### Reflect, State, Prompt
- `test_soul_reflect` — triggers the reflection/consolidation cycle
- `test_soul_state` — returns the full soul state snapshot
- `test_soul_prompt` — generates the system prompt string from the current soul state

### Lifecycle: Save and Export
- `test_soul_save` — persists soul to disk; file must exist after the call
- `test_soul_export` — exports soul data in a portable format

### Multi-Soul Management
- `test_soul_list_empty` / `test_soul_list_after_births` — list grows after each birth
- `test_soul_switch` / `test_soul_switch_invalid_name` — switching active soul; invalid name raises structured error
- `test_soul_tool_with_name_param` — a specific soul can be targeted by name without switching the active soul, enabling multi-soul workflows

## Known Gaps

No TODOs flagged. The `_env_context` helper sets/unsets env vars with cleanup, but there is no test verifying behavior when both `SOUL_DIR` env var and a CWD `.soul/` directory are present simultaneously — the precedence rule is untested.