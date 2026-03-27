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
  version: 0.2.8
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

### Runtime operations (v0.2.6)

```bash
# Process interaction through full cognitive pipeline
soul observe .soul/ --user-input "Hello" --agent-output "Hi there!" --channel discord

# Memory consolidation and reflection
soul reflect .soul/
soul reflect aria.soul --no-apply

# Update emotional state
soul feel .soul/ --mood excited --energy 5

# Generate system prompt (pipe-friendly, no Rich formatting)
soul prompt .soul/ > prompt.txt

# Delete memories (GDPR-compliant)
soul forget .soul/ "credit card"
soul forget aria.soul --entity "John Doe"

# Edit core memory
soul edit-core .soul/ --persona "I am a helpful coding assistant"
soul edit-core aria.soul --human "User prefers Python"

# Evolution system
soul evolve .soul/ --propose --trait communication.warmth --value high --reason "User prefers warmth"
soul evolve .soul/ --list
soul evolve .soul/ --approve abc123

# Evaluation and learning
soul evaluate .soul/ --user-input "Explain recursion" --agent-output "Recursion is..."
soul learn .soul/ --user-input "Fix this bug" --agent-output "Here's the fix" --domain coding

# Skills, bonds, events (v0.2.7: skills + eval history now persist across sessions)
soul skills .soul/
soul bond .soul/ --strengthen 5.0
soul events .soul/ --recent 20

# LCM context management
soul context --ingest --role user --content "Hello there"
soul context --assemble --max-tokens 4000
soul context --grep "hello"
soul context --describe
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
| Process interaction | `soul observe path --user-input X --agent-output Y` | `soul_observe(user_input, agent_output)` |
| Reflect | `soul reflect path` | `soul_reflect()` |
| Update mood/energy | `soul feel path --mood X --energy Y` | `soul_feel(mood, energy)` |
| System prompt | `soul prompt path` | `soul_prompt()` |
| Delete memories | `soul forget path "query"` | `soul_forget(query)` |
| Edit core memory | `soul edit-core path --persona X` | `soul_edit_core(persona, human)` |
| Evolution | `soul evolve path --propose ...` | `soul_evolve(action, trait, new_value, reason)` |
| Evaluate | `soul evaluate path --user-input X --agent-output Y` | `soul_evaluate(user_input, agent_output)` |
| Learn | `soul learn path --user-input X --agent-output Y` | `soul_learn(user_input, agent_output)` |
| Skills | `soul skills path` | `soul_skills()` |
| Bond | `soul bond path` | `soul_bond(strengthen)` |
| Events | `soul events path` | N/A (Python API) |
| Health audit | `soul health path` | `soul_health()` |
| Cleanup | `soul cleanup path --auto` | `soul_cleanup(auto)` |
| Repair | `soul repair path --reset-energy` | N/A (CLI only) |
| Ingest context | `soul context --ingest --role X --content Y` | `soul_context_ingest(role, content)` |
| Assemble context | `soul context --assemble --max-tokens N` | `soul_context_assemble(max_tokens)` |
| Search context | `soul context --grep PATTERN` | `soul_context_grep(pattern)` |
| Expand node | N/A | `soul_context_expand(node_id)` |
| Context metadata | `soul context --describe` | `soul_context_describe()` |

**Rule of thumb:** if the agent has Bash access, always prefer CLI. It's a direct process call — no JSON-RPC serialization, no MCP protocol overhead, no server needed.

## MCP Server (for agents without shell access)

23 tools available (13 soul/memory + 5 context + 5 psychology). Only set this up if the agent can't run shell commands.

```bash
# Start server (auto-detects .soul/ directory — no env vars needed)
soul-mcp

# Or with explicit path
SOUL_DIR=.soul soul-mcp
```

**Auto-detect:** When no `SOUL_DIR` or `SOUL_PATH` env var is set, the server looks for `.soul/` in CWD first, then falls back to `~/.soul/`. Just run `soul-mcp` in a project with a `.soul/` folder and it works.

**MCP Sampling Engine:** The server delegates cognitive tasks (sentiment, fact extraction, reflection, context compaction) to the host LLM via `ctx.sample()`. No API key needed — the host provides the model. Wired lazily on the first tool call.

### Soul tools (9)
`soul_birth`, `soul_list`, `soul_switch`, `soul_state`, `soul_feel`, `soul_save`, `soul_export`, `soul_reload`, `soul_prompt`

### Memory tools (4)
`soul_observe`, `soul_remember`, `soul_recall`, `soul_reflect`

### Context tools — LCM (5)
| Tool | Purpose |
|------|---------|
| `soul_context_ingest` | Ingest a message (role + content) into the immutable context store |
| `soul_context_assemble` | Assemble a context window within a token budget (auto-compacts) |
| `soul_context_grep` | Regex search across all context history (even compacted messages) |
| `soul_context_expand` | Expand a compacted node back to original messages (lossless recovery) |
| `soul_context_describe` | Metadata snapshot: message count, tokens, date range, compaction stats |

### Psychology tools (5)
`soul_evolve`, `soul_evaluate`, `soul_learn`, `soul_skills`, `soul_bond`

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

LCM is available via both MCP (`soul_context_*` tools) and CLI (`soul context --ingest`, `--assemble`, `--grep`, `--describe`). The CLI uses an in-memory SQLite store per invocation; the MCP server maintains a persistent per-soul context store across the session.

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
- `manifest.json` — Version, timestamps, format metadata
- `soul.json` — Identity, DNA (OCEAN personality), config
- `state.json` — Runtime state (mood, energy, lifecycle)
- `dna.md` — Human-readable personality snapshot
- `memory/core.json` — Core memory (persona + human knowledge)
- `memory/episodic.json` — Interaction history with sentiment
- `memory/semantic.json` — Extracted facts
- `memory/procedural.json` — Learned patterns
- `memory/graph.json` — Knowledge graph (entity relationships)
- `memory/self_model.json` — Self-image and reflection data
- `memory/general_events.json` — General event log

Portable across platforms. `soul inject` writes MCP config for any supported agent.

## Key Types

```python
from soul_protocol import (
    Soul, Interaction, MemoryType, MemoryEntry, Mood,
    CognitiveEngine, SearchStrategy, SoulState, DNA, Identity,
)
```
