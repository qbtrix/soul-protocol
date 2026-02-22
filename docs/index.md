<!-- Covers: Documentation index, quick links to all guides, version info, project links -->

# Soul Protocol Documentation

Soul Protocol is the open standard for portable AI identity and memory. It gives AI companions a persistent sense of self -- personality, memories, emotional state, and the ability to evolve -- that travels with them across platforms and sessions.

A soul remembers. A soul grows. A soul migrates.


## Quick Links

| Guide | Description |
|-------|-------------|
| [Getting Started](getting-started.md) | Installation, first soul, quick walkthrough |
| [Core Concepts](core-concepts.md) | Soul lifecycle, .soul format, identity, OCEAN personality, state, evolution |
| [Memory Architecture](memory-architecture.md) | 5-tier memory, psychology pipeline, ACT-R decay, LIDA gating, somatic markers |
| [CognitiveEngine Guide](cognitive-engine.md) | Plug in any LLM, SearchStrategy, prompt templates |
| [API Reference](api-reference.md) | Complete Soul class API, all types and models |
| [MCP Server](mcp-server.md) | FastMCP server for agent integration -- tools, resources, prompts |
| [CLI Reference](cli-reference.md) | Command-line interface for soul management |
| [Architecture](architecture.md) | Design philosophy, psychology stack, module structure |


## At a Glance

```python
from soul_protocol import Soul, Interaction

soul = await Soul.birth(name="Aria", values=["empathy", "creativity"])

await soul.observe(Interaction(
    user_input="I love building with Python",
    agent_output="Python is a great choice!",
    channel="chat",
))

memories = await soul.recall("Python")
prompt = soul.to_system_prompt()

await soul.export("aria.soul")
```


## Version

Current release: **v0.2.2**

Requires Python 3.11+.


## Links

- [GitHub Repository](https://github.com/OCEAN/soul-protocol)
- [PyPI Package](https://pypi.org/project/soul-protocol/)
- [Issue Tracker](https://github.com/OCEAN/soul-protocol/issues)
- [License (MIT)](../LICENSE)
