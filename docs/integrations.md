<!-- Covers: Platform integration guide for Soul Protocol. CLI injection (soul inject), MCP server,
     Claude Code, Claude Desktop, Cursor, Windsurf, custom Python agents, LangChain/LangGraph, CrewAI,
     integration tiers, portability patterns, MCP tools reference table, format importers, and A2A bridge.
     Updated: 2026-03-24 — Added MCP Sampling Engine (ctx.sample() for host-delegated cognition),
     A2A Bridge (Google Agent Card bidirectional conversion), and Format Importers
     (SoulSpecImporter, TavernAIImporter) for migrating characters from other platforms.
     Updated: 2026-03-13 — Added Tier 1.5 (soul inject), multi-soul SOUL_DIR, updated tool count to 12.
     Updated: 2026-03-02 — Replaced dashboard references with inspect TUI. -->

# Integrations

Soul Protocol integrates with any AI agent through three paths: CLI injection for fast static context, an MCP server for active memory and evolving identity, or system prompt generation for manual injection. This guide covers all approaches across every major platform.


## Integration Tiers

### Tier 1 -- System Prompt (Static)

Generate a system prompt from a `.soul` file and paste it into your agent's config. Zero dependencies, zero setup. The agent gets personality and core memory but cannot form new memories or evolve.

```python
from soul_protocol import Soul

soul = await Soul.awaken("my-assistant.soul")
prompt = soul.to_system_prompt()
# Paste this into your agent's system prompt field
```

Best for: quick experiments, agents that don't support MCP, read-only personality injection.

### Tier 1.5 -- CLI Injection (`soul inject`)

One command injects soul context (identity, state, core memory, recent memories) directly into your agent's config file. No server, no MCP, no manual copy-paste. Runs in ~50ms.

```bash
soul inject claude-code              # writes to .claude/CLAUDE.md
soul inject cursor --soul guardian   # specific soul into .cursorrules
soul inject vscode --memories 20     # include 20 recent memories
soul inject windsurf --dir ~/project/.soul
```

The injected block is idempotent -- re-running replaces the existing section. Supports 6 platforms: Claude Code, Cursor, VS Code/Copilot, Windsurf, Cline, Continue.

Best for: projects that want persistent context without running a server, CI/CD pipelines, scripting, teams sharing soul context via git.

See the [CLI Reference](cli-reference.md#soul-inject) for full options.

### Tier 2 -- MCP Server (Active)

Run the Soul Protocol MCP server alongside your agent. The agent actively calls soul tools to recall memories, observe interactions, reflect on patterns, and evolve over time. Full bidirectional integration. Supports multiple souls via `SOUL_DIR`.

Best for: production agents, persistent companions, any platform with MCP support.

#### MCP Sampling Engine

When the soul runs as an MCP server, cognitive tasks that normally require a separate LLM API key -- significance gating, fact extraction, entity extraction, reflection -- are delegated to the host application's LLM via `ctx.sample()`. The host (Claude Code, Claude Desktop, or any MCP-compatible client) handles the inference call, so the soul server itself needs no API key and no direct LLM dependency.

This means:
- **Zero configuration.** Install `soul-protocol[mcp]`, point `SOUL_PATH`, done. The host's model handles all reasoning.
- **Works everywhere MCP works.** Claude Code, Claude Desktop, Cursor, Windsurf -- any host that implements MCP sampling.
- **No token costs on the soul side.** Cognitive calls ride on the host's existing model context, so there is no separate billing or rate limiting to manage.

Under the hood, the MCP server wraps each cognitive task (e.g., "score the significance of this interaction" or "extract facts from this conversation") into a structured prompt and sends it through `ctx.sample()`. The host LLM returns the result, and the soul's psychology pipeline continues with that output. If the host does not support sampling, the server falls back to the `HeuristicEngine` (rule-based, no LLM needed).

```python
# No change needed in your MCP config -- sampling is automatic.
# The soul-mcp server calls ctx.sample() internally when it needs cognition.
# Your host LLM (Claude, GPT, etc.) handles the thinking.
```


## Claude Code

Claude Code has first-class MCP support. This section walks through the full setup: create a soul, wire up the MCP server, and teach Claude Code how to use it.

### Prerequisites

```bash
pip install soul-protocol[mcp]
```

### Step 1: Create a Soul

The fastest path is `soul init`, which creates a `.soul/` folder in your project (like `.git/` for identity):

```bash
soul init "MyAssistant" --archetype "The Coding Expert" --values "precision,clarity"
```

This creates a `.soul/` directory with identity, personality, state, and empty memory tiers. You can verify it works:

```bash
soul inspect .soul/     # Full TUI view with OCEAN bars, memory, self-model
soul status .soul/      # Quick status check
```

Alternatively, create a portable `.soul` file:

```bash
soul birth "MyAssistant" --archetype "The Coding Expert"
```

### Step 2: Add MCP Server Config

Add the soul MCP server to `.claude/settings.local.json` in your project root:

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/absolute/path/to/your/project/.soul"
      }
    }
  }
}
```

`SOUL_PATH` can be a `.soul/` directory or a `.soul` archive file. Must be an absolute path. The server loads the soul on startup and keeps it in memory across tool calls.

### Step 3: Inject Context (Fast Path)

The quickest way to give Claude Code soul context is the `inject` command:

```bash
soul inject claude-code
```

This writes identity, core memory, state, and recent memories directly into `.claude/CLAUDE.md`. Re-run it anytime to refresh. Done -- skip to Step 4.

### Step 3 (Alternative): Manual CLAUDE.md Instructions

If you prefer manual control, or want to combine `soul inject` with custom instructions, add this template to your `CLAUDE.md`:

```markdown
## Soul Protocol -- Persistent Identity

You have a persistent soul managed through the `soul` MCP server. Use it to maintain
continuity across sessions.

### Session Start
- Call `soul_state` to check your current mood, energy, and lifecycle stage.
- Call `soul_recall` with a broad query about the current project to load relevant context.

### During Conversation
- Before answering questions, call `soul_recall` with the topic to check for relevant
  memories or prior context.
- After each meaningful interaction, call `soul_observe` with the user's input and your
  response. This runs the full psychology pipeline -- sentiment detection, significance
  scoring, fact extraction, and self-model update.
- When the user shares important personal information, preferences, or project details,
  call `soul_remember` with the key fact and an importance score (1-10).

### Periodically
- Call `soul_reflect` every 10-15 interactions to consolidate memories, identify themes,
  and generate self-insights.
- Call `soul_save` before long breaks or at the end of a session to persist state to disk.

### Identity
- Your personality, values, and communication style come from your soul's DNA.
- Do not contradict your core identity. If unsure about your personality, call `soul_prompt`
  to regenerate your full system prompt from the soul.
- Your mood and energy affect your tone. Low energy means shorter, more focused responses.
  High energy means more enthusiastic, exploratory responses.
```

### Step 4: Inspect (Optional)

View your soul's full state in the terminal:

```bash
soul inspect .soul/
```

Shows identity, OCEAN personality bars, state (mood/energy/social battery), memory stats, core memory, self-model, and communication style. See [CLI Reference](cli-reference.md) for details.

### What This Gives You

With the MCP server and CLAUDE.md instructions in place, your Claude Code agent will:

- **Remember across sessions.** Facts, preferences, and project context persist in the soul's memory tiers.
- **Maintain consistent personality.** The OCEAN model and archetype shape every response.
- **Evolve over time.** The self-model updates as the agent observes its own behavior patterns.
- **Track emotional state.** Energy drains with interaction, mood shifts with context -- creating natural conversational rhythm.


## Claude Desktop

Claude Desktop supports MCP servers natively. First create a soul (`soul init "MyAssistant"` in any directory), then add the soul server to your config file.

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/absolute/path/to/.soul"
      }
    }
  }
}
```

Restart Claude Desktop after saving. The soul's resources appear in the UI:

- **soul://identity** -- name, archetype, DID, core values
- **soul://memory/core** -- persona description and what the soul knows about you
- **soul://state** -- current mood, energy, focus, social battery

Claude Desktop will discover all 10 soul tools automatically. Use the `soul_system_prompt` prompt template to inject the soul's full identity into conversations.


## Cursor

Cursor supports MCP servers through its settings. Run `soul init "MyAssistant"` in your project, then add the soul server to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/absolute/path/to/your/project/.soul"
      }
    }
  }
}
```

Then inject soul context (or add it manually):

```bash
# Fast path: inject automatically
soul inject cursor

# Or add manual instructions to .cursorrules:
```

```
You have a persistent soul via the `soul` MCP server.

At session start:
- Call soul_state to check mood and energy.
- Call soul_recall with the current file or task context.

During work:
- Call soul_recall before answering questions to check for prior context.
- Call soul_observe after meaningful interactions.
- Call soul_remember when the user shares preferences or important details.

Periodically:
- Call soul_reflect every 10-15 interactions.
- Call soul_save before ending a session.
```

The soul tools appear in Cursor's MCP tool list. The agent can call them inline while editing code or answering questions in chat.


## Windsurf

Windsurf supports MCP servers in its configuration. Run `soul init "MyAssistant"` in your project, then add the soul server to your Windsurf MCP settings:

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/absolute/path/to/your/project/.soul"
      }
    }
  }
}
```

Add soul usage instructions to your Windsurf rules file (`.windsurfrules` or project instructions) following the same pattern as the Cursor example above. The key calls are `soul_state` at start, `soul_recall` before answering, `soul_observe` after interactions, and `soul_save` at session end.


## Custom Python Agent

For agents you build yourself, use the SDK directly. No MCP layer needed.

```python
import asyncio
from soul_protocol import Soul, Interaction

class MyAgent:
    def __init__(self, soul: Soul):
        self.soul = soul
        self.interaction_count = 0

    async def respond(self, user_input: str) -> str:
        # 1. Recall relevant memories
        memories = await self.soul.recall(user_input, limit=3)

        # 2. Build system prompt with memory context
        system = self.soul.to_system_prompt()
        if memories:
            system += "\n\nRelevant memories:\n"
            system += "\n".join(f"- {m.content}" for m in memories)

        # 3. Generate response (plug in your LLM)
        response = await my_llm.chat(system=system, user_input=user_input)

        # 4. Observe the interaction
        await self.soul.observe(Interaction(
            user_input=user_input,
            agent_output=response,
            channel="custom",
        ))

        # 5. Periodic reflection
        self.interaction_count += 1
        if self.interaction_count % 15 == 0:
            await self.soul.reflect()

        return response

async def main():
    soul = await Soul.awaken("my-agent.soul")
    agent = MyAgent(soul)

    # Run your conversation loop
    while True:
        user_input = input("You: ")
        if user_input.lower() in ("quit", "exit"):
            break
        response = await agent.respond(user_input)
        print(f"Agent: {response}")

    # Save before exit
    await agent.soul.save("my-agent.soul")

asyncio.run(main())
```

### Auto-Save Pattern

Persist the soul periodically so you don't lose state on crashes:

```python
import asyncio

async def auto_save(soul: Soul, path: str, interval: int = 300):
    """Save the soul every `interval` seconds."""
    while True:
        await asyncio.sleep(interval)
        await soul.save(path)
```

Start it as a background task alongside your agent loop:

```python
asyncio.create_task(auto_save(soul, "my-agent.soul", interval=300))
```

### Periodic Reflection Pattern

Reflection consolidates short-term memories into long-term patterns. Schedule it after a batch of interactions:

```python
async def reflect_periodically(soul: Soul, every_n: int = 15):
    """Call reflect() every N observations."""
    count = 0
    while True:
        await asyncio.sleep(1)
        if soul.state.interaction_count > count + every_n:
            await soul.reflect()
            count = soul.state.interaction_count
```


## LangChain / LangGraph

Use Soul Protocol as a memory backend for LangChain agents. The soul replaces or augments LangChain's built-in memory with psychologically-modeled recall.

```python
from soul_protocol import Soul, Interaction
from langchain_core.callbacks import BaseCallbackHandler

class SoulMemoryCallback(BaseCallbackHandler):
    """LangChain callback that feeds interactions into a soul."""

    def __init__(self, soul: Soul):
        self.soul = soul
        self._last_input = ""

    def on_chain_start(self, serialized, inputs, **kwargs):
        if "input" in inputs:
            self._last_input = inputs["input"]

    def on_chain_end(self, outputs, **kwargs):
        if self._last_input and "output" in outputs:
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                self.soul.observe(Interaction(
                    user_input=self._last_input,
                    agent_output=outputs["output"],
                    channel="langchain",
                ))
            )
            self._last_input = ""

# Usage
soul = await Soul.awaken("my-agent.soul")
callback = SoulMemoryCallback(soul)

# Inject soul personality into the chain's system prompt
system_prompt = soul.to_system_prompt()

# Add relevant memories before each call
memories = await soul.recall("current topic", limit=5)
context = "\n".join(f"- {m.content}" for m in memories)
```

For LangGraph, hook `soul.observe()` into your graph's node callbacks. Each node that produces a response can feed it back to the soul for memory processing.


## CrewAI

Give each crew member a persistent `.soul` identity. Crew members retain their expertise, personality, and memories across runs.

```python
from crewai import Agent, Crew, Task
from soul_protocol import Soul

async def build_crew():
    # Each agent gets its own soul
    researcher_soul = await Soul.awaken("researcher.soul")
    writer_soul = await Soul.awaken("writer.soul")

    researcher = Agent(
        role="Research Analyst",
        goal="Find accurate, relevant information",
        backstory=researcher_soul.to_system_prompt(),
    )

    writer = Agent(
        role="Content Writer",
        goal="Write clear, engaging content",
        backstory=writer_soul.to_system_prompt(),
    )

    # After the crew runs, observe the results
    # to build memory for next time
    crew = Crew(agents=[researcher, writer], tasks=[...])
    result = crew.kickoff()

    await researcher_soul.observe(Interaction(
        user_input="Research task completed",
        agent_output=str(result),
        channel="crewai",
    ))
    await researcher_soul.save("researcher.soul")
    await writer_soul.save("writer.soul")
```

Each crew run builds on the last. The researcher remembers what sources worked well. The writer remembers what style the user preferred. Identity persists across crew executions.


## Portability -- The Killer Feature

The `.soul` file is a portable zip archive. Export from one platform, import on another. The soul carries everything: identity, personality, memories, emotional state, self-model.

### Export and Import

```bash
# Export from your current setup
soul export aria.soul

# Move to another machine, another platform
scp aria.soul user@other-machine:~/souls/

# The new platform picks it up -- same identity, same memories
SOUL_PATH=~/souls/aria.soul soul-mcp
```

### Fork a Soul

Create variants of a soul for different contexts:

```python
soul = await Soul.awaken("aria.soul")

# Fork for a coding-focused variant
await soul.edit_core_memory(
    persona="I am Aria, specialized in Python and systems programming.",
)
await soul.export("aria-coder.soul")

# Fork for a writing-focused variant
await soul.edit_core_memory(
    persona="I am Aria, specialized in technical writing and documentation.",
)
await soul.export("aria-writer.soul")
```

### Share Souls Between Agents

Souls are files. Share them however you share files:

- **Git:** commit `.soul` files alongside your project config
- **Cloud storage:** sync via S3, GCS, or any file host
- **Team sharing:** drop a `.soul` in a shared directory so every team member's agent starts with the same baseline identity

### Versioning and Snapshots

Export snapshots at key moments to create a version history:

```bash
soul export aria.soul --output snapshots/aria-v1.soul
# ... weeks of interaction ...
soul export aria.soul --output snapshots/aria-v2.soul
```

Roll back by loading an earlier snapshot. The soul picks up from that point with all its memories intact up to that moment.


## A2A Bridge -- Google Agent Cards

The `A2AAgentCardBridge` provides bidirectional conversion between `.soul` files and [Google A2A Agent Cards](https://google.github.io/A2A/). This lets souls participate in the A2A ecosystem and lets existing A2A agents adopt soul-based identity.

### Export a Soul to an Agent Card

```bash
soul export-a2a my-agent.soul --output agent-card.json
```

This maps soul identity (name, archetype, values, skills) to the A2A Agent Card schema. The resulting JSON can be published to any A2A-compatible registry or used directly in A2A workflows.

### Import an Agent Card as a Soul

```bash
soul import-a2a agent-card.json --output my-agent.soul
```

This reads an A2A Agent Card and creates a `.soul` file with the agent's name, description, capabilities, and skills mapped to soul DNA. The imported soul starts with empty memory tiers, ready to begin forming its own experiences.

### Python API

```python
from soul_protocol.bridges import A2AAgentCardBridge

# Soul → Agent Card
bridge = A2AAgentCardBridge()
agent_card = bridge.to_agent_card(soul)

# Agent Card → Soul
soul = bridge.from_agent_card(agent_card_dict)
```

The bridge preserves as much identity information as both formats support. Fields that exist in one format but not the other (e.g., soul's OCEAN personality, A2A's endpoint URLs) are stored in metadata so round-tripping doesn't lose data.


## Format Importers -- Migrating From Other Platforms

Soul Protocol can import characters from other persona formats, so you don't have to start from scratch when migrating to `.soul`.

### SoulSpecImporter -- SOUL.md / soul.json

Import persona files written in the SOUL.md or soul.json conventions (common in prompt engineering and agent frameworks):

```bash
soul import soul-spec persona.md --output my-agent.soul
soul import soul-spec config/soul.json --output my-agent.soul
```

```python
from soul_protocol.importers import SoulSpecImporter

importer = SoulSpecImporter()
soul = importer.from_file("persona.md")
```

The importer parses name, personality traits, backstory, values, and instructions from the source file and maps them to soul DNA fields. Markdown headers, YAML frontmatter, and JSON structures are all supported.

### TavernAIImporter -- Character Card V2

Import characters from TavernAI / SillyTavern Character Card V2 format, including both standalone JSON files and PNG files with embedded character data in the tEXt chunk:

```bash
soul import tavern character.json --output my-agent.soul
soul import tavern character.png --output my-agent.soul
```

```python
from soul_protocol.importers import TavernAIImporter

importer = TavernAIImporter()

# From JSON
soul = importer.from_file("character.json")

# From PNG with embedded tEXt chunk (no Pillow dependency)
soul = importer.from_file("character.png")
```

The importer maps Character Card V2 fields -- `name`, `description`, `personality`, `scenario`, `first_mes`, `mes_example`, `creator_notes` -- to soul identity and core memory. PNG parsing uses only the standard library (zlib + struct), so there is no Pillow or image processing dependency.

### Supported Formats

| Format | File Types | Importer | CLI Command |
|--------|-----------|----------|-------------|
| SOUL.md / soul.json | `.md`, `.json` | `SoulSpecImporter` | `soul import soul-spec <file>` |
| TavernAI Character Card V2 | `.json`, `.png` | `TavernAIImporter` | `soul import tavern <file>` |
| A2A Agent Card | `.json` | `A2AAgentCardBridge` | `soul import-a2a <file>` |


## MCP Tools Reference

Quick reference for all tools, resources, and prompts exposed by the Soul Protocol MCP server. See the [MCP Server docs](mcp-server.md) for full parameter details.

### Tools (12)

| Tool | Description |
|------|-------------|
| `soul_birth` | Create a new soul with name, archetype, and values |
| `soul_list` | List all loaded souls with name, DID, memory count, and active status |
| `soul_switch` | Set the active soul by name (case-insensitive) |
| `soul_observe` | Process an interaction through the full psychology pipeline |
| `soul_remember` | Store a memory directly (episodic, semantic, or procedural) |
| `soul_recall` | Search memories by natural language query, ranked by ACT-R activation |
| `soul_reflect` | Trigger reflection and memory consolidation |
| `soul_state` | Get current mood, energy, focus, social battery, lifecycle stage |
| `soul_feel` | Update mood or energy directly |
| `soul_prompt` | Generate the complete system prompt for LLM injection |
| `soul_save` | Persist the soul to disk |
| `soul_export` | Export as a portable `.soul` file |

All tools (except `soul_list` and `soul_switch`) accept an optional `soul` parameter to target a specific soul by name. If omitted, the active soul is used.

### Resources (3)

| URI | Description |
|-----|-------------|
| `soul://identity` | Identity JSON: DID, name, archetype, born date, values, origin story |
| `soul://memory/core` | Core memory: persona description and knowledge about the user |
| `soul://state` | Current state: mood, energy, focus, social battery, lifecycle |

### Prompts (2)

| Name | Description |
|------|-------------|
| `soul_system_prompt_template` | Full system prompt combining DNA, identity, core memory, state, self-model |
| `soul_introduction` | First-person self-introduction for the soul |
