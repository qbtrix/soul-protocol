# Changelog

All notable changes to soul-protocol are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.2.9] -- 2026-03-29

### Added
- **Progressive recall** — `recall(progressive=True)` returns primary entries with full content + overflow entries with L0 abstract. Uses `model_copy()` to avoid mutating store objects. `is_summarized` runtime marker on overflow entries
- **Archival memory** — `MemoryManager.archive_old_memories()` compresses episodic entries older than 48h into `ConversationArchive`. Archived entries filtered from recall. Archives persist through export/awaken
- **Auto-consolidation** — `observe()` auto-triggers archival + reflection every `consolidation_interval` (default 20) interactions. `interaction_count` persisted in `SoulConfig`
- **Eternal storage wiring** — `Soul.archive()` method for IPFS/Arweave archival. `EternalStorageManager.with_mocks()` factory. `eternal=` param on `birth()`/`awaken()`. `export(archive=True)` flag
- **Skill decay** — `Skill.decay(days)` reduces XP by 1 per day inactive, floor at 0, never reduces level. `SkillRegistry.decay_all()` runs at start of each `observe()`
- 33 new tests (1977 → 2010)

### Changed
- Skills XP grants now significance-weighted (5-30 range) instead of flat +10 per entity extraction
- Recall fetches `limit * 2` candidates in progressive mode for better overflow quality
- `archived: bool` field on `MemoryEntry` for tracking compressed memories
- `consolidation_interval: int` field on `MemorySettings` (default 20)
- `interaction_count: int` field on `SoulConfig` for persistence

---

## [0.2.8] -- 2026-03-27

### Added
- `soul health` CLI — audit memory tiers, duplicates, orphan nodes, bond sanity
- `soul cleanup` CLI — remove dupes, stale evals, orphans (--dry-run, --auto)
- `soul repair` CLI — reset energy/bond, rebuild graph, clear evals/skills
- `soul_skills`, `soul_evaluate`, `soul_learn`, `soul_evolve`, `soul_bond` MCP tools (23 total)
- `soul recall --full` flag for complete memory content (no truncation)
- `soul recall --json` flag for machine-readable output
- `soul_forget`, `soul_edit_core`, `soul_health`, `soul_cleanup` MCP tools
- Biorhythms documentation with always-on vs companion usage guide
- Always-On Worker preset in configuration docs

### Changed
- Default biorhythms now always-on (energy_drain_rate=0, social_drain_rate=0, tired_threshold=0)
- Companion souls opt-in to drain via explicit biorhythm config

### Fixed
- Evolution pending mutations now persist across save/reload cycles
- Previously, proposed mutations were lost on export/awaken (in-memory only)

---

## [0.2.7] — 2026-03-26

### Fixed

- **Bond system** — `context_for()` now passes actual `bond_strength` to memory recall instead of always defaulting to 100.0. Bond score now genuinely influences which memories surface in context.
- **Evolution pipeline** — `observe()` now calls `evaluate()` to build evaluation history. Previously, evaluation history was always empty so evolution triggers never fired and OCEAN personality was stuck at defaults forever.
- **Entity extraction** — added topic extraction patterns for natural speech (`"I work on X"`, `"I'm a Y"`, `"we're building Z"`). Captures concepts from real conversations that lack capitalized proper nouns or hardcoded tech names. Regex bounded to 5 words with trailing stop-word trimming.
- **Heuristic evaluator calibration** — recalibrated scoring functions so solid technical conversations score ~0.65–0.80 instead of ~0.33. Completeness threshold lowered to 20 words, relevance uses user tokens as denominator, specificity counts 6+ char words. Evolution trigger thresholds adjusted to 0.55 for heuristic mode.

### Added

- **Skills persistence** — `SkillRegistry` now serialized in `SoulConfig` and restored on `awaken()`. Learned skills survive export/import cycles.
- **Evaluation history persistence** — `Evaluator._history` now serialized in `SoulConfig` and restored on `awaken()`. Evaluation streaks accumulate across sessions.
- **18 real-world e2e tests** — new `test_e2e_real_world.py` with 8 scenarios simulating realistic multi-turn human conversations: developer onboarding, personal bonding, evolution triggers, self-model emergence, bond-filtered recall, full lifecycle persistence, mixed conversation, and evolution mutation proposals. (#143)

---

## [0.2.6] — 2026-03-24

### Added

- **MCP LCM context tools** — 5 new MCP tools expose Lossless Context Management through the soul server: `soul_context_ingest`, `soul_context_assemble`, `soul_context_grep`, `soul_context_expand`, `soul_context_describe`. Per-soul in-memory SQLite stores, CognitiveEngine auto-wired to compactors. (#138)
- **CLI runtime parity** — 13 new CLI commands for full feature parity with the Python API: `observe`, `reflect`, `feel`, `prompt`, `forget`, `edit-core`, `evolve`, `evaluate`, `learn`, `skills`, `bond`, `events`, `context`. Total: 34 commands. (#138)
- **Soul directory auto-detect** — MCP server now auto-detects `.soul/` in the working directory or `~/.soul/` when no `SOUL_DIR`/`SOUL_PATH` env var is set. Uses `Path.cwd()` for all install modes. Logs empty directory fallthrough. (#136)
- **Docs refresh** — updated getting-started, cognitive-engine, integrations, and memory-architecture guides for v0.2.5 features. (#137)

### Fixed

- **Dedup containment coefficient** — enriched facts (where a short fact is a subset of a longer version) now correctly land in MERGE range instead of CREATE. Containment coefficient (`intersection / min-set * 0.75`) used as floor for Jaccard, with `min_size >= 3` guard against spurious matches. (#135)
- **CI dependency resolution** — `dspy` and `litellm` extras emptied to prevent `uv sync` from failing on unresolvable transitive dependencies. Both can still be installed manually. (#136)
- **MCP test isolation** — autouse fixture now monkeypatches CWD and `Path.home()` to prevent auto-detect from loading real souls during tests. (#136)

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
