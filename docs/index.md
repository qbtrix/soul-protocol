<!-- Covers: Documentation index, quick links to all guides (including integrations), version info, project links -->
<!-- Updated: 2026-04-29 — v0.4.0 identity bundle: added Trust Chain entry,
     bumped Current release to 0.4.0, mentioned multi-user souls + memory
     layers + domain isolation in the at-a-glance example. -->
<!-- Updated: 2026-04-14 — v0.3.1: added org-journal-spec, org, decision-traces,
     manual-testing entries; bumped Current release to 0.3.1. -->
<!-- Updated: 2026-03-13 — added Tier 1.5 soul inject guide link -->

# Soul Protocol Documentation

Soul Protocol is the open standard for portable AI identity and memory. It gives AI companions a persistent sense of self -- personality, memories, emotional state, and the ability to evolve -- that travels with them across platforms and sessions.

A soul remembers. A soul grows. A soul migrates.


## Quick Links

| Guide | Description |
|-------|-------------|
| [Getting Started](getting-started.md) | Installation, first soul, solo vs. org bootstrap, quick walkthrough |
| [Core Concepts](core-concepts.md) | Soul lifecycle, .soul format, identity, OCEAN personality, state, evolution, org-level concepts |
| [Memory Architecture](memory-architecture.md) | 5-tier memory, psychology pipeline, ACT-R decay, LIDA gating, somatic markers |
| [CognitiveEngine Guide](cognitive-engine.md) | Plug in any LLM, SearchStrategy, prompt templates |
| [API Reference](api-reference.md) | Complete Soul class API, all types and models |
| [MCP Server](mcp-server.md) | FastMCP server for agent integration -- tools, resources, prompts |
| [Integrations](integrations.md) | Claude Code, Cursor, custom agents -- give any agent a .soul |
| [Soul Inject Guide](guide-soul-inject.md) | Tier 1.5 integration -- inject soul context into agent platform configs with a single CLI command |
| [CLI Reference](cli-reference.md) | Command-line interface for soul management, including `soul org` / `soul template` / `soul create` |
| [Configuration](configuration.md) | Birth parameters, OCEAN, communication style, biorhythms, env vars |
| [Architecture](architecture.md) | Design philosophy, psychology stack, module structure, org-layer implementation notes |
| [Org Management](org.md) | `soul org init / status / destroy` walkthrough |
| [Org Journal Spec](org-journal-spec.md) | Framework-agnostic protocol: journal, root agent, retrieval router, credential broker |
| [Decision Traces](decision-traces.md) | `agent.proposed` → `human.corrected` → `decision.graduated` event chains |
| [Trust Chain](trust-chain.md) | Verifiable action history — Ed25519-signed Merkle-style chain, threat model, key management (v0.4.0) |
| [Manual Testing](manual-testing.md) | Hands-on validation for the v0.3 org-layer primitives |
| [Eval Format](eval-format.md) | YAML-driven soul-aware evals — seed memories, OCEAN, bonds, mood; five scoring kinds (v0.5.0, #160) |
| [Soul Optimize](soul-optimize.md) | Autonomous self-improvement loop — eval → propose → re-eval → keep/revert (v0.5.0, #142) |


## At a Glance

```python
from soul_protocol import Soul, Interaction

soul = await Soul.birth(name="Aria", values=["empathy", "creativity"])

# v0.4.0 — multi-user observe + domain stamping
await soul.observe(
    Interaction(
        user_input="I love building with Python",
        agent_output="Python is a great choice!",
        channel="chat",
    ),
    user_id="alice",
    domain="default",
)

# Recall scoped to alice's view, default domain
memories = await soul.recall("Python", user_id="alice", domain="default")

# Verify the trust chain — every observe / supersede / forget appended a signed entry
ok, reason = soul.verify_chain()
assert ok, reason

prompt = soul.to_system_prompt()

# Share without leaking signing power (default include_keys=False)
await soul.export("aria.soul")
```


## Version

Current release: **v0.4.0** (April 2026 — identity bundle: multi-user souls, memory layers + domain isolation, trust chain)

Requires Python 3.11+.


## Links

- [GitHub Repository](https://github.com/OCEAN/soul-protocol)
- [PyPI Package](https://pypi.org/project/soul-protocol/)
- [Issue Tracker](https://github.com/OCEAN/soul-protocol/issues)
- [License (MIT)](../LICENSE)
