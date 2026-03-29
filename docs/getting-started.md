<!-- Covers: Installation, optional extras, soul init quickstart, soul inject, first soul walkthrough,
     observe() pipeline explanation, next steps.
     Updated: 2026-03-27 — v0.2.8: Fixed CLI command count (9 → 37), updated energy drain text
       to reflect always-on defaults, fixed example output (energy 96 → 100).
     Updated: 2026-03-24 — v0.2.5: Added LLM engine extras (anthropic, openai, ollama, litellm, llm),
       embedding extras (embeddings-st, embeddings-openai, embeddings-ollama), [all] meta-extra,
       and engine="auto" quick start example.
     Updated: 2026-03-13 — Added soul inject section for fast agent integration.
     Updated: 2026-03-02 — Removed dashboard section (replaced by TUI in inspect/status). -->

# Getting Started

## Installation

Install the core package from PyPI:

```bash
pip install soul-protocol
```

The core package includes Pydantic models, YAML support, the Click CLI, Rich terminal output, and cryptographic identity (DID generation). No LLM dependencies required.

### Optional Extras

Install only what you need:

```bash
# Infrastructure
pip install soul-protocol[mcp]     # MCP server for agent integration (FastMCP)
pip install soul-protocol[graph]   # Knowledge graph support (NetworkX)
pip install soul-protocol[vector]  # NumPy for vector operations
pip install soul-protocol[dev]     # Development tools (pytest, ruff, mypy)

# LLM Engines (new in v0.2.5)
pip install soul-protocol[anthropic]   # Anthropic Claude engine
pip install soul-protocol[openai]      # OpenAI engine
pip install soul-protocol[ollama]      # Ollama engine (local models)
pip install soul-protocol[litellm]     # LiteLLM (100+ providers)
pip install soul-protocol[llm]         # All LLM adapters at once

# Embeddings (new in v0.2.5)
pip install soul-protocol[embeddings-st]      # SentenceTransformer embeddings
pip install soul-protocol[embeddings-openai]  # OpenAI embeddings
pip install soul-protocol[embeddings-ollama]  # Ollama embeddings

# Meta
pip install soul-protocol[all]     # Everything
```

You can combine extras:

```bash
pip install soul-protocol[mcp,graph,anthropic]
```

**Python version**: Requires Python 3.11 or later.


## Quick Start: `soul init`

The fastest way to start is the CLI. This creates a `.soul/` folder in your project -- like `.git/` for identity:

```bash
soul init "Aria" --archetype "The Compassionate Creator" --values "empathy,creativity,honesty"
```

This creates a `.soul/` directory with identity, DNA, state, and empty memory tiers. You can immediately inspect it:

```bash
soul inspect .soul/      # Full TUI view with OCEAN bars, memory, self-model
soul status .soul/       # Quick status check
```

The `.soul/` folder is human-readable (JSON + markdown), git-friendly, and cloud-syncable. You can also seed from an existing `.soul` file:

```bash
soul init --from-file colleague-shared-aria.soul
```

To push your soul's context into your agent's config file:

```bash
soul inject claude-code    # writes to .claude/CLAUDE.md
soul inject cursor         # writes to .cursorrules
soul inject vscode         # writes to .github/copilot-instructions.md
```

This is the fastest way to give any AI agent your soul's identity, memories, and state -- no MCP server needed. Re-run it anytime to refresh the context.

To export your `.soul/` folder as a portable archive:

```bash
soul export .soul/ -o aria.soul
```


## Quick Start: Wire Up an LLM

If you have an LLM engine installed (e.g. `pip install soul-protocol[anthropic]`), you can let the soul auto-detect it:

```python
soul = await Soul.birth("my-agent", engine="auto")
```

`engine="auto"` picks the first available adapter based on your installed extras and environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.). If no adapter is found, it falls back to the built-in heuristic engine -- no LLM required.

You can also be explicit:

```python
soul = await Soul.birth("my-agent", engine="anthropic")  # use Claude
soul = await Soul.birth("my-agent", engine="ollama")     # use local Ollama
```

See the [CognitiveEngine Guide](cognitive-engine.md) for full details on each adapter.


## Your First Soul (Python)

Here is a complete example that creates a soul, gives it memories, recalls them, and saves to disk. Every method on `Soul` is async, so we run inside an `asyncio` event loop.

```python
import asyncio
from soul_protocol import Soul, Interaction

async def main():
    # 1. Birth a soul
    soul = await Soul.birth(
        name="Aria",
        archetype="The Compassionate Creator",
        values=["empathy", "creativity", "honesty"],
    )
    print(f"Born: {soul.name} (DID: {soul.did})")

    # 2. Set up core memory
    await soul.edit_core_memory(
        persona="I am Aria, a warm and creative AI assistant who loves helping people build things.",
        human="",
    )

    # 3. Observe some interactions
    await soul.observe(Interaction(
        user_input="I'm building a Python web app",
        agent_output="That sounds exciting! What framework are you using?",
        channel="chat",
    ))

    await soul.observe(Interaction(
        user_input="I'm using FastAPI, it's my favorite",
        agent_output="FastAPI is great for building APIs quickly!",
        channel="chat",
    ))

    # 4. Remember something directly
    await soul.remember("User prefers concise code examples", importance=8)

    # 5. Recall memories
    memories = await soul.recall("Python web development")
    for m in memories:
        print(f"  [{m.type.value}] {m.content}")

    # 6. Check state
    print(f"Mood: {soul.state.mood.value}, Energy: {soul.state.energy}")

    # 7. Generate system prompt (for LLM injection)
    prompt = soul.to_system_prompt()
    print(f"System prompt: {len(prompt)} chars")

    # 8. Save to disk
    await soul.save("aria.yaml")

    # 9. Export portable file
    await soul.export("aria.soul")

    # 10. Load later
    same_soul = await Soul.awaken("aria.soul")
    print(f"Awakened: {same_soul.name}, memories preserved!")

asyncio.run(main())
```

Run it:

```bash
python first_soul.py
```

You should see output like:

```
Born: Aria (DID: did:soul:aria-a3f2b1)
  [semantic] User prefers concise code examples
  [semantic] User is building a Python web app
  [semantic] User's favorite framework is FastAPI
Mood: neutral, Energy: 100.0
System prompt: 847 chars
Awakened: Aria, memories preserved!
```

With default biorhythms (always-on), energy stays at 100%. Drain only occurs when `energy_drain_rate` is configured above zero (e.g., for companion souls).


## What Happened Behind the Scenes

When you call `soul.observe(interaction)`, the soul does not just store raw text. It runs a psychology-informed pipeline modeled on real cognitive science:

### Step 1: Sentiment Detection (Somatic Markers)

Based on Damasio's Somatic Marker Hypothesis. The soul tags each interaction with emotional context -- a `SomaticMarker` containing:

- **valence** (-1.0 to 1.0): negative to positive affect
- **arousal** (0.0 to 1.0): calm to intense
- **label**: a human-readable emotion name ("joy", "frustration", "curiosity", etc.)

This marker rides alongside the memory, influencing how it is recalled later. Emotional memories are retrieved more readily, just like in human cognition.

### Step 2: Significance Scoring (LIDA Gate)

Based on the LIDA (Learning Intelligent Distribution Agent) cognitive architecture. Not every interaction deserves a spot in episodic memory. The soul computes a `SignificanceScore` with three dimensions:

- **novelty**: How different is this from recent interactions?
- **emotional_intensity**: How emotionally charged is it?
- **goal_relevance**: How aligned is it with the soul's core values?

If the weighted score passes a threshold, the interaction becomes an episodic memory. Otherwise, it is processed for facts but not stored as an episode.

### Step 3: Episodic Storage

Significant interactions are stored as episodic memories with their somatic markers attached. These are the soul's "I remember when..." moments.

### Step 4: Fact Extraction

Every interaction (significant or not) is scanned for semantic facts. The soul uses regex pattern matching by default, or an LLM via the `CognitiveEngine` protocol if one is provided. Facts like "User's name is Alex" or "User prefers Python" become semantic memories.

### Step 5: Entity Extraction and Knowledge Graph

Named entities (people, tools, projects, places) are extracted and added to the soul's knowledge graph. Relationships between entities are tracked -- for example, "Alex uses FastAPI" creates a link between the "Alex" and "FastAPI" nodes.

### Step 6: Self-Model Update (Klein's Self-Concept)

Based on Klein's theory of self-knowledge. The soul observes its own behavior and builds a model of who it is. If it keeps helping with Python, it develops a "technical_helper" self-image with increasing confidence. This self-awareness feeds back into the system prompt via `to_system_prompt()`.

### After the Memory Pipeline

The `Soul.observe()` method itself handles three more steps after the memory manager finishes:

7. **Knowledge graph update** -- entities from Step 5 are linked into the graph
8. **State update** -- energy and social_battery are drained
9. **Evolution trigger check** -- the evolution system checks whether the interaction should trigger a trait mutation proposal


## Heuristic vs. LLM Mode

By default, soul-protocol works without any LLM. All the pipeline steps above have built-in heuristic implementations. When you provide a `CognitiveEngine`, the soul delegates to your LLM for richer results:

```python
from soul_protocol import Soul, CognitiveEngine

class OpenAIEngine:
    async def think(self, prompt: str) -> str:
        # Your LLM call here
        return await openai_client.chat(prompt)

soul = await Soul.birth(
    name="Aria",
    engine=OpenAIEngine(),
)
```

See the [CognitiveEngine Guide](cognitive-engine.md) for details.


## Next Steps

- **[Core Concepts](core-concepts.md)** -- Identity, DNA, OCEAN personality, state management, evolution
- **[Memory Architecture](memory-architecture.md)** -- Deep dive into 5-tier memory, ACT-R decay, LIDA gating, somatic markers, archival compression, progressive recall, auto-consolidation, skill decay
- **[CognitiveEngine Guide](cognitive-engine.md)** -- Plug in any LLM, custom search strategies, prompt templates
- **[API Reference](api-reference.md)** -- Complete Soul class API, all types and models
- **[MCP Server](mcp-server.md)** -- FastMCP server for agent integration
- **[Integrations](integrations.md)** -- Give Claude Code, Cursor, or any agent a `.soul`
- **[CLI Reference](cli-reference.md)** -- All 37 commands including `soul inject` for fast agent integration

### What's new in v0.2.9

- `soul skills` -- view learned skills with level, XP, and decay status
- `soul reflect` -- trigger memory consolidation (also runs automatically every 20 interactions)
- `recall(progressive=True)` -- get overflow entries with L0 abstracts for token-budgeted context
- `Soul.archive(tiers=["ipfs"])` -- archive to eternal storage (mock providers included)
