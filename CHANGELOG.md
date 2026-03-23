# Changelog

All notable changes to soul-protocol are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.2.5] — 2026-03-23

### Added

- **Cognitive adapters** — wire any LLM into a soul's cognitive engine without subclassing. Pass `engine="auto"` to auto-detect from installed packages, `engine=AnthropicEngine()` / `OpenAIEngine()` / `OllamaEngine()` / `LiteLLMEngine("ollama/llama3.2")` for explicit control, or any async callable `engine=my_fn`. New install extras: `[anthropic]`, `[openai]`, `[ollama]`, `[litellm]`, `[llm]` (all three at once).
- **MCP sampling engine** — when the soul runs as an MCP server inside Claude Code or Claude Desktop, it now delegates cognitive tasks (significance gating, fact extraction, reflection) to the host LLM via `ctx.sample()`. No separate API key or extra dependency required.
- **Real embedding providers** — `SentenceTransformerEmbedder`, `OpenAIEmbedder`, and `OllamaEmbedder` replace hash-based similarity for semantic memory search. Install with `[embeddings-st]`, `[embeddings-openai]`, or `[embeddings-ollama]`.
- **Lossless Context Management (LCM)** — conversation context is never silently dropped. Three-level compaction (Summary → Bullets → Truncate) with a SQLite-backed conversation store and a hierarchical DAG for full-fidelity retrieval. Zero new dependencies — sqlite3 is stdlib.
- **Memory visibility tiers** — every `MemoryEntry` now carries a `visibility` field: `PUBLIC`, `BONDED`, or `PRIVATE`. Recall is automatically filtered by requester identity and bond strength.
- **Soul templates and `SoulFactory`** — define soul archetypes once, stamp out multiple souls in a single call. Useful for simulations, multi-agent pipelines, and testing.
- **A2A Agent Card bridge** — bidirectional conversion between Google A2A Agent Cards and `.soul` files. New CLI commands: `soul export-a2a` and `soul import-a2a`.
- **Format importers** — `SoulSpecImporter` reads SOUL.md / soul.json persona files; `TavernAIImporter` reads Character Card V2 (JSON and PNG with embedded `chara` tEXt chunk). No Pillow dependency for PNG imports.
- **Graph traversal** — `KnowledgeGraph` gains `traverse()`, `shortest_path()`, `get_neighborhood()`, `subgraph()`, and `progressive_context()` (L0/L1/L2 progressive loading for token-budget-aware context injection).
- **Learning events** — `LearningEvent` spec model wired into `Soul.learn()` for structured skill acquisition tracking alongside the existing XP system.
- **Multi-participant Interaction** — `Interaction` generalises to N participants. `user_input` and `agent_output` remain as backward-compatible properties. `Identity.bonds` replaces deprecated `bonded_to` with a `list[BondTarget]` and auto-migration.
- **Multi-soul coordination spec** (DSP v0.5.0 draft) — defines the Tuckman-informed lifecycle, transitive trust decay, reputation scoring, and handoff protocol for soul-to-soul collaboration across agents and platforms.

### Fixed

- Contradiction detection now runs during `observe()` on every call — location and employer changes correctly supersede stale facts rather than accumulating as duplicates.
- Third-person relationship extraction: `"Sarah's manager is Dave"` now produces a directed knowledge graph edge rather than being silently dropped.
- Verb-based contradiction patterns: `"lives in NYC"` is correctly superseded by `"moved to Amsterdam"` across sessions.
- Dedup tokenizer now preserves 2-character tokens (`go`, `js`, `ai`, `ml`) — fixes false-positive deduplication of short tech terms that were previously collapsed.
- `progressive_context()` renamed from the conflicting `format_context()` in the graph module — removes import collision with the runtime's own `format_context`.

### Changed

- `Soul.birth()`, `Soul.awaken()`, and `Soul.birth_from_config()` now accept an `engine` keyword argument (`CognitiveEngine | Callable | Literal["auto"] | None`). Passing a bare callable is automatically wrapped; `"auto"` resolves the best available adapter from installed packages.
- `Identity.bonded_to` is deprecated in favour of `bonds: list[BondTarget]`. Existing `.soul` files round-trip cleanly via auto-migration.

---

## [0.2.4] — 2026-03-19

- Version bump, whitepaper update (reincarnation and archival memory working).
- Rubric-based self-evaluation for skills and learning events.
- Community fix: dedup tokenizer short-token false positives (PR #109).

---

## [0.2.3] — 2026-03-05

- Initial public release on GitHub.
- 1,189 tests, spec + runtime two-layer architecture.
- MCP server (12 tools, 3 resources), 15-command CLI.
- Empirical validation: 20/20 multi-judge benchmark, head-to-head vs. Mem0.
- Soul Health Score framework (7 dimensions, SHS 90.2/100).
