<!-- Covers: Platform integration guide for Soul Protocol. Claude Code (MCP + CLAUDE.md template),
     Claude Desktop, Cursor, Windsurf, custom Python agents, LangChain/LangGraph, CrewAI,
     integration tiers, portability patterns, and MCP tools reference table. -->

# Integrations

Soul Protocol integrates with any AI agent through two paths: an MCP server that gives agents active memory and evolving identity, or system prompt injection for static personality. This guide covers both approaches across every major platform.


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

### Tier 2 -- MCP Server (Active)

Run the Soul Protocol MCP server alongside your agent. The agent actively calls soul tools to recall memories, observe interactions, reflect on patterns, and evolve over time. Full bidirectional integration.

Best for: production agents, persistent companions, any platform with MCP support.


## Claude Code

Claude Code has first-class MCP support. This section walks through the full setup: create a soul, wire up the MCP server, and teach Claude Code how to use it.

### Prerequisites

```bash
pip install soul-protocol[mcp]
```

### Step 1: Create a Soul

```bash
# Birth a new soul
soul birth "MyAssistant" --archetype "The Coding Expert"

# Export to portable .soul file
soul export MyAssistant.yaml --output my-assistant.soul
```

### Step 2: Add MCP Server Config

Add the soul MCP server to `.claude/settings.local.json` in your project root:

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/absolute/path/to/my-assistant.soul"
      }
    }
  }
}
```

`SOUL_PATH` must be an absolute path. The server loads the soul on startup and keeps it in memory across tool calls.

### Step 3: Add CLAUDE.md Instructions

Create or update your project's `CLAUDE.md` to teach the agent how to use its soul. Add the template below.

### CLAUDE.md Template

Copy this block into your `CLAUDE.md`:

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

### What This Gives You

With the MCP server and CLAUDE.md instructions in place, your Claude Code agent will:

- **Remember across sessions.** Facts, preferences, and project context persist in the soul's memory tiers.
- **Maintain consistent personality.** The OCEAN model and archetype shape every response.
- **Evolve over time.** The self-model updates as the agent observes its own behavior patterns.
- **Track emotional state.** Energy drains with interaction, mood shifts with context -- creating natural conversational rhythm.


## Claude Desktop

Claude Desktop supports MCP servers natively. Add the soul server to your config file.

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/absolute/path/to/my-assistant.soul"
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

Cursor supports MCP servers through its settings. Add the soul server to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/absolute/path/to/my-assistant.soul"
      }
    }
  }
}
```

Then add instructions to `.cursorrules` so the agent knows how to use its soul:

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

Windsurf supports MCP servers in its configuration. Add the soul server to your Windsurf MCP settings:

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/absolute/path/to/my-assistant.soul"
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


## MCP Tools Reference

Quick reference for all tools, resources, and prompts exposed by the Soul Protocol MCP server. See the [MCP Server docs](mcp-server.md) for full parameter details.

### Tools (10)

| Tool | Description |
|------|-------------|
| `soul_birth` | Create a new soul with name, archetype, and values |
| `soul_observe` | Process an interaction through the full psychology pipeline |
| `soul_remember` | Store a memory directly (episodic, semantic, or procedural) |
| `soul_recall` | Search memories by natural language query, ranked by ACT-R activation |
| `soul_reflect` | Trigger reflection and memory consolidation |
| `soul_state` | Get current mood, energy, focus, social battery, lifecycle stage |
| `soul_feel` | Update mood or energy directly |
| `soul_prompt` | Generate the complete system prompt for LLM injection |
| `soul_save` | Persist the soul to disk |
| `soul_export` | Export as a portable `.soul` file |

### Resources (3)

| URI | Description |
|-----|-------------|
| `soul://identity` | Identity JSON: DID, name, archetype, born date, values, origin story |
| `soul://memory/core` | Core memory: persona description and knowledge about the user |
| `soul://state` | Current state: mood, energy, focus, social battery, lifecycle |

### Prompts (2)

| Name | Description |
|------|-------------|
| `soul_system_prompt` | Full system prompt combining DNA, identity, core memory, state, self-model |
| `soul_introduction` | First-person self-introduction for the soul |
