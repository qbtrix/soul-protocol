# Changelog

All notable changes to soul-protocol are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **Density-driven focus** — `SoulState.focus` is now computed from a sliding window of recent interactions instead of being a static default. `Biorhythms` gains `focus_window_seconds` (default 1 hour), `focus_high_threshold` (default 3), and `focus_max_threshold` (default 10). With defaults: 0 interactions in window → `low`, 1-2 → `medium`, 3-9 → `high`, 10+ → `max`. A new `recent_interactions: list[datetime]` field on `SoulState` carries the rolling window.
- **Manual focus lock** — `SoulState.focus_override` (`str | None`) pins focus to a fixed level, bypassing the density calc. Set via `soul.feel(focus="max")` (or `manager.update(focus="max")`). Clear with `soul.feel(focus="auto")` to re-enable density-driven focus.
- **`soul feel --focus`** CLI flag — set focus to `low`/`medium`/`high`/`max`/`auto`.
- **MCP `soul_feel` `focus` parameter** — same surface for MCP clients.
- **`Soul.recompute_focus(now=None)`** — public method to refresh focus before reading state, used by CLI status display and MCP `soul_state` so stale values never leak into a status check.

### Changed

- `StateManager.on_interaction` now appends timestamps to `recent_interactions` and recomputes focus on every call.
- `StateManager.reset()` clears `focus_override` and `recent_interactions` along with the existing fields.

---

## [0.3.1] -- 2026-04-14

### Added

- **Org-level event journal** — append-only event log with SQLite WAL backend, atomic `seq` allocation, and opportunistic hash-chain for tamper evidence. `EventEntry`, `Actor`, and `DataRef` spec types land in `soul_protocol.spec`. Journal entries flow through the org layer for audit and replay. (#165, #172)
- **Decision traces** — three new event types (`agent.proposed`, `human.corrected`, `decision.graduated`) with `causation_id` chaining so a correction links back to the proposal that triggered it. Helpers for building a trace, querying by chain, and clustering recurring correction patterns. This is the core moat — the graduation from "the agent guessed" to "the human decided, and here's the receipt." (#168)
- **Retrieval router + credential broker** — Zero-Copy data federation for the org layer. Router resolves a `DataRef` against registered adapters, broker scopes credentials per source and fails closed with an audit event on any denial. No data is copied into the org boundary; only the receipt is. (#169)
- **`soul org` CLI** — `init`, `status`, and `destroy` commands to bootstrap an org, inspect its current state (root agent, journal head, adapter registry), and tear it down cleanly. `destroy` archives the org to `~/.soul-archives/` before wiping so nothing is ever truly lost on an accident. (#167, #170)
- **Root Agent** — the governance-only agent that sits above the org. Three-layer undeletability (storage-level guard on the file, protocol-level guard in the journal, CLI-level refusal to delete) makes it structurally impossible to remove by accident. Can propose, cannot execute — by design. (#170)
- **Default archives directory** at `~/.soul-archives/` as a sibling of the org directory so `soul org destroy` archives survive a wipe of the org dir itself.
- **`MemoryEntry.scope` + `match_scope` helper** — scope tags on memories with a matcher that uses the spec-level grammar (`org:*`, `agent:<id>`, `session:<id>`, etc.). Recalls can now filter by scope without reaching into tier internals. (#162)
- **`RetrievalTrace` receipt** — every recall now produces a trace with the query, candidate set, rerank decisions, and final selection. Exposed at runtime via `Soul.last_retrieval` so callers can introspect why a given memory surfaced. (#161)
- **Bundled role archetype templates** — Arrow, Flash, Cyborg, and Analyst templates ship with the package. `load_template()` loads them by name, and the new `soul template` CLI lists and instantiates them. (#163)
- **`SOUL_USERS_DIR` env var + improved `--users-dir` default** — user souls now nest under `--data-dir` by default (so `soul org init --data-dir /tmp/foo` keeps founder souls in `/tmp/foo/users/` instead of the real `~/.soul/users/`). The `SOUL_USERS_DIR` env var overrides without a flag, and an explicit `--users-dir` overrides both. The pre-v0.3.1 behavior of always writing to `~/.soul/users/` (regardless of `--data-dir`) silently polluted home directories during CI runs and isolated demos.
- **Framework-agnostic Org Journal Spec** at `docs/org-journal-spec.md` so other implementations can target the same wire format without reading the Python source. (#164)
- **Manual testing guide** at `docs/manual-testing.md` for org-layer flows that are awkward to cover in unit tests. (#164)

### Changed

- Architecture doc trimmed — org-layer detail moved to the dedicated spec so `docs/architecture.md` stays focused on the soul runtime. (#164)
- Doc examples neutralized — replaced PocketPaw-specific wording so the docs land cleanly for anyone using the protocol from their own stack. (#171)

### Fixed


- Bare `pip install soul-protocol` now produces a working `soul` CLI. The CLI's required dependencies (`click`, `rich`, `pyyaml`, `cryptography`) have moved from the `[engine]` extra into base `dependencies`, so `soul --help` no longer raises `ImportError` on a minimal install. The `[engine]` extra is kept as an empty backwards-compat alias so existing `pip install soul-protocol[engine]` pins continue to resolve. (#173, fixes #157)
- `smart_recall` now populates `Soul.last_retrieval` with a `RetrievalTrace` receipt. The original #161 instrumentation covered `recall()` only because `smart_recall` was not on dev at the time; this closes the gap. The trace carries `source="soul.smart"` and metadata flags that record whether rerank ran.
- `match_scope` is now bidirectional containment: a caller with scope `org:sales:leads` matches a memory tagged `org:sales:*` (and vice versa). The previous asymmetric behaviour made bundled archetypes' core memories invisible to agents installed from them. The fix makes the glob-style `default_scope` in Arrow, Flash, Cyborg, and Analyst actually functional out of the box. The old one-way variant is preserved as `match_scope_strict`.

---

## [0.3.0] -- 2026-04-09

### Added
- **Dream cycle** — `Soul.dream()` for offline batch memory consolidation. Reviews accumulated episodes to detect topic clusters (Jaccard token overlap), extract recurring procedures (action signature frequency), detect behavioral trends (topic drift over time), consolidate knowledge graph (merge duplicate entities, prune expired edges), and synthesize cross-tier insights (episodes → procedural memories, behavioral patterns → OCEAN evolution proposals). No LLM required — all heuristic-based.
- `soul dream` CLI command with `--since`, `--no-archive`, `--no-synthesize`, `--dry-run`, `--json` flags. `--dry-run` previews the full report without any destructive mutations so you can see what a cycle would change before committing.
- `DreamReport` dataclass with topic clusters, detected procedures, behavioral trends, graph consolidation stats, evolution insights, and a `dry_run` flag on the report itself.
- **Smart recall** — `Soul.smart_recall()` for LLM-reranked memory retrieval. Fetches a larger candidate pool via heuristic recall, then optionally uses the `CognitiveEngine` to pick the most contextually relevant entries. Opt-in via `MemorySettings.smart_recall_enabled` (default `False`) or a per-call `enabled=` override. Hardened prompt injection defense: memory content is sanitized (angle brackets stripped, response-marker strings redacted) and isolated inside a `BEGIN/END MEMORIES` fence so adversarial memories can't hijack the rerank. 30-second hard timeout on the LLM call so a hung engine can't stall the recall hot path — falls back cleanly to heuristic order on timeout, parse error, or engine failure.
- **Significance short-circuit** — `observe()` now skips entity extraction (step 5) and self-model update (step 6) when an interaction scores below the significance threshold AND fact extraction finds nothing. Saves two LLM calls per trivial interaction. Gated by `MemorySettings.skip_deep_processing_on_low_significance` (default `True`) with an escape hatch (`False`) for callers that need guaranteed extraction. The gate re-checks `significant` after step 4b fact-based promotion so meaningful short messages still get the full pipeline.
- **`soul remember --type`** — the CLI command now accepts `--type/-t episodic|semantic|procedural` to pick which tier a memory lands in. Fixes a long-standing gap where the runtime `Soul.remember()` supported tier selection but the CLI always defaulted to semantic, silently dropping events that callers intended as episodic.

### Changed
- `MemorySettings` gains `smart_recall_enabled` (bool, default False) and `skip_deep_processing_on_low_significance` (bool, default True). Default values preserve previous behavior — no breaking change for existing souls.
- `_dedup_semantic` in the dream cycle now soft-deletes duplicates via `superseded_by` instead of removing them from the underlying dict. Preserves an audit trail and honors any future side effects added to `SemanticStore.remove()`.
- `_count_archivable` in dry-run mode matches `archive_old_memories` exactly (48-hour cutoff, archived filter, min-3 guard) so dry-run counts don't drift from real-run counts.

### Fixed
- CLI `remember` previously dropped `--type` silently because the option didn't exist. Tools passing the flag (like the PocketPaw workspace soul-sync hook) were failing without surfacing the error, leaving episodic tiers empty for extended periods.

### Docs
- `docs/cli-reference.md` now has full sections for `soul remember` and `soul recall` — these were missing from the reference entirely. Includes memory tier guide and full option tables.
- `skills/soul-protocol/SKILL.md` updated with episodic and procedural examples plus a tier guide for agents.
- `docs/getting-started.md` notes the runtime `type` parameter on `soul.remember()` for users reading the Python walkthrough.
- `README.md` (kb-go workspace) adds a "Pairing with Soul Protocol" guide explaining when to reach for each tool and how to bridge them in an agent pipeline.

### Tests
- 2062 tests passing (up from 2010). New test classes: `TestDreamerDryRun`, `TestSignificanceShortCircuit`. New test files: `test_dream.py`, `test_rerank.py`. New CLI tests for `remember --type` with every tier plus invalid-value rejection.

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
