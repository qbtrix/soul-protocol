---
{
  "title": "Soul Agent: Claude Agent SDK + Soul Protocol with 15 MCP Tools",
  "summary": "Implements a full-featured conversational agent that combines the Claude Agent SDK's tool execution and streaming loop with Soul Protocol's v0.2.3 feature set, exposing 15 MCP tools covering memory, personality, emotion, bond tracking, skills, GDPR deletion, evolution proposals, core memory editing, reincarnation, and encrypted export. The module-level `_soul` singleton pattern mirrors the MCP server architecture for consistency.",
  "concepts": [
    "Claude Agent SDK",
    "MCP tools",
    "soul singleton",
    "soul_recall",
    "soul_remember",
    "soul_forget",
    "soul_observe",
    "soul_feel",
    "soul_evolve",
    "GDPR deletion",
    "reincarnation",
    "encrypted export",
    "bond tracking",
    "skill registry",
    "tool schema"
  ],
  "categories": [
    "integration",
    "MCP",
    "agent",
    "soul-protocol"
  ],
  "source_docs": [
    "6cd22f6bc51f4c65"
  ],
  "backlinks": null,
  "word_count": 600,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`soul_agent.py` is the most comprehensive Soul Protocol integration example, designed to demonstrate the entire v0.2.3 API surface through a real agent. Where `real_agent.py` shows the lifecycle, `soul_agent.py` shows every available operation exposed as MCP (Model Context Protocol) tools — making the soul's capabilities directly callable by the Claude Agent SDK's tool execution loop.

## Architecture: Claude Agent SDK + MCP Tools

The file bridges two systems:
- **Claude Agent SDK**: provides the agent loop, streaming, tool dispatch, and session management
- **Soul Protocol**: provides persistent identity, memory, personality, and emotional state

MCP tools act as the interface layer. The agent's LLM decides which soul operations to invoke based on conversation context, and the SDK handles the tool call / result injection cycle.

## Module-Level Soul Singleton

```python
_soul: Soul | None = None

async def _get_soul() -> Soul:
    if _soul is None:
        raise RuntimeError("No soul loaded.")
    return _soul
```

This pattern is intentionally identical to `mcp/server.py`. Using a module-level singleton avoids passing the soul through every tool call's context. The `RuntimeError` guard prevents silent failures where a tool is called before the soul has been loaded — a defensive pattern against initialization ordering bugs.

## The 15 MCP Tools

Tools are organized into functional groups:

**Memory (4 tools)**
- `soul_recall` — BM25 search with type filter and minimum importance threshold
- `soul_remember` — explicit storage with type, importance, emotion, and entity tags
- `soul_forget` — GDPR-compliant deletion by memory ID
- `soul_memory_list` — paginated memory listing

**Observation and State (2 tools)**
- `soul_observe` — feed a raw interaction through the full extraction pipeline
- `soul_state` — get current mood, energy, and social battery

**Identity and Personality (3 tools)**
- `soul_status` — full identity summary (DID, archetype, values, bond strength)
- `soul_feel` — inject an explicit emotion to shift mood
- `soul_core_memory_edit` — update the soul's core persistent memory

**Growth and Evolution (3 tools)**
- `soul_reflect` — trigger self-reflection to consolidate memories
- `soul_evolve` — propose and apply a personality evolution step
- `soul_skill_update` — add or level-up a learned skill

**Lifecycle (3 tools)**
- `soul_save` — persist to disk
- `soul_export` — export as encrypted `.soul` archive
- `soul_reincarnate` — reset the soul's state while preserving DNA

## Tool Schema Design

Each tool uses explicit JSON Schema for its parameters:

```python
@tool(
    "soul_recall",
    "Search the soul's memories by natural language query.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
            "memory_type": {"type": "string", "enum": ["episodic", "semantic", "procedural"]},
            "min_importance": {"type": "integer"},
        },
        "required": ["query"],
    },
)
```

The `enum` constraint on `memory_type` prevents the LLM from passing invalid type strings, avoiding runtime validation errors. Making `query` the only required field lets the LLM do simple recalls without specifying every parameter.

## Startup Flow

The `main()` function parses `--name`, `--soul`, `--archetype`, `--values`, and `--password` flags. If `--soul` is provided, the soul is awakened from a file (with optional decryption password). Otherwise, a new soul is born. The tool registry (`ALL_TOOLS`, `TOOL_NAMES`) is assembled and passed to the Claude SDK client configuration.

## Known Gaps

- The soul singleton is not thread-safe. If the SDK spawned multiple tool calls in parallel (possible with parallel tool use), concurrent writes to the soul's memory store could race. A mutex or async lock around mutation operations is absent.
- The `soul_reincarnate` tool description is not shown in the extracted snippet — it's unclear what safety guardrails (confirmation prompt, data export first) exist before state is wiped.
- No reconnection logic if the soul file on disk is modified externally between tool calls — the in-memory state would silently diverge from the file.