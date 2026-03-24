---
name: soul-protocol
description: >
  Give AI agents persistent identity, memory, and personality using Soul Protocol.
  Use when building agents that need to remember across sessions, maintain consistent
  behavior, evolve over time, or migrate between platforms. CLI-first — use shell
  commands for speed, MCP tools as fallback for agents without shell access.
  Keywords: memory, identity, personality, persistent, remember, recall, soul,
  companion, MCP, context, lossless, OCEAN, Big Five, observe, reflect.
license: MIT
compatibility: "Python 3.11+. CLI requires soul-protocol[engine]. MCP server requires soul-protocol[mcp]."
metadata:
  author: OCEAN Foundation
  version: 0.2.5
  repository: https://github.com/qbtrix/soul-protocol
  pypi: https://pypi.org/project/soul-protocol/
---

# Soul Protocol — Persistent AI Identity and Memory

Give your agent a soul — persistent memory, personality, and identity that survive across sessions and platforms. Souls are portable `.soul` files that work with any LLM.

**Two integration paths:**
- **CLI (fast)** — use `soul` commands via Bash. Direct execution, no server overhead. Best for coding agents (Claude Code, Cursor, Copilot).
- **MCP (universal)** — use MCP tools via `soul-mcp` server. Works for agents without shell access (Claude Desktop, web agents).

Use CLI when you have Bash. Use MCP when you don't.

## Install

```bash
pip install soul-protocol[engine]    # CLI + core (recommended)
pip install soul-protocol[mcp]       # + MCP server
pip install soul-protocol[all]       # Everything
```

## CLI Reference (preferred — faster than MCP)

### Create and manage souls

```bash
# Birth a new soul
soul birth "Aria" --archetype "The Compassionate Creator"

# Initialize a soul in the current directory (creates .soul/ folder)
soul init --format zip

# Inspect a soul (rich TUI: OCEAN bars, memories, state)
soul inspect .soul/aria.soul

# Quick status check (mood, energy, memory count)
soul status .soul/aria.soul

# List all local souls
soul list
```

### Memory operations

```bash
# Store a memory (fast — direct write, no server round-trip)
soul remember .soul/aria.soul "User prefers concise answers" --importance 8
soul remember .soul/aria.soul "User is a senior Python developer" --importance 9
soul remember .soul/aria.soul "Had a productive session" --emotion happy

# Recall memories by query
soul recall .soul/aria.soul "user preferences"
soul recall .soul/aria.soul "python" --limit 5 --min-importance 7

# Show recent memories
soul recall .soul/aria.soul --recent 10
```

### Export and portability

```bash
# Export to portable .soul file (ZIP archive)
soul export aria.yaml --output aria.soul

# Unpack to browse contents
soul unpack aria.soul --output aria-unpacked/

# Cross-format: SoulSpec, TavernAI, A2A Agent Card
soul export-soulspec aria.soul --output aria-soulspec/
soul export-tavernai aria.soul --output aria.png
soul export-a2a aria.soul --output aria-agent-card.json
```

### Agent configuration

```bash
# Auto-configure MCP for your agent
soul inject --target claude-code     # Claude Code (.mcp.json)
soul inject --target claude-desktop  # Claude Desktop
soul inject --target cursor          # Cursor
soul inject --target vscode          # VS Code
soul inject --target windsurf        # Windsurf
soul inject --target cline           # Cline
```

## Session Workflow (CLI)

### On session start
```bash
# Load relevant memories for the current task
soul recall .soul/myagent.soul "current project context" --limit 5

# Check mood and energy
soul status .soul/myagent.soul
```

### During work
```bash
# Store important facts as you learn them
soul remember .soul/myagent.soul "Switched to FSL license for PocketPaw" --importance 9
soul remember .soul/myagent.soul "NexWrk demo scheduled for next week" --importance 8

# Recall when you need context
soul recall .soul/myagent.soul "licensing decisions"
```

### On session end
```bash
# Export updated soul (optional — MCP server auto-saves)
soul export .soul/myagent.soul --output .soul/myagent.soul
```

## CLI vs MCP — Quick Mapping

| Task | CLI (fast, use when you have Bash) | MCP (universal, use without shell) |
|------|-------|-----|
| Store a memory | `soul remember path "text" -i 8` | `soul_remember(content, importance)` |
| Search memories | `soul recall path "query" -n 5` | `soul_recall(query, limit)` |
| Check status | `soul status path` | `soul_state()` |
| Create soul | `soul birth "Name"` | `soul_birth(name)` |
| Inspect soul | `soul inspect path` | `soul_prompt()` + `soul_state()` |
| Export | `soul export path -o out.soul` | `soul_export(path)` |
| List souls | `soul list` | `soul_list()` |
| Configure agent | `soul inject --target X` | N/A (manual config) |

**Rule of thumb:** if the agent has Bash access, always prefer CLI. It's a direct process call — no JSON-RPC serialization, no MCP protocol overhead, no server needed.

## MCP Server (for agents without shell access)

18 tools available. Only set this up if the agent can't run shell commands.

```bash
# Start server (auto-detects .soul/ directory)
soul-mcp

# Or with explicit path
SOUL_DIR=.soul soul-mcp
```

### Soul tools (9)
`soul_birth`, `soul_list`, `soul_switch`, `soul_state`, `soul_feel`, `soul_save`, `soul_export`, `soul_reload`, `soul_prompt`

### Memory tools (4)
`soul_observe`, `soul_remember`, `soul_recall`, `soul_reflect`

### Context tools — LCM (5)
`soul_context_ingest`, `soul_context_assemble`, `soul_context_grep`, `soul_context_expand`, `soul_context_describe`

### Resources (3)
`soul://identity`, `soul://memory/core`, `soul://state`

### MCP config
```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": { "SOUL_DIR": ".soul" }
    }
  }
}
```

Or just run `soul inject --target claude-code` to auto-configure.

## CognitiveEngine

### Via MCP (automatic)
When running as MCP server, the soul uses the **host LLM** (Claude, GPT, etc.) for cognitive tasks via MCP sampling. No API keys needed. Powers: sentiment analysis, fact extraction, entity extraction, significance scoring, reflection, context compaction.

### Via Python (manual)
One method: `async def think(self, prompt: str) -> str`

```python
from anthropic import AsyncAnthropic
from soul_protocol import Soul

class ClaudeEngine:
    def __init__(self):
        self.client = AsyncAnthropic()

    async def think(self, prompt: str) -> str:
        r = await self.client.messages.create(
            model="claude-sonnet-4-5-20250514", max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.content[0].text

soul = await Soul.birth("Aria", engine=ClaudeEngine())
```

### Without any LLM
Works offline with heuristic fallback — pattern matching for sentiment, rule-based fact extraction. Less accurate but zero dependencies.

## Memory Architecture

| Tier | Purpose | CLI access |
|------|---------|-----------|
| **Core** | Persona + human knowledge | `soul inspect` |
| **Episodic** | Interaction history with sentiment | `soul recall` |
| **Semantic** | Extracted facts | `soul recall` |
| **Procedural** | Learned patterns | `soul recall` |
| **Knowledge Graph** | Entity relationships | Python API |

## Lossless Context Management (LCM)

Soul = cross-session memory (who you are). LCM = within-session context (what was said).

Messages go into an immutable SQLite store. Three-level compaction when the window fills:
1. **Summary** — LLM prose summary (uses CognitiveEngine)
2. **Bullets** — LLM bullet points (more compact)
3. **Truncation** — Deterministic (guaranteed convergence, no LLM)

After compaction, `grep` still searches originals and `expand` recovers them. Nothing is lost.

LCM is currently MCP-only (no CLI commands yet). Use `soul_context_ingest`, `soul_context_assemble`, `soul_context_grep`, `soul_context_expand`, `soul_context_describe`.

## Python API (for building on top)

```python
from soul_protocol import Soul, Interaction

soul = await Soul.awaken(".soul/aria.soul")

# Observe (full cognitive pipeline: sentiment → significance → facts → entities)
await soul.observe(Interaction(
    user_input="I'm learning Rust",
    agent_output="Great choice for systems work!",
    channel="chat",
))

# Recall
memories = await soul.recall("programming", limit=5)

# System prompt (personality + core memory + mood + recalled context)
prompt = soul.to_system_prompt()

# Direct memory storage
await soul.remember("User prefers TypeScript", importance=8)

# Reflect (consolidate recent episodes into themes)
result = await soul.reflect()

# Export
await soul.export("aria.soul")
```

## .soul File Format

A `.soul` file is a ZIP archive containing:
- `soul.json` — Identity, DNA (OCEAN personality), state
- `memory.json` — All memory tiers
- `graph.json` — Knowledge graph (if present)
- `metadata.json` — Version, timestamps

Portable across platforms. `soul inject` writes MCP config for any supported agent.

## Key Types

```python
from soul_protocol import (
    Soul, Interaction, MemoryType, MemoryEntry, Mood,
    CognitiveEngine, SearchStrategy, SoulState, DNA, Identity,
)
```
