<!-- Covers: MCP server setup, configuration for Claude Desktop/Cursor, all 10 tools with parameters,
     3 resources, 2 prompts, programmatic usage, and design notes. -->

# MCP Server

Soul Protocol includes a FastMCP-based Model Context Protocol server for agent integration. Any MCP-compatible client (Claude Desktop, Cursor, custom agents) can connect to a soul and interact with its memory, identity, and emotional state in real time.

## Installation

The MCP server requires the optional `mcp` extra:

```bash
pip install soul-protocol[mcp]
```

This pulls in `fastmcp` as a dependency. The core `soul-protocol` package has no dependency on it.

## Running

```bash
# Start with an existing soul file
SOUL_PATH=aria.soul soul-mcp

# Start empty (create a soul at runtime via the soul_birth tool)
soul-mcp
```

The server reads `SOUL_PATH` from the environment on startup. If set, it loads that soul file (`.soul`, `.json`, `.yaml`, or `.md`) before accepting connections. If not set, the server starts with no soul loaded -- clients must call `soul_birth` before using any other tool.

## Configuration

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/path/to/aria.soul"
      }
    }
  }
}
```

### Cursor / VS Code

Add to your MCP settings (`.cursor/mcp.json` or equivalent):

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/path/to/aria.soul"
      }
    }
  }
}
```

### Custom MCP Client

Any client that speaks the Model Context Protocol over stdio can connect. The server uses FastMCP's default stdio transport.

## Tools (10)

All tools are prefixed `soul_` to avoid name collisions when running alongside other MCP servers.

---

### `soul_birth`

Create a new soul with persistent identity and memory.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | The soul's name |
| `archetype` | `str` | `""` | Archetype (e.g. "The Compassionate Creator") |
| `values` | `list[str]` | `[]` | Core values for significance scoring |

**Returns:** JSON with `name`, `did`, and `status: "born"`.

---

### `soul_observe`

Process an interaction through the full psychology pipeline. Extracts facts, detects sentiment, gates episodic storage, updates the self-model.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_input` | `str` | required | What the user said |
| `agent_output` | `str` | required | What the agent responded |
| `channel` | `str` | `"mcp"` | Source channel identifier |

**Returns:** JSON with `status`, `mood`, and `energy`.

---

### `soul_remember`

Store a memory directly, bypassing the observe pipeline.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | required | The memory content |
| `importance` | `int` | `5` | Importance on a 1-10 scale |
| `memory_type` | `str` | `"semantic"` | One of: `core`, `episodic`, `semantic`, `procedural` |
| `emotion` | `str` | `None` | Optional emotion label (e.g. "joy", "frustration") |

**Returns:** JSON with `memory_id`, `type`, and `importance`.

---

### `soul_recall`

Search the soul's memories by natural language query. Results are ranked by ACT-R activation scoring (recency, frequency, emotional intensity, query relevance).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Search query |
| `limit` | `int` | `5` | Maximum number of results |

**Returns:** JSON with `count` and `memories` array. Each memory includes `id`, `type`, `content`, `importance`, and `emotion`.

---

### `soul_reflect`

Trigger a reflection and memory consolidation pass. The soul reviews recent interactions, identifies themes, summarizes patterns, and generates self-insights. Requires a `CognitiveEngine` (LLM) for full power; returns a skip status without one.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| (none) | | | |

**Returns:** JSON with `status` and either `themes`, `emotional_patterns`, `self_insight` (on success) or `reason` (on skip).

---

### `soul_state`

Get the soul's current mood, energy, focus, social battery, and lifecycle stage.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| (none) | | | |

**Returns:** JSON with `mood`, `energy`, `focus`, `social_battery`, and `lifecycle`.

---

### `soul_feel`

Update the soul's emotional state directly.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mood` | `str` | `None` | One of: `neutral`, `curious`, `focused`, `tired`, `excited`, `contemplative`, `satisfied`, `concerned` |
| `energy` | `float` | `None` | Energy **delta** (-100 to 100). Positive increases, negative decreases. Clamped to 0-100 after application. |

**Returns:** JSON with updated `mood` and `energy`.

Note: `energy` is a delta, not an absolute value. Passing `energy: -10` drains 10 points from the current level.

---

### `soul_prompt`

Generate the complete system prompt for LLM injection. Includes identity, DNA, personality traits, core memory, current state, and self-model insights.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| (none) | | | |

**Returns:** Plain text system prompt string.

---

### `soul_save`

Persist the soul to disk as a YAML config with full memory data.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | `None` | File path. Uses the last known path if omitted. |

**Returns:** JSON with `status` and `name`.

---

### `soul_export`

Export the soul as a portable `.soul` file (zip archive). Contains identity, DNA, memory tiers, state, and self-model -- everything needed to restore the soul on another machine.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Output file path (should end in `.soul`) |

**Returns:** JSON with `status`, `path`, and `name`.

---

## Resources (3)

Resources provide read-only access to soul data. MCP clients can subscribe to these URIs for live state.

| URI | Returns |
|-----|---------|
| `soul://identity` | Full identity JSON: DID, name, archetype, born date, bonded_to, core values, origin story |
| `soul://memory/core` | Core memory: `persona` (self-description) and `human` (what the soul knows about the user) |
| `soul://state` | Current state: mood, energy, focus, social battery, lifecycle stage |

## Prompts (2)

Prompts are pre-built text templates that MCP clients can request.

| Name | Purpose |
|------|---------|
| `soul_system_prompt` | Complete system prompt for LLM context injection. Combines DNA, identity, core memory, state, and self-model into a single prompt string. |
| `soul_introduction` | First-person self-introduction. Example: "I'm Aria, The Compassionate Creator. My core values are empathy, curiosity. I'm currently feeling curious with 85% energy." |

## Programmatic Usage

You can also use the MCP server from Python without running it as a subprocess:

```python
from soul_protocol.mcp import create_server

mcp = create_server()

# Use with FastMCP's test client
async with mcp.test_client() as client:
    result = await client.call_tool("soul_birth", {"name": "Aria"})
    print(result)

# Or compose with other MCP servers in a larger system
```

## Design Notes

- **One soul per server instance.** The server holds a single soul in a global variable. To manage multiple souls, run multiple server processes.
- **All tools are prefixed `soul_`.** This avoids name collisions when a client connects to several MCP servers simultaneously (e.g. soul + filesystem + database).
- **Global state -- not thread-safe.** The server uses module-level state. Do not call `soul_observe` concurrently from multiple threads. Sequential tool calls from a single MCP client are fine.
- **Stateful lifecycle.** The soul persists in memory across tool calls within a session. Call `soul_save` or `soul_export` to persist before the server shuts down.
