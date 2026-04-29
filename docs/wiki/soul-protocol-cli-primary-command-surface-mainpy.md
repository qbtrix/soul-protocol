---
{
  "title": "Soul Protocol CLI — Primary Command Surface (`main.py`)",
  "summary": "The main Click application that powers the `soul` command-line tool, exposing 40+ subcommands covering the full soul lifecycle: initialisation, memory management, eternal storage, platform injection, format conversion, org management, and health tooling.",
  "concepts": [
    "soul CLI",
    "Click",
    "soul init",
    "soul recall",
    "soul observe",
    "soul dream",
    "soul evolve",
    "soul inject",
    "eternal storage",
    "format conversion",
    "TavernAI",
    "A2A Agent Card",
    "SoulSpec",
    "GDPR forget",
    "LCM",
    "OCEAN visualisation",
    "path sanitisation"
  ],
  "categories": [
    "cli",
    "architecture",
    "memory-system"
  ],
  "source_docs": [
    "c40c7e20f9e2312d"
  ],
  "backlinks": null,
  "word_count": 614,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`cli/main.py` is the primary entry point for the `soul` CLI. It wires together every user-facing command into a single Click group and delegates to the runtime layer for execution. The breadth of commands reflects soul-protocol's scope: managing identity, memory, storage, platform integration, and observability all from the terminal.

## Command Groups

### Identity and Lifecycle
| Command | Purpose |
|---------|---------|
| `soul init` | Create a new `.soul/` directory with identity, OCEAN, and values |
| `soul inspect` | Full dump of identity, memory, state, and self-model |
| `soul status` | Quick one-screen overview |
| `soul retire` | Gracefully retire a soul (marks lifecycle state) |
| `soul delete` | Remove a `.soul` file (root souls are blocked at CLI level) |
| `soul list` | List all saved souls on disk |

### Memory
| Command | Purpose |
|---------|---------|
| `soul remember` | Store a fact with type, importance, and optional emotion |
| `soul recall` | Query memories by text, recency, or importance threshold |
| `soul forget` | GDPR-compliant deletion by query, entity, or timestamp |
| `soul edit-core` | Update always-loaded persona and human-knowledge blocks |

### Cognition and Evolution
| Command | Purpose |
|---------|---------|
| `soul observe` | Feed an interaction through the full cognitive pipeline |
| `soul reflect` | Trigger memory consolidation |
| `soul dream` | Offline batch memory consolidation (dream cycle) |
| `soul feel` | Manually update mood and energy |
| `soul evolve` | Propose, approve, or reject personality mutations |
| `soul evaluate` | Score an interaction against a quality rubric |
| `soul learn` | Evaluate and create a learning event if notable |

### Format Conversion
| Command | Purpose |
|---------|---------|
| `soul export` | Export soul to different format (zip, dir, YAML) |
| `soul unpack` | Unpack a `.soul` file to browsable directory |
| `soul migrate` | Migrate from legacy `SOUL.md` flat format |
| `soul import-soulspec` / `soul export-soulspec` | SoulSpec directory interchange |
| `soul import-tavernai` / `soul export-tavernai` | TavernAI Character Card V2 |
| `soul import-a2a` / `soul export-a2a` | A2A Agent Card JSON |

### Platform and Eternal Storage
| Command | Purpose |
|---------|---------|
| `soul inject` | Write soul context into agent platform config files |
| `soul archive` | Push soul to eternal storage (Arweave/IPFS) |
| `soul recover` | Pull soul back from eternal storage by reference |
| `soul eternal-status` | Show what has been archived and where |

### Maintenance
| Command | Purpose |
|---------|---------|
| `soul health` | Audit memory tiers, duplicates, skills, graph, bond |
| `soul cleanup` | Remove duplicates, stale evals, orphan graph nodes |
| `soul context` | LCM (Lossless Context Management) ingest and assembly |
| `soul prompt` | Print the system prompt for a soul |

## Path Sanitisation

`_safe_name()` strips path separators from soul names before using them in file paths, preventing directory traversal when a user supplies a name like `../../etc/passwd` to `soul init`.

## OCEAN Visualisation

`_ocean_bar()` and `_pct_color()` render personality traits as labelled colour-coded bars in the terminal, used by `soul inspect` and `soul status`.

## Known Gaps

- `soul template` / `soul create-from-template` depend on bundled YAML archetypes (Arrow, Flash, Cyborg, Analyst). These templates are not yet user-extensible from the CLI.
- The `soul archive` command updates `manifest.json` inside the zip archive post-archive via `_update_soul_manifest()`; if the archive step partially succeeds, the manifest can be out of sync.
- Several commands call `_save_soul()` which handles both directory and zip-file souls; the dual-format save path has historically been a source of subtle bugs on format transitions.
