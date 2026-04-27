# Soul Protocol — Gap Analysis

> Vision docs vs implementation reality. What's built, what's missing, and what's beyond the original spec.

**Date:** 2026-03-06
**Codebase version:** 0.2.2 (dev branch, commit eaaeebd)

---

## 1. Executive Summary

Soul Protocol has implemented roughly **65-70% of the vision** described across the four DSP specification documents. The core experience loop --- birth a soul, give it a personality, observe interactions, remember facts, recall memories, save and migrate --- is fully functional. The implementation went significantly beyond the vision in several areas (psychology-informed memory, cognitive engine, self-model emergence) while leaving the entire eternal storage tier and several CLI commands unbuilt.

### Key Strengths

- **Memory system is more sophisticated than the vision.** The implementation added ACT-R activation decay, somatic markers, significance gating, spreading activation, and a self-model --- none of which were in the original spec.
- **Full parse/export pipeline.** All four input formats (md, yaml, json, .soul) are supported with round-trip fidelity.
- **Cognitive Engine pattern.** The `CognitiveEngine` protocol allows LLM-enhanced cognition while the `HeuristicEngine` provides zero-dependency fallback --- a clean architecture not in the vision.
- **MCP server.** 10 tools, 3 resources, 2 prompts for AI agent integration. Not in any vision doc.
- **Solid test coverage.** 981 tests across 56 test files.

### Key Gaps

- **Eternal storage is entirely unbuilt.** No IPFS, Arweave, or blockchain integration. Local-only.
- **Lifecycle is incomplete.** Only `BORN`, `ACTIVE`, `DORMANT`, `RETIRED` exist. The vision specifies `UNBORN`, `ESSENCE`, `REINCARNATED`, and a full retirement-with-farewell flow.
- **Skills/XP system is missing.** The vision describes leveled skills with XP progression. Zero implementation.
- **No vector/embedding search.** Recall uses token overlap and ACT-R heuristics, not semantic vectors.
- **No memory compression/consolidation pipeline.** The SimpleMem-inspired summarization, deduplication, and pruning are not implemented beyond basic reflection.
- **Bond system is minimal.** `bonded_to` is a string field with no `bondStrength` tracking or evolution.
- **No integration adapters.** The vision describes LangChain, Vercel AI SDK, and raw API adapters. None exist.
- **JSON Schema is not published.** The vision describes a formal `$schema` at `soul-protocol.org/schema/v1.json`. The `schemas/` directory exists but no validation schema is shipped.

---

## 2. Feature Matrix

### 2.1 Identity System

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| Soul name | DSP.md | DONE | `types.py` (Identity) | Required field |
| Archetype | DSP.md | DONE | `types.py` (Identity) | Optional string |
| DID generation | DSP.md | DONE | `identity/did.py` | `did:soul:{name}-{hex}` format |
| Birth certificate | DSP.md | NOT STARTED | -- | Vision has bornAt, birthplace, witnesses, genesisHash; implementation has none of these |
| Bond (bonded_to) | DSP.md | PARTIAL | `types.py` (Identity) | String field only. No bondStrength, bondedAt, or bond evolution |
| Origin story | DSP.md, IMPL-SPEC | DONE | `types.py` (Identity) | `origin_story` field |
| Prime directive | IMPL-SPEC | DONE | `types.py` (Identity) | `prime_directive` field |
| Core values | DSP.md | DONE | `types.py` (Identity) | List of strings, wired into significance scoring |
| Public key / crypto identity | DSP.md | NOT STARTED | -- | Vision has `publicKey` on soul.json; not implemented |
| Human DID (did:human:) | DSP.md | NOT STARTED | -- | `bonded_to` is freeform string, not DID-format |

### 2.2 DNA / Personality

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| OCEAN personality model | DSP.md, IMPL-SPEC | DONE | `types.py` (Personality) | 5 traits, 0.0-1.0, defaults to 0.5 |
| Communication style | IMPL-SPEC | DONE | `types.py` (CommunicationStyle) | warmth, verbosity, humor_style, emoji_usage |
| Biorhythms | IMPL-SPEC | DONE | `types.py` (Biorhythms) | chronotype, social_battery, energy_regen_rate |
| DNA-to-system-prompt | DSP.md, IMPL-SPEC | DONE | `dna/prompt.py` | Includes OCEAN, comm style, state, core memory |
| DNA-to-markdown | IMPL-SPEC | DONE | `dna/prompt.py` | `dna_to_markdown()` for export |
| dna.md in .soul file | DSP.md | DONE | `export/pack.py` | Included in zip archive |
| Dynamic preferences (`{{DYNAMIC_PREFERENCES}}`) | DSP.md | NOT STARTED | -- | Vision shows template variables in dna.md; not implemented |

### 2.3 Memory System

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| Working memory (volatile) | MEM-ARCH | NOT STARTED | -- | Vision describes session context buffer; runtime manages this externally |
| Core memory (always loaded) | MEM-ARCH, DSP.md | DONE | `memory/core.py` | persona + human fields, self-editable |
| Self-editing core memory | MEM-ARCH | DONE | `soul.py` (`edit_core_memory`) | Append-based editing via MemoryManager |
| Episodic memory | DSP.md, MEM-ARCH | DONE | `memory/episodic.py` | Full store with add, search, remove |
| Semantic memory | DSP.md, MEM-ARCH | DONE | `memory/semantic.py` | Fact store with dedup |
| Procedural memory | DSP.md, MEM-ARCH | DONE | `memory/procedural.py` | How-to store |
| Knowledge graph | MEM-ARCH | DONE | `memory/graph.py` | Entities + directed edges, serializable |
| Archival memory | MEM-ARCH | NOT STARTED | -- | Vision describes compressed conversation transcripts; not implemented |
| Memory recall (keyword) | MEM-ARCH | DONE | `memory/recall.py`, `memory/search.py` | Token overlap + ACT-R activation |
| Memory recall (vector/embedding) | MEM-ARCH | NOT STARTED | -- | SearchStrategy protocol exists but no embedding implementation |
| Memory consolidation (merge/prune) | MEM-ARCH | PARTIAL | `memory/manager.py` (`consolidate`) | Only via CognitiveEngine reflection; no automatic scheduled consolidation |
| Memory compression (SimpleMem-style) | MEM-ARCH | NOT STARTED | -- | No summarization, no recursive consolidation |
| Importance-based pruning | MEM-ARCH | NOT STARTED | -- | `importance_threshold` in settings but no pruning logic |
| Semantic deduplication | MEM-ARCH | PARTIAL | `memory/manager.py` | Token-overlap dedup in `extract_facts`; no embedding-based dedup |
| Memory forget/remove | DSP.md, MEM-ARCH | DONE | `soul.py`, `memory/manager.py`, `cli/main.py` | Remove by query/entity/timestamp/id. CLI is dry-run by default; `--apply` writes a `.soul.bak`. `--id` added 2026-04-27 for surgical single-id deletion (audited via `Soul.forget_one`). |
| User-driven memory supersede | -- | DONE | `soul.py`, `memory/manager.py`, `cli/main.py` | 2026-04-27. `Soul.supersede(old_id, new_content, ...)` writes new entry, sets `old.superseded_by = new.id`, appends to `supersede_audit`. Old entry is filtered from search by default but kept on disk for provenance. CLI: `soul supersede`. |
| Hybrid inline+external storage | MEM-ARCH | NOT STARTED | -- | No vector DB, no external storage links |
| Embedding interface | MEM-ARCH | PARTIAL | `memory/strategy.py` | `SearchStrategy` protocol exists; no embedding providers |
| Storage backend interface | MEM-ARCH | DONE | `storage/protocol.py` | Protocol defined but only file backend implemented |
| Memory in .soul file | MEM-ARCH, DSP.md | DONE | `export/pack.py`, `export/unpack.py` | All tiers serialized into zip |
| Fact conflict resolution | -- | DONE | `memory/manager.py` | v0.2.2 feature, superseded_by field |
| Fact extraction (heuristic) | -- | DONE | `memory/manager.py` | 18+ regex patterns |
| Entity extraction | -- | DONE | `memory/manager.py` | Tech terms + proper noun detection |

### 2.4 State / Feelings

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| Mood enum | DSP.md | DONE | `types.py` (Mood) | 8 moods (vision has 6, implementation adds satisfied + concerned) |
| Energy (0-100) | DSP.md | DONE | `types.py` (SoulState) | Float with clamping |
| Focus levels | DSP.md | DONE | `types.py` (SoulState) | String: low/medium/high |
| Social battery (0-100) | DSP.md | DONE | `types.py` (SoulState) | Float with clamping |
| Last interaction timestamp | DSP.md | DONE | `types.py` (SoulState) | Updated on each observe() |
| Streak tracking | DSP.md | NOT STARTED | -- | Vision shows `streak: 7`; not implemented |
| `feel()` method | DSP.md | DONE | `soul.py`, `state/manager.py` | Delta-based updates |
| State serialization | DSP.md | DONE | `export/pack.py` | state.json in .soul file |
| Mood inertia (EMA smoothing) | -- | DONE | `state/manager.py` | v0.3 feature, not in vision |
| Sentiment-driven mood | -- | DONE | `state/manager.py` | SomaticMarker -> Mood mapping |

### 2.5 Evolution

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| Evolution modes | DSP.md, IMPL-SPEC | DONE | `types.py` (EvolutionMode) | disabled, supervised, autonomous |
| Mutation proposal | DSP.md | DONE | `evolution/manager.py` | With immutability guards |
| Mutation approval/rejection | DSP.md | DONE | `evolution/manager.py` | For supervised mode |
| Auto-apply (autonomous mode) | DSP.md | DONE | `evolution/manager.py` | Auto-approved on proposal |
| Evolution history | DSP.md | DONE | `types.py` (EvolutionConfig) | List of Mutation records |
| Mutable/immutable trait config | IMPL-SPEC | DONE | `types.py` (EvolutionConfig) | With top-level category guards |
| Mutation rate | DSP.md | PARTIAL | `types.py` (EvolutionConfig) | Field exists but not used in trigger logic |
| Automatic evolution triggers | DSP.md | NOT STARTED | `evolution/manager.py` | `check_triggers()` is a no-op placeholder |
| `requiresApproval` per-mutation | DSP.md | NOT STARTED | -- | Approval is mode-based, not per-mutation |

### 2.6 Lifecycle

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| UNBORN state | DSP.md | NOT STARTED | -- | Vision has it; implementation starts at BORN |
| BORN / ALIVE state | DSP.md | DONE | `types.py` (LifecycleState) | Called BORN and ACTIVE |
| DORMANT state | DSP.md | DONE | `types.py` (LifecycleState) | Defined but no transition logic |
| RETIRING state | DSP.md | NOT STARTED | -- | Vision has a transitional retiring state |
| ESSENCE state | DSP.md | NOT STARTED | -- | "Form dissolved, essence preserved" |
| REINCARNATED state | DSP.md | NOT STARTED | -- | No reincarnation system |
| `Soul.birth()` | DSP.md | DONE | `soul.py` | Async classmethod with full config |
| `Soul.awaken()` | DSP.md | DONE | `soul.py` | From .soul file, directory, json, yaml, md |
| `Soul.retire()` | DSP.md | DONE | `soul.py` | With preserve_memories option |
| `Soul.reincarnate()` | DSP.md | NOT STARTED | -- | Not implemented |
| `Soul.fromMarkdown()` | DSP.md | DONE | `soul.py` | `from_markdown()` classmethod |
| `Soul.migrate()` | DSP.md | PARTIAL | `soul.py` | `export()` creates .soul file; no `migrate()` method per se |
| Age calculation | DSP.md | PARTIAL | -- | `born` field exists; no `age`/`ageInDays` properties |

### 2.7 Eternal Storage

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| Local .soul file | ETERNAL | DONE | `export/pack.py`, `storage/file.py` | Zip archive format |
| IPFS archiving | ETERNAL | NOT STARTED | -- | No IPFS integration |
| IPFS pinning services | ETERNAL | NOT STARTED | -- | No Pinata/web3.storage |
| Arweave archiving | ETERNAL | NOT STARTED | -- | No Arweave integration |
| Blockchain birth registration | ETERNAL | NOT STARTED | -- | No smart contract |
| Soul recovery from external | ETERNAL | NOT STARTED | -- | Only local recovery |
| Manifest with eternal links | ETERNAL | NOT STARTED | -- | SoulManifest exists but has no eternal storage fields |
| Encryption at rest | ETERNAL | DONE | `crypto/encrypt.py` | Fernet + PBKDF2, but not wired into save/export by default |
| `soul archive` CLI | ETERNAL | NOT STARTED | -- | No archive command |
| `soul recover` CLI | ETERNAL | NOT STARTED | -- | No recovery command |
| Soul discovery (on-chain) | ETERNAL | NOT STARTED | -- | No on-chain queries |

### 2.8 CLI Commands

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| `soul birth` | DSP.md, IMPL-SPEC | DONE | `cli/main.py` | With OCEAN flags, --config, --from-file |
| `soul init` | -- | DONE | `cli/main.py` | Creates .soul/ project folder (beyond vision) |
| `soul inspect` | IMPL-SPEC | DONE | `cli/main.py` | Rich TUI with OCEAN bars, memory, self-model |
| `soul status` | DSP.md, IMPL-SPEC | DONE | `cli/main.py` | Quick view with progress bars |
| `soul export` | IMPL-SPEC | DONE | `cli/main.py` | soul, json, yaml, md formats |
| `soul migrate` | IMPL-SPEC | DONE | `cli/main.py` | SOUL.md to .soul conversion |
| `soul retire` | DSP.md | DONE | `cli/main.py` | With confirmation prompt |
| `soul list` | -- | DONE | `cli/main.py` | Lists saved souls in ~/.soul/ |
| `soul archive` | DSP.md, ETERNAL | NOT STARTED | -- | Arweave archiving command |
| `soul recover` | ETERNAL | NOT STARTED | -- | Recovery from external storage |

### 2.9 Parsers

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| soul.md parser | IMPL-SPEC | DONE | `parsers/markdown.py` | YAML frontmatter + section splitting |
| soul.yaml parser | IMPL-SPEC | DONE | `parsers/yaml_parser.py` | PyYAML + Pydantic validation |
| soul.json parser | IMPL-SPEC | DONE | `parsers/json_parser.py` | Pydantic model_validate_json |
| .soul archive parser | IMPL-SPEC | DONE | `export/unpack.py` | Zip extraction with memory tiers |
| Parser auto-detection | IMPL-SPEC | DONE | `soul.py` (`awaken`) | Routes by file extension |

### 2.10 Integration Adapters

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| LangChain adapter | IMPL-SPEC | NOT STARTED | -- | Vision has langchain.ts |
| Vercel AI SDK adapter | IMPL-SPEC | NOT STARTED | -- | Vision has vercel-ai.ts |
| Raw LLM adapter | IMPL-SPEC | NOT STARTED | -- | Vision has raw.ts |
| `toSystemPrompt()` | DSP.md | DONE | `soul.py`, `dna/prompt.py` | Core integration point |
| `observe()` hook | DSP.md | DONE | `soul.py` | Psychology-informed pipeline |
| `context_for()` | -- | DONE | `soul.py` | Per-turn context block (beyond vision) |

### 2.11 Skills / XP System

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| Skills manifest | DSP.md | NOT STARTED | -- | No skills module |
| XP progression | DSP.md, IMPL-SPEC | NOT STARTED | -- | No XP tracking |
| Skill levels | DSP.md | NOT STARTED | -- | No leveling system |
| Skill config | IMPL-SPEC | NOT STARTED | -- | Vision describes per-skill config |

### 2.12 Encryption / Security

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| AES-256 encryption | ETERNAL | PARTIAL | `crypto/encrypt.py` | Uses Fernet (AES-128-CBC), not AES-256-GCM as spec'd |
| PBKDF2 key derivation | ETERNAL | DONE | `crypto/encrypt.py` | 480,000 iterations |
| Passphrase-based encryption | ETERNAL | DONE | `crypto/encrypt.py` | Salt prepended to ciphertext |
| Encrypted .soul export | ETERNAL | NOT STARTED | -- | encrypt/decrypt functions exist but not wired into pack/unpack |
| Key management | IMPL-SPEC | NOT STARTED | -- | Vision has identity/keys.ts; not implemented |
| Hardware wallet support | ETERNAL | NOT STARTED | -- | Future vision item |

### 2.13 JSON Schema

| Feature | Vision Doc | Status | Files | Notes |
|---------|-----------|--------|-------|-------|
| Published JSON Schema | IMPL-SPEC | NOT STARTED | `schemas/` dir exists | No actual schema file generated |
| `$schema` reference in soul.json | IMPL-SPEC | NOT STARTED | -- | Vision references soul-protocol.org/schema/v1.json |

---

## 3. Architecture Comparison

### 3.1 Vision Package Structure (from DSP-IMPLEMENTATION-SPEC.md)

```
packages/soul-protocol/
  src/
    index.ts
    soul.ts
    types/
      identity.ts, dna.ts, memory.ts, state.ts, evolution.ts
    parsers/
      markdown.ts, yaml.ts, json.ts, archive.ts
    identity/
      did.ts, keys.ts, bond.ts
    dna/
      personality.ts, communication.ts, biorhythms.ts, prompt-generator.ts
    memory/
      core.ts, episodic.ts, semantic.ts, procedural.ts, graph.ts,
      recall.ts, consolidate.ts
    state/
      mood.ts, energy.ts, focus.ts
    evolution/
      mutations.ts, approval.ts, history.ts
    storage/
      interface.ts, local.ts, indexeddb.ts, file.ts, memory.ts
    export/
      pack.ts, unpack.ts
    crypto/
      encrypt.ts, decrypt.ts, keys.ts
    utils/
      embeddings.ts, similarity.ts, validators.ts
  cli/
    commands/
      birth.ts, inspect.ts, migrate.ts, export.ts, status.ts, retire.ts
  adapters/
    langchain.ts, vercel-ai.ts, raw.ts
  schemas/
    v1.json
```

### 3.2 Actual Implementation Structure

```
src/soul_protocol/
  __init__.py              # Public API, version
  soul.py                  # Main Soul class
  types.py                 # ALL models in single file (not split by domain)
  exceptions.py            # Custom exception hierarchy

  cli/
    main.py                # Click CLI (all commands in one file)

  cognitive/               # ** NOT IN VISION **
    engine.py              # CognitiveEngine protocol + HeuristicEngine
    prompts.py             # LLM prompt templates

  crypto/
    encrypt.py             # Fernet + PBKDF2 (encrypt + decrypt combined)

  dna/
    prompt.py              # dna_to_system_prompt + dna_to_markdown

  evolution/
    manager.py             # Single file (vision has 3 files)

  export/
    pack.py                # .soul zip creation
    unpack.py              # .soul zip extraction

  identity/
    did.py                 # DID generation only (no keys.ts, no bond.ts)

  mcp/                     # ** NOT IN VISION **
    server.py              # FastMCP server (10 tools, 3 resources, 2 prompts)

  memory/
    core.py                # CoreMemoryManager
    episodic.py            # EpisodicStore
    semantic.py            # SemanticStore
    procedural.py          # ProceduralStore
    graph.py               # KnowledgeGraph
    manager.py             # MemoryManager facade (1037 lines)
    recall.py              # RecallEngine with ACT-R scoring
    search.py              # Token overlap scoring + tokenizer
    activation.py          # ** NOT IN VISION ** ACT-R activation
    attention.py           # ** NOT IN VISION ** Significance gating
    self_model.py          # ** NOT IN VISION ** Klein's self-concept
    sentiment.py           # ** NOT IN VISION ** Somatic markers
    strategy.py            # ** NOT IN VISION ** Pluggable SearchStrategy

  parsers/
    markdown.py            # soul.md parser
    yaml_parser.py         # soul.yaml parser
    json_parser.py         # soul.json parser

  state/
    manager.py             # Single file (vision has 3 files)

  storage/
    file.py                # FileStorage + save/load convenience functions
    protocol.py            # Storage protocol definition
    memory_store.py        # In-memory storage (testing)
```

### 3.3 Key Structural Differences

| Aspect | Vision | Actual | Assessment |
|--------|--------|--------|------------|
| Language | TypeScript/npm | Python/pip | Deliberate pivot |
| Types organization | 5 separate files | 1 monolithic `types.py` | Works at current scale |
| CLI structure | 6 command files | 1 `main.py` with Click | Simpler, works fine |
| State management | 3 files (mood, energy, focus) | 1 `manager.py` | Appropriate consolidation |
| Evolution | 3 files (mutations, approval, history) | 1 `manager.py` | Appropriate consolidation |
| Identity | 3 files (did, keys, bond) | 1 `did.py` | Missing: keys, bond |
| Memory modules | 7 files | 14 files | Implementation is richer |
| Adapters | 3 adapter files | 0 adapters | Major gap |
| Cognitive layer | Not in vision | 3 files | Beyond vision |
| MCP server | Not in vision | 1 file (444 lines) | Beyond vision |
| Storage backends | 4 backends | 3 backends | Missing: IndexedDB (browser) |

---

## 4. What's Beyond Vision (Built but Not in Docs)

These features exist in the implementation but were not described in any of the four vision documents.

### 4.1 Psychology-Informed Memory (v0.2.0)

The memory system implements concepts from cognitive science papers:

| Feature | Theory Source | Implementation |
|---------|-------------|----------------|
| Somatic markers | Damasio's Somatic Marker Hypothesis | `memory/sentiment.py` - valence/arousal/label on every memory |
| Significance gating | LIDA architecture | `memory/attention.py` - novelty + emotional_intensity + goal_relevance |
| ACT-R activation decay | Anderson's ACT-R | `memory/activation.py` - power-law decay over access timestamps |
| Spreading activation | ACT-R spreading | `memory/activation.py` - query relevance as associative strength |
| Emotional boost | Flashbulb memory effect | `memory/activation.py` - high-arousal memories recalled more easily |

**Files:** `memory/sentiment.py` (295 lines), `memory/attention.py` (105 lines), `memory/activation.py` (172 lines)

### 4.2 Cognitive Engine / Heuristic Engine (v0.2.1)

A dual-mode processing architecture:

- **`CognitiveEngine`** protocol: single `async think(prompt: str) -> str` method that consumers implement with any LLM
- **`HeuristicEngine`**: zero-dependency fallback that routes task-tagged prompts to heuristic functions
- **`CognitiveProcessor`**: internal orchestrator that delegates sentiment, significance, fact extraction, entity extraction, self-reflection, and consolidation to either engine

**File:** `cognitive/engine.py` (480 lines)

### 4.3 Self-Model Emergence (v0.2.0, enhanced v0.3.0)

Based on Klein's self-concept theory, the soul builds a model of who it is from observation:

- **Emergent domain discovery**: domains are not hardcoded but discovered from interaction content
- **Seed domains**: 6 bootstrap domains (technical_helper, creative_writer, etc.) that can be replaced
- **Dynamic keyword expansion**: domain vocabularies grow as the soul encounters related content
- **Confidence curves**: diminishing returns formula approaching 0.95 as evidence accumulates
- **Self-model in system prompt**: top 3 self-images injected into LLM context

**File:** `memory/self_model.py` (547 lines)

### 4.4 Pluggable Search Strategy (v0.2.2)

The `SearchStrategy` protocol allows consumers to replace token-overlap search with embeddings, vector DB queries, or any custom scoring:

```python
class SearchStrategy(Protocol):
    def score(self, query: str, content: str) -> float: ...
```

**File:** `memory/strategy.py` (42 lines)

### 4.5 MCP Server (v0.3.2)

A FastMCP server exposing the soul as an MCP service:

- **10 tools**: soul_birth, soul_observe, soul_remember, soul_recall, soul_reflect, soul_state, soul_feel, soul_prompt, soul_save, soul_export
- **3 resources**: soul://identity, soul://memory/core, soul://state
- **2 prompts**: soul_system_prompt, soul_introduction
- Single-client design with lifespan-based startup from `SOUL_PATH` env var

**File:** `mcp/server.py` (444 lines)

### 4.6 Two-Layer Architecture

The codebase separates "engine-level" processing (requires LLM or heuristic) from "core-level" data models and storage. This manifests as:

- **Core layer**: `types.py`, `identity/`, `memory/core.py`, `memory/episodic.py`, `memory/semantic.py`, `memory/procedural.py`, `memory/graph.py`, `export/`, `storage/` -- pure data, no intelligence
- **Engine layer**: `cognitive/`, `memory/activation.py`, `memory/attention.py`, `memory/self_model.py`, `memory/sentiment.py`, `memory/strategy.py` -- intelligence and processing

### 4.7 Context-for-Turn API (v0.3.0)

`soul.context_for(user_input)` generates a per-turn context block with live state and relevant memories, designed for agentic systems that compress or truncate conversation history.

### 4.8 General Events (Conway Hierarchy, v0.2.2)

Episodes cluster into GeneralEvent themes following Conway's Self-Memory System. Created during reflection/consolidation, linking episodic memories to higher-level narrative themes.

### 4.9 Fact Conflict Resolution (v0.2.2)

When a new fact contradicts an existing one (same template prefix, different value), the old fact is marked `superseded_by` rather than deleted, preserving history.

### 4.10 Custom Exception Hierarchy (v0.3.2)

```
SoulProtocolError
  SoulFileNotFoundError
  SoulCorruptError
  SoulExportError
  SoulRetireError
```

### 4.11 Sentiment-Driven Mood with EMA Inertia

Mood changes are driven by detected sentiment but smoothed via exponential moving average (alpha=0.4). A single mild message cannot flip the mood -- accumulated signal is required.

---

## 5. Priority Roadmap

### P0: Critical for Launch

These items are required before soul-protocol can be considered "v1.0":

| Item | Effort | Depends On |
|------|--------|------------|
| **Encrypted .soul export** -- wire crypto into pack/unpack | S | crypto/encrypt.py exists |
| **Skills/XP system** -- basic skill tracking and levels | M | New module |
| **Birth certificate** -- bornAt, birthplace, witnesses, genesisHash | S | types.py change |
| **Bond model** -- bondStrength, bondedAt, bond evolution | S | types.py change |
| **JSON Schema** -- generate from Pydantic models, publish | S | schemas/ dir exists |
| **Lifecycle completeness** -- ESSENCE, REINCARNATED states | M | types.py + soul.py |
| **`soul.age` / `soul.age_in_days`** -- computed properties | S | soul.py |
| **Automatic evolution triggers** -- replace check_triggers no-op | M | evolution/manager.py |

### P1: Important Differentiators

These items would significantly strengthen the protocol's value proposition:

| Item | Effort | Depends On |
|------|--------|------------|
| **Embedding-based recall** -- implement a SearchStrategy with sentence-transformers or OpenAI | M | memory/strategy.py exists |
| **Memory consolidation pipeline** -- scheduled summarization + pruning | L | memory/manager.py |
| **Memory compression** -- SimpleMem-style recursive consolidation | L | New module |
| **Archival memory tier** -- conversation transcript storage with summaries | M | New store |
| **Integration adapters** -- at least one reference adapter (e.g., for litellm or any-llm) | M | New module |
| **Streak tracking** -- consecutive interaction day counting | S | state/manager.py |
| **Working memory interface** -- session context buffer tracking | M | New module |

### P2: Nice to Have

| Item | Effort | Depends On |
|------|--------|------------|
| **IPFS archiving** -- web3.storage or Pinata integration | L | New module, optional dep |
| **Temporal knowledge graph** -- time-aware relationships (Graphiti-style) | L | memory/graph.py |
| **Dynamic preferences in dna.md** -- template variable injection | S | dna/prompt.py |
| **Multi-format CLI export** -- `soul export --format` already exists but could expand | S | cli/main.py |
| **soul archive CLI** -- archive to IPFS/Arweave | M | P2 deps |
| **soul recover CLI** -- recovery from external storage | M | P2 deps |

### P3: Future Vision

| Item | Effort | Depends On |
|------|--------|------------|
| **Arweave permanent storage** -- pay-once archiving | L | arweave SDK |
| **On-chain birth registration** -- Base L2 smart contract | XL | Solidity, ethers |
| **Multi-device sync** -- cloud-based soul synchronization | XL | Backend infra |
| **Soul transfer mechanism** -- ownership transfer | L | Blockchain |
| **Hardware wallet support** -- HSM key storage | M | Crypto infra |
| **IndexedDB backend** -- browser storage (only relevant if JS SDK exists) | M | JS port |
| **Neo4j backend** -- production graph database | M | neo4j driver |
| **Vector DB backends** -- Chroma, Pinecone, Qdrant | M per backend | embedding pipeline |

---

## 6. Metrics

### 6.1 Codebase Size

| Metric | Count |
|--------|-------|
| Python source files | 46 |
| Source lines of code | 7,086 |
| Test files | 34 |
| Test lines of code | 7,216 |
| Test functions | 453 |
| Source-to-test ratio | 1:1.02 (excellent) |

### 6.2 Module Size Breakdown

| Module | Files | Lines | Notes |
|--------|-------|-------|-------|
| memory/ | 14 | 2,860 | Largest module -- core of the protocol |
| cognitive/ | 3 | 590 | Engine + prompts |
| cli/ | 2 | 488 | Rich TUI inspect/status |
| mcp/ | 2 | 448 | FastMCP server |
| state/ | 2 | 186 | Manager + init |
| storage/ | 4 | 341 | File + protocol + memory |
| evolution/ | 2 | 200 | Manager + init |
| dna/ | 2 | 161 | Prompt generation |
| export/ | 3 | 162 | Pack + unpack |
| parsers/ | 4 | 217 | md, yaml, json |
| identity/ | 2 | 36 | DID generation only |
| crypto/ | 2 | 92 | Encrypt/decrypt |
| types.py | 1 | 313 | All Pydantic models |
| soul.py | 1 | 681 | Main Soul class |
| exceptions.py | 1 | 45 | Error hierarchy |

### 6.3 Vision Doc vs Implementation

| Metric | Vision Docs | Implementation |
|--------|-------------|----------------|
| Total lines | 3,764 (5 docs) | 7,086 (source) + 7,216 (tests) = 14,302 |
| Language | TypeScript | Python |
| Package manager | npm | pip/uv |
| Format spec coverage | 4/4 (md, yaml, json, .soul) | 4/4 |
| Memory tiers coverage | 3/5 (core, recall, graph; missing working + archival) | 3/5 |
| Storage tier coverage | 1/4 (local only) | 1/4 |
| CLI command coverage | 5/8 (birth, inspect, status, export, migrate, retire; missing archive, recover, list) | 7/8 (adds init, list; missing archive, recover) |

### 6.4 Test Coverage Areas

| Area | Test Files | Test Count | Coverage Quality |
|------|-----------|------------|------------------|
| Memory system | 8 files | ~180 | Deep -- ACT-R, sentiment, self-model, strategy |
| Models/types | 3 files | ~40 | Validation, serialization, enums |
| Soul class | 1 file (in test_models/) | ~30 | Birth, observe, remember, recall, save |
| CLI | 2 files | ~35 | All commands tested |
| Cognitive | 2 files | ~50 | Both engine modes, all tasks |
| Evolution | 1 file | ~25 | All modes, immutability, apply |
| State | 2 files | ~30 | EMA, mood mapping, rest |
| Storage | 2 files | ~20 | File persistence, atomic writes |
| MCP | 2 files | ~30 | All tools, resources, prompts |
| Export | included in storage | ~13 | Pack/unpack round-trip |

---

*Document generated from codebase analysis on 2026-03-06.*
