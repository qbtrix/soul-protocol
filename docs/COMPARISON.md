<!--
  COMPARISON.md — soul-protocol vs other AI memory systems.
  Updated: 2026-05-25 — rewrite against the 0.5.0.dev0 surface. Adds rows for
  trust chain (signed action history), multi-user attribution + domain
  isolation, soul-aware evals, autonomous optimization, graph traversal +
  typed ontology, and dedup-aware writes. Previous version (2026-03-08) is
  preserved in git history.
  Created: 2026-03-08 — head-to-head feature matrix vs Mem0, MemGPT/Letta,
  LangChain Memory, Cognee, and OpenAI Memory.
-->

# Comparison: Soul Protocol vs. AI Memory Systems

> [!NOTE]
> **Last refreshed:** 2026-05-25 against soul-protocol **v0.5.0.dev0**.
> **Previous version:** 2026-03-08, scored against soul-protocol 0.2.x. Preserved in git history.
> Competitor capability claims reflect each project's latest stable release as of refresh date — links inline.

How Soul Protocol compares to [Mem0](https://github.com/mem0ai/mem0), [MemGPT / Letta](https://github.com/letta-ai/letta), [LangChain Memory](https://python.langchain.com/docs/modules/memory/), [Cognee](https://github.com/topoteretes/cognee), and OpenAI Memory. We try to be fair. Every system on this list solves real problems. The question is which problems you need solved.

Soul Protocol's pitch is differentiated, not dominant. Competitors do real things better — mature vector store ecosystems, longer production track records, deeper context-window management. The rows below name those wins, too.

---

## 1 · Feature matrix

| Dimension | Soul Protocol (0.5.0.dev0) | Mem0 | MemGPT / Letta | LangChain Memory | Cognee | OpenAI Memory |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Portable identity** (single-file `.soul` archive) | Yes | No | No | No | No | No |
| **Multi-user attribution** (`user_id` on every memory) | Yes (0.4.0) | Per-user instance | Per-agent | Per-conversation | Per-dataset | Per-account |
| **Domain isolation** (allow-list-enforced sub-namespaces) | Yes (0.4.0) | No | No | No | Yes (graph domains) | No |
| **Signed action history** (Ed25519 trust chain, verifiable) | Yes (0.4.0 + hardening 0.5.0.dev0) | No | No | No | No | No |
| **Personality model** (OCEAN Big Five, structured) | Yes | No | No | No | No | No |
| **Significance gating** (LIDA — decide what's worth remembering) | Yes | No | No | No | No | No |
| **Emotional memory** (somatic markers per memory) | Yes | No | No | No | No | No |
| **Self-model** (Klein — emergent identity from experience) | Yes | No | No | No | No | No |
| **Activation decay** (ACT-R — recency + frequency scoring) | Yes | No | No | No | No | No |
| **Memory update verbs** (`confirm`/`update`/`supersede`/`forget`/`purge`/`reinstate`, PE-gated) | Yes (0.5.0.dev0) | Add/update/delete | Function-call based | Buffer/summary clear | Graph CRUD | Add/forget |
| **Dedup-aware writes** (`note()` with Jaccard + containment, CREATE/SKIP/MERGE) | Yes (0.5.0.dev0) | Partial (semantic dedup) | No | No | Graph-level merge | Yes (opaque) |
| **Knowledge graph** (temporal entity-relations) | Yes (typed: 8 kinds + 8 predicates, 0.5.0.dev0) | No | No | Entity memory only | Yes (rich) | No |
| **Graph traversal API** (`nodes/edges/path/subgraph/mermaid`) | Yes (0.5.0.dev0) | No | No | No | Yes | No |
| **Soul-aware evals** (YAML spec, 5 scoring kinds, soul-state seeding) | Yes (0.5.0.dev0) | No | No | LangSmith (external) | No | No |
| **Autonomous optimization** (`optimize` loop drives knobs from eval signal) | Yes (0.5.0.dev0) | No | No | No | No | No |
| **Structured diff** (`soul diff` across identity, memory, trust chain) | Yes (0.5.0.dev0) | No | No | No | No | No |
| **Vector search** | Pluggable (sentence-transformers, OpenAI, Ollama, TF-IDF, hash) | Built-in (mature, many stores) | Via tools | Built-in (via embeddings) | Built-in | Internal |
| **Pluggable LLM** (any provider, including offline) | Yes (Anthropic / OpenAI / Ollama / LiteLLM / MCP-sampling / Callable) | Partial | No (OpenAI-focused) | Yes | Yes | No (OpenAI only) |
| **Heuristic fallback** (zero LLM calls, zero cost) | Yes | No | No | No | No | No |
| **Offline mode** (no network required) | Yes | No | No | Partial | No | No |
| **Append-only org journal** (SQLite WAL, hash-chained, scope-stamped) | Yes (0.3.1) | No | No | No | No | No |
| **Decision traces** (`agent.proposed` → `human.corrected` → `decision.graduated`) | Yes (0.3.1) | No | No | No | No | No |
| **MCP server** (28+ tools, FastMCP-based) | Yes | Community wrapper | Community wrapper | No | No | No |
| **Multi-language spec** (language-agnostic SPEC.md + conformance contract) | Yes (0.3.3, conformance suite pending) | No | No | No | No | No |
| **Open standard / public RFC process** | Yes | No | No | No | No | No |
| **Context window management** (paging in/out of LLM context) | No | No | Yes (core feature) | Partial | No | No |
| **RAG pipeline** | No (use with) | Yes | Via tools | Yes | Yes | Internal |
| **Production-grade vector DB integrations** | Planned | Yes (broad ecosystem) | Yes | Yes (broad ecosystem) | Yes | Internal |
| **Persistent graph DB backends** (Neo4j, etc.) | No | No | No | No | Yes | No |
| **Managed cloud service** | No | Yes | Yes | No | Yes | Yes |

---

## 2 · Benchmark snapshot

Five-tier head-to-head from 2026-03 still stands as the most recent direct measurement. Soul Protocol and Mem0 (v1.0.5) processed identical conversations, scored by the same LLM judge. Stateless baseline included for reference.

| Test | Soul Protocol | Mem0 v1.0.5 | Stateless Baseline |
|---|:---:|:---:|:---:|
| **Overall** | **8.5** | 6.0 | 3.0 |
| **Emotional Continuity** | **9.2** | 7.0 | 1.8 |
| **Hard Recall** (fact buried under 30+ turns) | **7.8** | 5.1 | 4.2 |

Component ablation — which parts of Soul Protocol actually matter:

| Condition | Response Quality | Hard Recall | Emotional Continuity | Overall |
|---|:---:|:---:|:---:|:---:|
| **Full Soul** (personality + memory) | 8.3 ± 0.3 | 8.4 ± 0.4 | 9.3 ± 0.2 | **8.7 ± 0.2** |
| **RAG Only** (memory, no personality) | 7.8 ± 0.3 | 8.2 ± 0.2 | 9.3 ± 0.2 | 8.4 ± 0.2 |
| **Personality Only** (no memory) | 7.8 ± 0.4 | 5.9 ± 0.7 | 7.2 ± 0.7 | 7.0 ± 0.4 |

Validation details: 5 judge models from 4 providers (Anthropic, Google, DeepSeek, Meta). 20/20 judgments favored Soul over stateless baseline. Total validation cost under $5. Full methodology in the [whitepaper](../WHITEPAPER.md#12-empirical-validation).

The 0.5.0.dev0 features (memory update primitives, evals, optimize, graph traversal) were not part of this benchmark. The benchmark will re-run when 0.5.0 tags; new dimensions (multi-user separation, optimization-loop convergence, trust-chain verification overhead) will be added at that point.

---

## 3 · How each system differs

### 3.1 · Mem0

Mem0 is a persistent memory layer for LLM applications. It stores user facts and preferences in a vector database and retrieves them via similarity search. It does this well and has production-ready integrations with major vector stores.

**Where Soul Protocol differs.** Mem0 treats memory as a retrieval problem. Soul Protocol treats it as an identity problem with memory hanging off the identity. Mem0 stores facts. Soul Protocol stores facts with emotional context (somatic markers), filters what's worth storing (significance gate), lets memories strengthen or fade based on usage (ACT-R decay), and builds an emergent self-concept from accumulated experience (Klein self-model).

As of 0.4.0/0.5.0.dev0, Soul Protocol also carries:

- A signed, verifiable history of every memory mutation (the trust chain) — Mem0 has no equivalent. You cannot prove what a Mem0 store contained at time T.
- Multi-user attribution with domain isolation enforcement — Mem0 is per-user-instance; serving multiple users from one store with allow-listed namespaces is not native.
- Memory update verbs gated by prediction error and a one-hour reconsolidation window — Mem0 has update/delete but no cog-sci-grounded gating.
- A `note()` writer with Jaccard + containment dedup that returns CREATE/SKIP/MERGE — Mem0's dedup runs implicitly during indexing.

**Where Mem0 wins.** Production-grade vector DB integrations across the major stores (Chroma, Pinecone, Qdrant, Weaviate, pgvector). Mature managed cloud. Longer production track record at scale. If you just need "remember what the user said earlier" with a hosted backend, Mem0 is the simpler deploy.

In the 2026-03 benchmark, both beat a stateless baseline; Soul scored 8.5 overall vs Mem0's 6.0, with the largest gap in emotional continuity (9.2 vs 7.0). That benchmark predates Soul Protocol's 0.4/0.5 additions.

Mem0 has no concept of portable identity. There is no file format, no personality model, no signed history, and no way to move a memory state between platforms.

### 3.2 · MemGPT / Letta

MemGPT solves a specific and important problem: how to give an LLM access to more memory than fits in a single context window. It pages memory in and out, uses function calls to manage retrieval, and effectively gives an LLM an operating system for its own context.

**Where Soul Protocol differs.** MemGPT manages *what fits in the prompt*. Soul Protocol defines *who the agent is*. MemGPT doesn't have personality, portable identity, emotional markers, a self-model, signed history, or domain isolation. Soul Protocol doesn't manage context windows.

The two are complementary: a MemGPT system could use Soul Protocol for the identity + signed-history layer that gets paged into context.

**Where MemGPT / Letta wins.** Context window management is the canonical problem MemGPT was built for; Soul Protocol has nothing in that lane. Letta's hosted service is mature. If your primary problem is "my conversations don't fit in 200k tokens and I need automated paging," reach for MemGPT.

### 3.3 · LangChain Memory

LangChain provides memory modules for RAG pipelines: conversation buffers, summary buffers, entity memory, vector store-backed retrieval. These are retrieval infrastructure components.

**Where Soul Protocol differs.** LangChain memory answers "how do I find relevant context?" Soul Protocol answers "who is this AI and what does it remember?" LangChain has no significance filtering (everything gets stored), no emotional tagging, no activation decay, no self-model, no portable file format, no signed history, and no eval / optimize loop. Soul Protocol's memory pipeline decides *whether* to store something before deciding *how* to retrieve it.

**Where LangChain wins.** Ecosystem breadth. If you're already deep in LangChain, the buffer / summary / entity memory modules drop in with one import and integrate with every chain / agent primitive in the framework. LangSmith provides external evaluation tooling that's more mature than Soul Protocol's in-tree `soul eval`.

### 3.4 · Cognee

Cognee builds knowledge graphs from unstructured data with domain isolation. It has strong graph construction and query capabilities with production integrations and persistent graph DB backends.

**Where Soul Protocol differs.** Cognee's knowledge graph is locked to its runtime. Soul Protocol's knowledge graph is portable (entities + typed edges serialize into the `.soul` file with `graph.entity_added` / `graph.relation_added` trust-chain hooks) and comes alongside seven other memory layers. Soul Protocol adds identity, personality, emotional memory, significance gating, signed history, and the eval / optimize loop that Cognee doesn't address.

The 0.5.0.dev0 graph work narrowed the historical gap: Soul Protocol now ships eight built-in entity kinds, eight relation predicates, and a `Soul.graph` view with `path` / `subgraph` / `to_mermaid` / `reachable`. Graph mutations are signed into the trust chain.

**Where Cognee wins.** Persistent graph DB backends (Neo4j and friends) — Soul Protocol's graph is in-memory dict + adjacency-list, fine for soul-sized graphs but not for enterprise knowledge graphs at scale. Cognee's graph construction from unstructured corpora is more mature. If your application is more about structured knowledge over a large corpus than companion identity, Cognee's graph-first approach is the better fit.

### 3.5 · OpenAI Memory

OpenAI's built-in memory stores facts about users across conversations within the OpenAI ecosystem. It's automatic, requires no setup, and works well within ChatGPT and the API.

**Where Soul Protocol differs.** OpenAI Memory is per-account, per-platform. You cannot export it, move it to another provider, inspect the raw data, or verify what was stored when. Soul Protocol is a portable file you own: rename it to `.zip`, read the JSON, load it with Claude today and Ollama tomorrow. The trust chain proves the soul's history hasn't been tampered with. The eval framework lets you measure whether the soul is actually behaving as you want.

OpenAI Memory also has no personality model, no emotional markers, no self-model, no domain isolation, no eval / optimize loop, and no signed history. It stores facts; Soul Protocol stores identity.

**Where OpenAI wins.** Zero-config. If you're building exclusively on OpenAI's platform and want "it just works," there's no setup required. The flip side is total vendor lock-in.

---

## 4 · When to use what

Not every project needs Soul Protocol. Here's an honest guide.

**Use Mem0 if** you need a production-ready persistent memory layer with minimal setup, you're building a standard chatbot that needs to remember user preferences, and you don't need portable identity, signed history, or emotional context. Mem0 is simpler to deploy and has mature vector store integrations.

**Use MemGPT / Letta if** your primary problem is context window management. If your agent needs to work with very long conversations and you need to page information in and out of context efficiently, MemGPT is purpose-built for that.

**Use LangChain Memory if** you're already in the LangChain ecosystem and need basic conversation persistence. Buffer memory and entity memory are straightforward to add to an existing chain.

**Use Cognee if** your primary need is building and querying knowledge graphs from large unstructured corpora with strong domain isolation and a persistent graph DB. Soul Protocol's graph is portable but in-memory; Cognee's is enterprise-scale.

**Use OpenAI Memory if** you're building exclusively on OpenAI's platform and want zero-config persistence. It just works, with no additional infrastructure — and no portability or auditability.

**Use Soul Protocol if** you're building an AI agent that needs to feel like someone rather than something — and that needs to be auditable, portable, and measurable. Specifically:

- You need an agent with a persistent personality that evolves, memories that carry emotional weight, and a sense of self that develops from experience.
- You need to **move identity between platforms** without losing memory or behavior.
- You need to **prove** what your agent learned and when (the trust chain — required for compliance, reputation systems, or shared-soul deployments).
- You need **multi-user attribution and domain isolation** in a single soul (one agent serving multiple humans with enforced context separation).
- You need to **measure and improve** the agent against held-out cases (the `soul eval` + `soul optimize` loop).
- You need **dedup-aware writes** so repeated similar facts collapse instead of accumulating duplicates.

Soul Protocol also works alongside the systems above. You can use Mem0 or LangChain for retrieval and Soul Protocol for the identity + signed-history layer on top. The `CognitiveEngine` interface means any LLM backend works, and the `.soul` file format means the identity is never locked to one platform.

---

## 5 · What this doc does not cover

- Specific competitor performance benchmarks under load. The 2026-03 numbers compare quality, not latency / throughput / cost-per-write.
- Hosted-service economics. Mem0 / Letta / Cognee / OpenAI Memory all run cloud services with different pricing models; soul-protocol is self-hosted only at this layer.
- Forward compatibility. Each competitor evolves; rows above were verified against latest stable releases as of refresh date. File an issue if a row goes stale.
