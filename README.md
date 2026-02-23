<!-- README.md — Full rewrite for v0.2.2 release. Replaced the original 32-line stub
     with a comprehensive project README covering architecture, API, CLI, integration
     patterns, and roadmap. ~300 lines. -->

# Soul Protocol

**The open standard for portable AI identity and memory.**

[![PyPI version](https://img.shields.io/pypi/v/soul-protocol)](https://pypi.org/project/soul-protocol/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/OCEAN/soul-protocol/actions)

---

## What is Soul Protocol?

Soul Protocol gives AI agents persistent identity and psychology-informed memory.
Instead of stateless prompts, your agent remembers, evolves, and maintains a
consistent personality across conversations. Export the soul as a portable `.soul`
file and migrate between any platform.

---

## Features

| Category | What you get |
|---|---|
| **Memory** | 5-tier architecture: core, episodic, semantic, procedural, knowledge graph |
| **Personality** | Big Five OCEAN model with communication style and biorhythms |
| **Cognition** | Psychology pipeline -- Damasio somatic markers, ACT-R activation, LIDA significance, Klein self-model |
| **Evolution** | Supervised or autonomous trait mutation with approval workflow |
| **Portability** | `.soul` file format -- zip archive with identity, memory, and state |
| **Integration** | Single `CognitiveEngine.think()` method -- plug in any LLM |
| **Retrieval** | Pluggable `SearchStrategy` -- swap in embeddings with one class |
| **CLI** | 7 commands: `birth`, `inspect`, `status`, `export`, `migrate`, `retire`, `list` |

---

## Installation

```bash
pip install soul-protocol
```

Optional extras:

```bash
pip install soul-protocol[graph]    # Knowledge graph support (networkx)
pip install soul-protocol[vector]   # NumPy for vector operations
pip install soul-protocol[dev]      # pytest, ruff, mypy
```

---

## Quick Start

```python
import asyncio
from soul_protocol import Soul, Interaction

async def main():
    # Birth a new soul
    soul = await Soul.birth(
        name="Aria",
        archetype="The Compassionate Creator",
        values=["empathy", "creativity"],
    )

    # Observe an interaction
    await soul.observe(Interaction(
        user_input="I love building with Python",
        agent_output="Python is great for prototyping!",
    ))

    # Recall memories
    memories = await soul.recall("Python")
    print(memories)

    # Reflect -- consolidates memories, updates self-model
    result = await soul.reflect()

    # Export as a portable .soul file
    await soul.export("aria.soul")

asyncio.run(main())
```

---

## Core Concepts

### .soul File Format

A `.soul` file is a zip archive containing:

| File | Purpose |
|---|---|
| `manifest.json` | Format version, checksums, stats |
| `config.json` | Identity, DNA, evolution config |
| `memory.json` | Full memory state (episodic, semantic, procedural) |
| `self_model.json` | Klein self-concept, relationship notes |
| `graph.json` | Entity relationships (if knowledge graph is used) |

Fully portable. Move between platforms, back up to cloud storage, inspect with
any zip tool. Versioned so older readers can still parse newer files.

### 5-Tier Memory

| Tier | Role | Persistence |
|---|---|---|
| **Core** | Persona definition + human knowledge | Always in context |
| **Episodic** | Interaction history with timestamps and somatic markers | Gated by significance |
| **Semantic** | Extracted facts with confidence scores and conflict resolution | Updated on every interaction |
| **Procedural** | Learned patterns and preferences | Long-term |
| **Knowledge Graph** | Entity relationships (optional, requires `networkx`) | Long-term |

The memory pipeline runs on every `soul.observe()` call:

1. Detect sentiment (Damasio somatic markers)
2. Compute significance (LIDA architecture)
3. Gate for episodic storage -- only significant experiences are kept
4. Extract semantic facts with confidence scoring
5. Extract entities for the knowledge graph
6. Update the self-model (Klein self-concept)

### OCEAN Personality

Big Five model on 0.0--1.0 scales:

- **O**penness -- curiosity, creativity, willingness to try new things
- **C**onscientiousness -- organization, reliability, attention to detail
- **E**xtraversion -- social energy, talkativeness, assertiveness
- **A**greeableness -- empathy, cooperation, warmth
- **N**euroticism -- emotional reactivity, anxiety, sensitivity

These traits drive communication style, social battery drain rate, and behavioral
tendencies. They can evolve over time through the supervised mutation system.

### CognitiveEngine

A single-method protocol. Implement `async def think(self, prompt: str) -> str`
to connect any LLM. When no engine is provided, the soul falls back to built-in
heuristics for sentiment detection, significance scoring, and fact extraction.

With an engine attached, the soul gains:
- LLM-quality sentiment analysis
- Nuanced significance assessment
- Richer fact and entity extraction
- Reflection and memory consolidation
- Self-model updates grounded in conversation

---

## CognitiveEngine Integration

Connect any LLM in about 10 lines:

```python
from soul_protocol import Soul, CognitiveEngine

class ClaudeEngine:
    """Adapter for Anthropic's Claude API."""

    def __init__(self, client):
        self.client = client

    async def think(self, prompt: str) -> str:
        response = await self.client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

# Birth a soul with LLM-enhanced cognition
soul = await Soul.birth("Aria", engine=ClaudeEngine(client))
```

The same pattern works with OpenAI, Ollama, or any other provider. Just return
a string from `think()`.

---

## SearchStrategy -- Pluggable Retrieval

The default retrieval uses token overlap (Jaccard similarity). Swap in embeddings
or a vector database with a single class:

```python
from soul_protocol import Soul, SearchStrategy

class EmbeddingSearch:
    """Use embeddings for semantic retrieval."""

    def __init__(self, embed_fn):
        self.embed_fn = embed_fn

    def score(self, query: str, content: str) -> float:
        q_vec = self.embed_fn(query)
        c_vec = self.embed_fn(content)
        return cosine_similarity(q_vec, c_vec)

soul = await Soul.birth("Aria", search_strategy=EmbeddingSearch(my_embed))

# recall() now uses your embedding function for relevance scoring
memories = await soul.recall("Python projects")
```

---

## MCP Server

Soul Protocol ships with an MCP (Model Context Protocol) server for agent
integration:

```bash
pip install soul-protocol[mcp]
SOUL_PATH=aria.soul soul-mcp
```

Exposes 10 tools that any MCP-compatible agent can call: observe interactions,
recall memories, inspect state, and more.

See [MCP documentation](https://modelcontextprotocol.io/) for integration details.

---

## CLI Reference

```
soul <command> [options]
```

| Command | Description | Example |
|---|---|---|
| `birth` | Birth a new soul | `soul birth Aria --archetype "The Creator"` |
| `inspect` | Inspect a soul file (identity, OCEAN traits, state) | `soul inspect aria.soul` |
| `status` | Show current mood, energy, social battery | `soul status aria.soul` |
| `export` | Export to .soul, .json, .yaml, or .md | `soul export aria.soul -o aria.json -f json` |
| `migrate` | Convert SOUL.md to .soul format | `soul migrate SOUL.md -o aria.soul` |
| `retire` | Retire a soul (preserves memories by default) | `soul retire aria.soul` |
| `list` | List all saved souls in ~/.soul/ | `soul list` |

---

## Architecture

```
                        Interaction
                            |
                            v
                  +-------------------+
                  | Psychology Pipeline|
                  +-------------------+
                            |
          +---------+-------+-------+---------+
          |         |               |         |
          v         v               v         v
     Somatic   Significance    Fact       Entity
     Markers   Gate (LIDA)     Extraction Extraction
     (Damasio)      |               |         |
          |         v               v         v
          |    [threshold?]    Semantic    Knowledge
          |     /       \      Memory     Graph
          |    yes       no        |         |
          v     |                  v         v
       Episodic |          +------------------+
       Memory   |          |  Self-Model      |
          |     |          |  Update (Klein)  |
          v     v          +------------------+
     +-------------------------------+
     |       Memory Manager          |
     |  (5-Tier Storage + Recall)    |
     +-------------------------------+
                    |
                    v
             .soul File Export
```

---

## How Is This Different?

**vs MemGPT / Letta**: Soul Protocol is an identity layer, not a context window
manager. MemGPT optimizes what fits in the prompt. Soul Protocol defines who
the agent *is* -- personality, memory architecture, self-concept, and evolution.

**vs LangChain Memory**: Psychology-informed, not just retrieval. Soul Protocol
adds significance scoring, emotional markers, fact conflict resolution, and
self-model tracking. Memories export as portable `.soul` files rather than being
locked to a single framework.

**vs Vector Databases**: Memory is more than retrieval. A vector DB gives you
similarity search. Soul Protocol adds significance gating (not everything is
worth remembering), somatic markers (emotional context on memories), fact
supersession (newer facts replace outdated ones), and a self-model that updates
as the agent learns about itself.

---

## Roadmap

| Version | Focus |
|---|---|
| **v0.3** | Eternal storage (Arweave/IPFS), multi-user support |
| **v0.4** | Vector embedding integration, social dynamics |
| **v0.5** | Multi-soul interactions, soul breeding |

---

## Development

```bash
git clone https://github.com/OCEAN/soul-protocol.git
cd soul-protocol
pip install -e ".[dev]"
pytest tests/
```

---

## License

[MIT](LICENSE)
