---
name: soul-protocol
description: >
  Give AI agents persistent identity, memory, and personality using Soul Protocol.
  Use when building agents that need to remember across sessions, maintain consistent
  behavior, evolve over time, or migrate between platforms. Covers soul creation,
  memory management, MCP server setup (18 tools), lossless context management,
  cognitive engine wiring, CLI commands, and cross-platform identity.
  Keywords: memory, identity, personality, persistent, remember, recall, soul,
  companion, MCP server, context window, lossless, OCEAN, Big Five, observe, reflect.
license: MIT
compatibility: "Python 3.11+. MCP server requires soul-protocol[mcp]. No external API keys needed — uses host LLM via MCP sampling."
metadata:
  author: OCEAN Foundation
  version: 0.2.5
  repository: https://github.com/qbtrix/soul-protocol
  pypi: https://pypi.org/project/soul-protocol/
---

# Soul Protocol — Persistent AI Identity and Memory

Give your agent a soul — persistent memory, personality, and identity that survive across sessions and platforms. Souls are portable `.soul` files that work with any LLM.

## Install

```bash
pip install soul-protocol          # Core (zero heavy deps)
pip install soul-protocol[mcp]     # + MCP server (recommended for agents)
pip install soul-protocol[all]     # Everything (MCP + vector + graph + CLI)
```

## Setup MCP Server

The fastest way to wire a soul into any agent. Auto-detects `.soul/` directory — zero config needed.

```bash
# Create a soul and configure MCP for your agent in one step
soul init --setup-targets claude-code
```

Or add to your MCP config manually:

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

## Quick Start (Python API)

```python
from soul_protocol import Soul, Interaction

# 1. Birth a soul
soul = await Soul.birth(
    name="Aria",
    archetype="The Compassionate Creator",
    values=["empathy", "creativity", "honesty"],
)

# 2. Observe interactions (feeds the full cognitive pipeline)
await soul.observe(Interaction(
    user_input="I've been learning Rust lately",
    agent_output="Nice — Rust is solid for systems work.",
    channel="chat",
))

# 3. Recall memories by query
memories = await soul.recall("programming", limit=5)

# 4. Generate system prompt (personality + memories + mood)
prompt = soul.to_system_prompt()

# 5. Export portable .soul file
await soul.export("aria.soul")
```

## MCP Tools (18)

### Soul Management
| Tool | What it does |
|------|-------------|
| `soul_birth` | Create a new soul with name, archetype, and values |
| `soul_list` | List all loaded souls |
| `soul_switch` | Switch active soul (multi-soul support) |
| `soul_state` | Get current mood, energy, focus, social battery |
| `soul_feel` | Update emotional state |
| `soul_save` | Save soul to disk |
| `soul_export` | Export to portable `.soul` file |
| `soul_reload` | Reload from disk (picks up external changes) |
| `soul_prompt` | Generate complete system prompt for LLM injection |

### Memory
| Tool | What it does |
|------|-------------|
| `soul_observe` | Process interaction through the full cognitive pipeline |
| `soul_remember` | Store a fact directly (with importance score) |
| `soul_recall` | Search memories by query |
| `soul_reflect` | Consolidate recent memories into themes and insights |

### Lossless Context Management (LCM)
| Tool | What it does |
|------|-------------|
| `soul_context_ingest` | Store a message in the immutable context store |
| `soul_context_assemble` | Build token-budgeted context window with auto-compaction |
| `soul_context_grep` | Regex search across full conversation history |
| `soul_context_expand` | Recover originals from any compacted node |
| `soul_context_describe` | Metadata snapshot — counts, tokens, compaction stats |

### Resources
- `soul://identity` — DID, name, archetype, values
- `soul://memory/core` — Persona and human knowledge
- `soul://state` — Mood, energy, focus

## Session Workflow

**Start:** `soul_recall` relevant memories + `soul_state` to check mood/energy.

**During work:** `soul_observe` after significant interactions. `soul_remember` for facts worth keeping. `soul_context_ingest` for within-session recall.

**End:** Auto-saves on shutdown. No manual save needed.

## CognitiveEngine — Zero Config via MCP

When running as an MCP server, the soul uses the **host LLM** for all cognitive tasks via MCP sampling. No API keys needed — the soul piggybacks on whatever brain is running the session.

This powers: sentiment analysis, significance scoring (LIDA-based), fact extraction, entity extraction, self-model evolution, memory reflection, and context compaction.

### Custom Engine (standalone Python)

One method: `async def think(self, prompt: str) -> str`

```python
from anthropic import AsyncAnthropic

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

Works with any LLM: Claude, OpenAI, Ollama, local models.

## Memory Architecture

| Tier | Purpose | Recalled by |
|------|---------|------------|
| **Core** | Persona + human knowledge | Always in system prompt |
| **Episodic** | Interaction history with sentiment | Query similarity |
| **Semantic** | Extracted facts | Query similarity |
| **Procedural** | Learned patterns | Query similarity |
| **Knowledge Graph** | Entity relationships | Entity traversal |

## Lossless Context Management

Soul = cross-session memory (who you are). LCM = within-session context (what was said).

Messages go into an immutable SQLite store. Three-level compaction when the window fills:
1. **Summary** — LLM prose summary of old messages
2. **Bullets** — LLM bullet points (more compact)
3. **Truncation** — Deterministic (guaranteed convergence, no LLM)

After compaction, `grep` still searches originals and `expand` recovers them. Nothing is lost.

## Common Patterns

### Stateful Chat Agent
```python
soul = await Soul.awaken("aria.soul")

async def handle(user_msg: str) -> str:
    response = await llm_call(system=soul.to_system_prompt(), message=user_msg)
    await soul.observe(Interaction(user_input=user_msg, agent_output=response))
    await soul.save()
    return response
```

### Teach the Soul
```python
await soul.remember("User prefers concise answers", importance=8)
await soul.remember("User is a senior Python developer", importance=9)
```

### Cross-Platform Migration
```python
await soul.export("aria.soul")                # Export from platform A
soul = await Soul.awaken("aria.soul")         # Import on platform B
```

## CLI

```bash
soul birth "Aria" --archetype "The Compassionate Creator"
soul init --format zip --setup-targets claude-code
soul inspect aria.soul
soul status aria.soul
soul remember aria.soul "Loves hiking" --importance 7
soul recall aria.soul "hobbies"
soul export aria.yaml --output aria.soul
soul inject --target claude-code              # Configure MCP
soul list
```

## Key Types

```python
from soul_protocol import (
    Soul, Interaction, MemoryType, MemoryEntry, Mood,
    CognitiveEngine, SearchStrategy, SoulState, DNA, Identity,
)
```
