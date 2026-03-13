# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Soul Protocol is a portable AI identity and memory standard. It provides persistent personality (OCEAN model), 5-tier memory (core, episodic, semantic, procedural, knowledge graph), emergent self-model, cognitive pipeline, DNA evolution, bond tracking, and eternal storage — all packaged in a `.soul` archive format (zip containing JSON/markdown).

**Python 3.11+** | **Package:** `soul-protocol` v0.2.3 | **Build:** hatchling (src layout)

**Two-layer architecture:** core (Pydantic-only, zero deps) + engine (yaml/click/rich/crypto)

## Commands

```bash
# Install for development
pip install -e ".[dev]"
pip install -e ".[all,dev]"   # all optional extras

# Run all tests (1145 tests, asyncio_mode=auto — no @pytest.mark.asyncio needed)
python -m pytest tests/

# Run a single test file or directory
python -m pytest tests/test_soul.py
python -m pytest tests/test_memory/

# Lint and format (ruff, line-length=100, rules: E/F/I/UP)
ruff check src/
ruff check src/ --fix
ruff format src/

# Type check
mypy src/

# CLI (installed as entry point)
soul birth "Name" --archetype creative_writer
soul init "Name" --setup claude-code
soul inspect path/to/file.soul
soul status path/to/file.soul
soul export source --output out.json --format json
soul inject --target claude-code          # inject context into agent configs
soul archive path/to/file.soul --tier ipfs
soul recover <reference>
```

## Architecture

### Facade Pattern — `Soul` class (`runtime/soul.py`)

All public API goes through `Soul`, which delegates to managers:

```
Soul
├── MemoryManager (runtime/memory/manager.py)
│   ├── CoreMemoryManager     — always-loaded persona + human profile
│   ├── EpisodicStore         — interaction history
│   ├── SemanticStore         — extracted facts (with conflict resolution + dedup)
│   ├── ProceduralStore       — learned patterns
│   ├── KnowledgeGraph        — entity relationships (optional, networkx)
│   ├── RecallEngine          — cross-store ACT-R search
│   ├── SelfModelManager      — Klein self-concept, emergent domain discovery
│   └── CognitiveProcessor    — routes to LLM, DSPy, or heuristic engine
├── StateManager              — mood, energy, focus, social battery
├── EvolutionManager          — DNA mutation proposals/approvals
├── Bond                      — human-soul relationship strength (0-100, logarithmic)
└── SkillRegistry             — domain expertise tracking
```

### Key Protocols (structural typing, `@runtime_checkable`)

- **`CognitiveEngine`** — implement `async def think(self, prompt: str) -> str` to plug in any LLM. `HeuristicEngine` is the zero-dependency fallback.
- **`SearchStrategy`** — implement `def score(self, query: str, content: str) -> float` for custom memory retrieval. `TokenOverlapStrategy` is the default.
- **`EmbeddingProvider`** — pluggable vector embeddings (`HashEmbedder`, `TFIDFEmbedder`).
- **`EternalStorageProvider`** — pluggable eternal storage (IPFS, Arweave, blockchain).

### Observe Pipeline (`MemoryManager.observe()`)

Psychology-informed processing on each interaction:
1. `detect_sentiment()` → SomaticMarker (Damasio)
2. `assess_significance()` → SignificanceScore (LIDA attention gate, optionally via DSPy)
3. Significant? → store in EpisodicStore with psychology metadata
4. `extract_facts()` → SemanticStore (with conflict/supersede logic + dedup via `reconcile_fact()`)
5. Phase 2: `generate_abstract()` → L0 ~100-token fingerprint on episodic entries
6. Phase 2: `compute_salience()` → retrieval weight (0-1)
7. `extract_entities()` → KnowledgeGraph (with provenance/edge metadata)
8. `update_self_model()` → SelfModelManager (Klein domain classification)
9. `check_triggers()` → EvolutionManager

### Memory Content Layers (Phase 2)

Progressive loading to manage context windows:
- **L0 — Abstract** (~100 tokens): fingerprint stored on MemoryEntry
- **L1 — Overview** (~1K tokens): expanded summary
- **L2 — Full content**: original text

### Async-First API

All lifecycle methods are async: `Soul.birth()`, `Soul.awaken()`, `Soul.observe()`, `Soul.recall()`, `Soul.export()`, `Soul.reflect()`, `Soul.reincarnate()`. CLI commands wrap with `asyncio.run()`.

### `.soul` File Format

A zip archive containing JSON and markdown files. Written by `export/pack.py`, read by `export/unpack.py`. The `.soul/` directory (like `.git/`) is the local working format, managed by `storage/file.py` with atomic writes (tempdir + shutil.move). Supports password-protected encryption.

### ACT-R Memory Scoring (`memory/activation.py`)

Combines base-level decay (recency × frequency), spreading activation (query relevance), emotional boost (somatic markers), and stochastic noise.

### Fact Conflict Resolution & Dedup

When a new fact shares a template prefix with an existing fact, the old fact is marked `superseded_by` — never deleted. `dedup.reconcile_fact()` uses Jaccard similarity to prevent duplicate semantic entries.

### Memory Categories (Extraction Taxonomy)

`MemoryCategory` enum classifies extracted memories:
- **User-facing:** PROFILE, PREFERENCE, ENTITY, EVENT
- **Agent-facing:** CASE, PATTERN, SKILL

## Key Files

| File | Role |
|---|---|
| `src/soul_protocol/runtime/soul.py` | Main Soul class — lifecycle, observe, recall, export, reincarnate |
| `src/soul_protocol/runtime/types.py` | All Pydantic models (SoulConfig, DNA, MemoryEntry, Bond, etc.) |
| `src/soul_protocol/runtime/memory/manager.py` | MemoryManager — observe pipeline orchestration |
| `src/soul_protocol/runtime/memory/dedup.py` | Semantic deduplication (`reconcile_fact()`) |
| `src/soul_protocol/runtime/memory/attention.py` | Significance gating (LIDA) |
| `src/soul_protocol/runtime/cognitive/engine.py` | CognitiveEngine protocol, HeuristicEngine, CognitiveProcessor |
| `src/soul_protocol/runtime/cognitive/dspy_adapter.py` | DSPy integration for LLM-powered cognition |
| `src/soul_protocol/runtime/bond.py` | Human-Soul bond model (logarithmic growth) |
| `src/soul_protocol/runtime/skills.py` | SkillRegistry for domain expertise |
| `src/soul_protocol/runtime/embeddings/` | Vector search (HashEmbedder, TFIDFEmbedder, VectorStrategy) |
| `src/soul_protocol/runtime/eternal/` | Eternal storage (IPFS, Arweave, blockchain) |
| `src/soul_protocol/cli/main.py` | Click CLI — 15 commands |
| `src/soul_protocol/cli/inject.py` | Soul inject — context injection into 6 agent platforms |
| `src/soul_protocol/mcp/server.py` | FastMCP server (12 tools, 3 resources, 2 prompts) |
| `src/soul_protocol/exceptions.py` | Custom exception hierarchy |
| `tests/conftest.py` | Shared fixtures: `sample_soul`, `sample_identity`, `tmp_soul_file` |

## MCP Server

Multi-soul support via `SoulRegistry`. Load via `SOUL_DIR` (scan directory) or `SOUL_PATH` (single file).

**12 Tools:** `soul_birth`, `soul_list`, `soul_switch`, `soul_observe`, `soul_remember`, `soul_recall`, `soul_reflect`, `soul_state`, `soul_feel`, `soul_prompt`, `soul_save`, `soul_export`

**3 Resources:** `soul://identity`, `soul://memory/core`, `soul://state`

**2 Prompts:** `soul_system_prompt_template`, `soul_introduction`

## Conventions

- **Pydantic v2** for all data models (in `runtime/types.py`)
- **Click** for CLI commands
- **Rich** for TUI output (panels, progress bars, tables)
- **ruff** for linting/formatting (not black/flake8)
- Source layout: all code under `src/soul_protocol/`
- Runtime code under `src/soul_protocol/runtime/`, spec under `src/soul_protocol/spec/`
- Tests mirror source structure: `tests/test_memory/`, `tests/test_cognitive/`, etc.
- Optional dependencies guarded by extras: `engine`, `mcp`, `dspy`, `graph`, `vector`, `all`
