<!-- README.md — soul-protocol open standard -->
<!-- Updated: 2026-04-29 (v0.4.0) — Identity bundle release: multi-user souls
     (#46), user-defined memory layers + domain isolation (#41), Ed25519-signed
     trust chain (#42). Plus rolled-in polish: density-driven focus (#194),
     memory update primitives — supersede + forget --id (#193), wiki rebuild
     (#186). Schema migrates automatically on awaken. Soul.export now defaults
     to include_keys=False so shared souls cannot be impersonated. Test count
     2371 → 2551.
     Updated: 2026-04-19 (v0.3.2) — retrieval infrastructure (Router, Broker
     impl, ProjectionAdapter) pruned from soul-protocol; spec/retrieval.py
     now holds only the vocabulary (Protocols + types + exceptions) that a
     third-party implementation needs. Concrete orchestration moved to the
     consuming runtime (pocketpaw reference impl). New docs/SPEC.md is the
     language-agnostic standard. Test count 2297 → 2333.
     Updated: 2026-04-14 (v0.3.1) — bumped test count to 2297, added org-layer
     pitch to the header, new "Org layer (v0.3.1)" feature block, v0.3.1
     quick-start with `soul org init`, CLI count 38 → 44 commands (adds org,
     template, user, create), pointers to org-journal-spec.md, org.md,
     decision-traces.md, and manual-testing.md.
     Updated: 2026-04-09 (v0.3.0) — bumped test count badge to 2105, noted the
     four v0.3.0 features in this header block: dream cycle (offline batch
     memory consolidation), smart recall (opt-in LLM reranking with prompt
     injection defense and timeout), significance short-circuit (skip expensive
     steps on trivial interactions), and soul remember --type flag fix.
     Updated: 2026-04-06 — Added dream feature (offline batch consolidation).
     CLI: 37 → 38 commands. MCP: 23 → 24 tools.
     Updated: 2026-03-29 (v0.2.9) — bumped test count to 2010, version to 0.2.9.
     5 new features: skills decay, progressive recall, archival memory,
     auto-consolidation, eternal storage wiring. -->

# Soul Protocol

**Portable AI identity, memory, and emotion -- plus an org-level journal, decision traces, and a verifiable trust chain. An open standard.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests: 2551 passing](https://img.shields.io/badge/tests-2551%20passing-brightgreen)](https://github.com/qbtrix/soul-protocol)

---

> **This repo ships both the standard and a Python reference implementation.**
>
> - **Implementing Soul Protocol in another language** (Rust, Go, TypeScript, custom runtime)? Start with [docs/SPEC.md](docs/SPEC.md) — the language-agnostic contract.
> - **Building a Python agent on top of our implementation**? Continue reading this README.

---

AI memory systems optimize for retrieval: find the most similar text, stuff it into context, move on. They treat persistence as an IQ problem. But what makes a companion feel real isn't similarity search. It's knowing what matters, what to forget, and who it's becoming.

Soul Protocol gives AI agents persistent identity with psychology-informed memory. Your agent remembers selectively, forms emotional bonds, develops skills, and maintains a personality that evolves over time. The entire state exports as a portable `.soul` file. Switch LLMs, switch platforms, keep the soul.

**v0.4.0 — Identity bundle (April 2026):** one soul can serve multiple users without bleeding context (`soul.observe(user_id=...)`), memory layers are open strings instead of a fixed enum (build a custom `social` or `finance` layer), domain isolation enforces who can read/write which slice, and every learning event, memory mutation, and bond change appends a signed entry to a verifiable trust chain. Read [docs/trust-chain.md](docs/trust-chain.md) for the threat model.

As of v0.3.1, the protocol also covers the layer *above* a single soul: an org-scoped append-only event journal, a root governance agent, scope-tagged memory, decision traces (`agent.proposed` → `human.corrected` → `decision.graduated`), and a zero-copy retrieval router for federating external data without copying it into the org boundary.

**[Read the whitepaper](WHITEPAPER.md)** for the full design rationale and empirical validation.

---

## Validated: 5 judges, 4 providers, 20/20 favored Soul

We tested Soul Protocol against stateless baselines using five judge models from four competing AI providers. Every single judgment favored soul-enabled agents.

![Quality Validation Results](assets/charts/tier3_multijudge.png)

**Component ablation** — which parts actually matter:

![Component Ablation](assets/charts/tier4_ablation.png)

**Head-to-head vs. Mem0** — Soul Protocol outperforms production memory systems:

![Mem0 Comparison](assets/charts/tier5_mem0.png)

> Total validation cost: **under $5**. 1,100+ agent simulations, 25 scenario variations, 5 judge models. Plus a **1,000-turn marathon**: 85% recall at 4.9x memory efficiency vs. RAG. Full methodology in the [whitepaper](WHITEPAPER.md#12-empirical-validation).

---

## Soul Health Score: 90.2 / 100

SHS is a 0-100 composite score across 7 psychology-informed dimensions. It measures whether a soul actually works -- remembers selectively, expresses personality consistently, maintains identity across exports, and forms meaningful bonds.

| Dimension | Score | Status |
|-----------|------:|--------|
| Memory Recall (D1) | -- | Not run (requires long-horizon scenarios) |
| Emotional Intelligence (D2) | 72.8 | Heuristic: 70% accuracy. LLM judge: 97%. |
| Personality Expression (D3) | 96.0 | Prompt fidelity 100%, OCEAN stability 100% |
| Bond / Relationship (D4) | 100.0 | Logarithmic growth curve r=1.000 |
| Self-Model (D5) | 88.0 | Domain classification 100%, emergence at turn 2 |
| Identity Continuity (D6) | 100.0 | Export/import round-trip lossless |
| Portability (D7) | 100.0 | Engine-independent by design |

The entire eval suite runs without an LLM. Cost: $0. Fully reproducible. When tested with Claude Haiku as an LLM judge, sentiment accuracy jumps from 70% to 97%, proving the architecture works -- the heuristic fallback is the honest baseline, not the ceiling.

Full methodology: [research/EVAL-FRAMEWORK.md](research/EVAL-FRAMEWORK.md)

---

## Architecture: spec + runtime

```
soul_protocol/
├── spec/                   The protocol. Portable, minimal, no opinions.
│                           Per-soul types + org-layer types (journal, decisions, retrieval).
├── runtime/                Reference implementation. Opinionated, batteries-included.
├── engine/                 Org-layer engine: SQLite WAL journal, retrieval router, credential broker.
├── cli/                    44-command CLI (incl. `soul org`, `soul template`, `soul user`, `soul create`)
└── mcp/                    MCP server (24 tools, 3 resources)
```

**`spec/`** defines what any runtime must implement: Identity, MemoryStore, MemoryEntry, SoulContainer, `.soul` file format, EmbeddingProvider, EternalStorageProvider. v0.3 added org-layer spec types (`EventEntry`, `Actor`, `DataRef`, `AgentProposal`, `HumanCorrection`, `DecisionGraduation`, `RetrievalRequest`/`Result`, `RetrievalTrace`). Depends on Pydantic only.

**`runtime/`** is one way to run the protocol. OCEAN personality, five-tier memory, psychology pipeline, cognitive engine, bonds, skills, evolution. Other runtimes can implement `spec/` differently.

**`engine/`** (new in v0.3.1) runs the org layer: a SQLite WAL-backed journal with atomic `seq` allocation, a retrieval router that resolves `DataRef` payloads against registered adapters, and a credential broker that scopes secrets per source and fails closed on denial. The full contract lives in [`docs/org-journal-spec.md`](docs/org-journal-spec.md).

Like HTTP and nginx. The spec defines the contract. The runtime is one implementation.

---

## Features

| Category | What you get |
|---|---|
| **Memory** | 5-tier: core, episodic, semantic, procedural, knowledge graph |
| **Psychology** | Damasio somatic markers, ACT-R activation decay, LIDA significance gate, Klein self-model |
| **Personality** | OCEAN Big Five with communication style and biorhythms. Structured, not a prompt string. |
| **Bond** | Emotional attachment (0-100 strength). Logarithmic growth, linear decay. |
| **Evolution** | Supervised or autonomous trait mutation with approval workflow |
| **Cognitive adapters** | `engine="auto"` or `engine=AnthropicEngine()` — wire any LLM into the cognitive pipeline |
| **MCP sampling** | Running inside Claude Code / Desktop? The host LLM handles cognition. No extra API key. |
| **LCM** | Lossless Context Management — three-level compaction, SQLite backing, no lost context |
| **Visibility tiers** | `PUBLIC` / `BONDED` / `PRIVATE` on every memory; recall filtered by bond strength |
| **Templates** | `SoulFactory` — define archetypes and batch-create souls from a template |
| **A2A bridge** | Export/import Google A2A Agent Cards ↔ `.soul` files |
| **Format importers** | `SoulSpecImporter` (SOUL.md), `TavernAIImporter` (Character Card V2, incl. PNG) |
| **Graph traversal** | BFS, shortest path, neighborhood, subgraph, and `progressive_context()` (L0/L1/L2) |
| **Vector search** | Pluggable EmbeddingProvider. Real backends: sentence-transformers, OpenAI, Ollama. |
| **Encryption** | AES-256-GCM encryption at rest for .soul files (scrypt key derivation) |
| **GDPR deletion** | Targeted memory deletion with cascade logic and audit trail |
| **Eternal storage** | Archive to decentralized storage (mock providers, production planned) |
| **Portability** | `.soul` ZIP archive. JSON inside. Rename to .zip and read it. |
| **Cross-language** | JSON Schemas auto-generated from spec. Validate `.soul` files in any language. |
| **Dream** | Offline batch consolidation — topic clustering, procedure detection, graph cleanup, personality drift |
| **Org Journal** | Append-only event log with SQLite WAL backend, atomic `seq`, opportunistic hash-chain. `soul org init` bootstraps it. |
| **Root Agent** | Governance identity with three-layer undeletability (file guard, protocol guard, CLI refusal). Signs; cannot execute. |
| **Scope tags** | `MemoryEntry.scope` + `match_scope` helper. Bidirectional containment (`org:sales:*` matches `org:sales:leads`). |
| **Decision traces** | `agent.proposed` → `human.corrected` → `decision.graduated` event chains linked by `causation_id`. |
| **Zero-Copy federation** | `RetrievalRouter` + `CredentialBroker`. Resolves `DataRef` payloads against registered adapters; only the receipt crosses the boundary. |
| **RetrievalTrace** | Every `recall()` and `smart_recall()` emits a trace (query, candidates, rerank decisions) on `Soul.last_retrieval`. |
| **Role archetypes** | Bundled Arrow, Flash, Cyborg, Analyst templates. `soul template list` / `soul create --template arrow`. |
| **CLI** | 44 commands. Rich TUI output. |
| **MCP** | 24 tools + 3 resources for Claude Code, Cursor, or any MCP client |

---

## Install

```bash
pip install soul-protocol
```

As of v0.3.1 the bare install gives you a working `soul` CLI out of the box — no extras required. The `[engine]` extra is kept as an empty alias so older pins keep resolving (#173).

Extras:

| Extra | What it adds |
|---|---|
| `[engine]` | Empty backwards-compat alias. The base install already ships Click, Rich, PyYAML, and cryptography. |
| `[mcp]` | MCP server (Claude Code, Cursor, any MCP client) |
| `[anthropic]` | `AnthropicEngine` — Anthropic SDK cognitive adapter |
| `[openai]` | `OpenAIEngine` — OpenAI SDK cognitive adapter |
| `[ollama]` | `OllamaEngine` — local Ollama cognitive adapter |
| `[litellm]` | `LiteLLMEngine` — 100+ providers via LiteLLM |
| `[llm]` | All three commercial adapters at once |
| `[embeddings-st]` | `SentenceTransformerEmbedder` — local semantic embeddings |
| `[embeddings-openai]` | `OpenAIEmbedder` — OpenAI text-embedding-3 |
| `[embeddings-ollama]` | `OllamaEmbedder` — local Ollama embeddings |
| `[graph]` | networkx knowledge graph |
| `[all]` | Everything above |

```bash
# LLM-wired soul (Anthropic)
pip install "soul-protocol[anthropic] @ git+https://github.com/qbtrix/soul-protocol.git"

# MCP server
pip install "soul-protocol[mcp] @ git+https://github.com/qbtrix/soul-protocol.git"

# Everything
pip install "soul-protocol[all] @ git+https://github.com/qbtrix/soul-protocol.git"
```

Or clone:

```bash
git clone https://github.com/qbtrix/soul-protocol.git
cd soul-protocol
pip install -e ".[dev]"
```

---

## Quick start

### CLI

```bash
soul init "Aria" --archetype "The Compassionate Creator"
soul inspect .soul/
soul status .soul/
```

### Python

```python
import asyncio
from soul_protocol import Soul, Interaction

async def main():
    soul = await Soul.birth(
        name="Aria",
        archetype="The Coding Expert",
        values=["precision", "clarity"],
        ocean={"openness": 0.8, "conscientiousness": 0.9, "neuroticism": 0.2},
        communication={"warmth": "high", "verbosity": "low"},
        persona="I am Aria, a precise coding assistant.",
    )

    await soul.observe(Interaction(
        user_input="How do I optimize this SQL query?",
        agent_output="Add an index on the join column.",
    ))

    # The soul discovers its own identity from experience
    images = soul.self_model.get_active_self_images()

    memories = await soul.recall("SQL optimization")
    prompt = soul.to_system_prompt()
    await soul.export("aria.soul")

asyncio.run(main())
```

Or from config:

```python
soul = await Soul.birth_from_config("soul-config.yaml")
```

```yaml
# soul-config.yaml
name: Aria
archetype: The Coding Expert
values: [precision, clarity, speed]
ocean:
  openness: 0.8
  conscientiousness: 0.9
  neuroticism: 0.2
communication:
  warmth: high
  verbosity: low
persona: I am Aria, precise and efficient.
```

---

## Quick start: bootstrap an org (v0.3.1)

A single soul is great for a personal companion. For a team of agents that share a journal, scope grammar, and root signing key, bootstrap an org:

```bash
pip install soul-protocol
soul org init --org-name "Acme" --purpose "AI tooling" --non-interactive
soul org status
```

That creates `~/.soul/` with a root soul, Ed25519 signing keys, a SQLite WAL journal seeded with `org.created` + `scope.created` events, and an archive directory at `~/.soul-archives/`. Every subsequent action — memories, proposals, corrections, retrievals — writes into that journal. See [`docs/org.md`](docs/org.md) for the full flow.

Instantiate a soul from a bundled role archetype:

```bash
soul template list                       # Arrow, Flash, Cyborg, Analyst
soul create --template arrow --name Aria # new soul preconfigured with Arrow's DNA
```

Every recall now leaves a receipt:

```python
memories = await soul.recall("Python")
trace = soul.last_retrieval  # RetrievalTrace: query, candidates, rerank decisions, final
```

---

## The .soul file

A ZIP archive containing everything:

| File | Contents |
|---|---|
| `manifest.json` | Format version, soul ID, export timestamp, stats |
| `soul.json` | Identity, DNA, memory settings, evolution config |
| `state.json` | Mood, energy, focus, social battery |
| `dna.md` | Human-readable personality blueprint |
| `memory/core.json` | Persona + bonded-entity profile |
| `memory/episodic.json` | Interaction history with somatic markers |
| `memory/semantic.json` | Extracted facts with confidence scores |
| `memory/procedural.json` | Learned patterns |
| `memory/graph.json` | Temporal entity relationships |
| `memory/self_model.json` | Klein self-concept domains |

Rename to `.zip`, open with any archive tool. Move between platforms. Back up anywhere. Version in git.

---

## Memory pipeline

Every `soul.observe()` call runs the psychology pipeline:

1. **Sentiment** (Damasio). Tag emotional context as a somatic marker: valence, arousal, label.
2. **Significance** (LIDA). Score novelty + emotional intensity + goal relevance. Below 0.3, skip episodic.
3. **Episodic storage**. Only significant experiences.
4. **Fact extraction**. Names, preferences, context. Conflict-checked against existing facts.
5. **Entity extraction**. Feed the knowledge graph with temporal edges.
6. **Self-model** (Klein). Update emergent domain confidence from accumulated experience.

Retrieval uses ACT-R activation decay: recent, frequently accessed, emotionally charged memories rank higher. A memory recalled twice today outranks an "important" memory from last week that was never revisited.

---

## CognitiveEngine

Connect any LLM — three ways:

```python
from soul_protocol import Soul
from soul_protocol.runtime.cognitive.adapters import AnthropicEngine, LiteLLMEngine

# 1. Auto-detect from installed packages
soul = await Soul.birth("Aria", engine="auto")

# 2. Explicit adapter
soul = await Soul.birth("Aria", engine=AnthropicEngine(model="claude-opus-4-5"))

# 3. Any async callable
async def my_llm(prompt: str) -> str:
    ...  # call your own API

soul = await Soul.birth("Aria", engine=my_llm)
```

Or write your own adapter — implement a single `async def think(self, prompt: str) -> str` method:

```python
class MyEngine:
    async def think(self, prompt: str) -> str:
        ...

soul = await Soul.birth("Aria", engine=MyEngine())
```

Without an engine, the soul falls back to `HeuristicEngine`: word-list sentiment, formula-based significance, regex fact extraction. No LLM calls, no hallucination, no cost.

When running as an MCP server inside Claude Code or Claude Desktop, `engine="auto"` automatically routes cognitive tasks to the host LLM via MCP sampling — no API key needed.

---

## Vector search

```python
from soul_protocol.runtime.embeddings.hash_embedder import HashEmbedder
from soul_protocol.runtime.embeddings.vector_strategy import VectorSearchStrategy

strategy = VectorSearchStrategy(embedder=HashEmbedder(dimensions=64))
# Use with soul.recall() or standalone
```

The `EmbeddingProvider` interface is defined in `spec/`. Swap in OpenAI, Cohere, or local embeddings by implementing `embed()` and `dimensions`.

---

## Eternal storage

```bash
soul archive aria.soul --tiers local,ipfs
soul recover aria.soul --source ipfs
soul eternal-status aria.soul
```

Archive souls to decentralized storage (local, IPFS, Arweave, blockchain). Current providers are mocks for development. Production integrations planned.

---

## CLI

```
soul <command> [options]
```

See [CLI Reference](docs/cli-reference.md) for all 44 commands. Highlights:

| Command | Description |
|---|---|
| `init` | Initialize a .soul/ folder (like .git/) |
| `birth` | Birth a new soul (OCEAN flags, config files) |
| `inspect` | Full TUI: identity, OCEAN bars, state, memory, self-model |
| `status` | Quick check: mood, energy, memory count |
| `export` | Export to .soul, .json, .yaml, or .md |
| `inject` | Inject soul context into an agent platform's config file |
| `migrate` | Convert SOUL.md to .soul format |
| `recall` | Query a soul's memories |
| `remember` | Store a memory in a soul |
| `retire` | Retire a soul (preserves memories) |
| `list` | List saved souls in ~/.soul/ |
| `unpack` | Unpack a .soul file into a browsable directory |
| `archive` | Archive to eternal storage tiers |
| `recover` | Recover from eternal storage |
| `eternal-status` | Show eternal storage references |
| `dream` | Offline batch memory consolidation |
| `org init` | Bootstrap an org (root soul, journal, scopes, fleet) |
| `org status` | Snapshot the org from its journal |
| `org destroy` | Archive-and-wipe the org directory |
| `template list` / `show` | Browse bundled role archetypes (Arrow, Flash, Cyborg, Analyst) |
| `create --template` | Instantiate a soul from an archetype |
| `user invite` | Invite a user to the org (stub — real flow in a follow-up PR) |

---

## MCP server

```bash
pip install soul-protocol[mcp]
SOUL_PATH=aria.soul soul-mcp
```

24 tools and 3 resources for Claude Code, Cursor, or any MCP-compatible client. See [integrations](docs/integrations.md).

---

## Comparison

**vs Mem0**: Mem0 does vector retrieval. Soul Protocol adds identity, personality, significance gating, emotional memory, and a portable file format. In head-to-head benchmarks, Soul Protocol scored 8.5 vs. Mem0's 6.0 overall, with the largest gap in emotional continuity (9.2 vs. 7.0).

**vs Cognee**: Cognee builds knowledge graphs from unstructured data. Good system, but platform-locked. Soul Protocol's knowledge graph is portable and comes with temporal edges.

**vs MemGPT / Letta**: Context window management vs. identity. MemGPT optimizes what fits in the prompt. Soul Protocol defines who the agent *is*.

**vs LangChain Memory**: RAG retrieval vs. psychology-informed processing. Soul Protocol adds significance scoring, somatic markers, fact conflict resolution, self-model tracking, and portable export.

**vs OpenAI Memory**: Per-account facts vs. a portable standard. Export your soul, own your data.

---

## Use with PocketPaw

[PocketPaw](https://github.com/pocketpaw/pocketpaw) uses soul-protocol for persistent identity across Telegram, Discord, Slack, WhatsApp, and web.

```python
from soul_protocol import Soul, Interaction

soul = await Soul.awaken(".soul/")
await soul.observe(Interaction(
    user_input=user_message,
    agent_output=agent_response,
))
```

---

## Documentation

- [Whitepaper](WHITEPAPER.md) -- design rationale, psychology stack, empirical validation
- [Architecture](docs/architecture.md) -- two-layer diagrams, module dependency graph, org-layer implementation notes
- [Org Journal Spec](docs/org-journal-spec.md) -- framework-agnostic protocol for the journal, root agent, and retrieval router
- [Org Management](docs/org.md) -- `soul org init / status / destroy` walkthrough
- [Decision Traces](docs/decision-traces.md) -- `agent.proposed` → `human.corrected` → `decision.graduated` chains
- [Manual Testing](docs/manual-testing.md) -- hands-on validation for the org-layer primitives
- [Configuration](docs/configuration.md) -- OCEAN, communication style, config files, env vars
- [Self-Model](docs/self-model.md) -- Klein's self-concept, domain discovery
- [Cognitive Engine](docs/cognitive-engine.md) -- LLM integration, heuristic fallback
- [Memory Architecture](docs/memory-architecture.md) -- five tiers, activation, compression
- [CLI Reference](docs/cli-reference.md) -- all commands and options
- [MCP Server](docs/mcp-server.md) -- tools, resources, setup
- [Gap Analysis](docs/GAP-ANALYSIS.md) -- what's built vs. what's planned
- [JSON Schemas](schemas/) -- cross-language `.soul` file validation

---

## Development

```bash
git clone https://github.com/qbtrix/soul-protocol.git
cd soul-protocol
pip install -e ".[dev]"
pytest tests/   # 2297 tests
```

---

## License

[MIT](LICENSE)
