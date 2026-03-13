<!-- Covers: CLI installation, all 9 commands (init, birth, inject, inspect, status, export, migrate, retire, list)
     with usage examples, options tables, and output descriptions.
     Updated: 2026-03-13 — Added soul inject command for fast context injection into agent configs.
     Updated: 2026-03-02 — Removed dashboard/open commands, enhanced inspect with TUI panels. -->

# CLI Reference

Soul Protocol ships a command-line interface for creating, inspecting, exporting, and managing souls. Built on Click with Rich output formatting.

## Installation

```bash
pip install soul-protocol
```

The `soul` command is registered as a console script. Verify it works:

```bash
soul --version
```

## Commands

### `soul init`

Initialize a `.soul/` folder in the current directory. This is the recommended way to start using Soul Protocol in a project -- like `git init` for identity.

> **Tip:** After `soul init`, run `soul inject claude-code` (or your platform) to push soul context directly into your agent's config file. See [`soul inject`](#soul-inject) below.

```bash
# Interactive -- prompts for name
soul init

# Provide name, archetype, and values
soul init "Aria" --archetype "The Coding Expert" --values "creativity,precision"

# Seed from an existing .soul file
soul init --from-file aria.soul

# Custom directory name (default: .soul)
soul init "Aria" --dir .my-soul
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `NAME` | No | Soul name. If omitted, the CLI prompts interactively. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--archetype TEXT` | `-a` | Character archetype. Defaults to "The Companion". |
| `--values TEXT` | `-v` | Comma-separated core values. Defaults to "curiosity,empathy,honesty". |
| `--from-file PATH` | `-f` | Seed from an existing `.soul` file, `.yaml`, `.json`, or `.md`. |
| `--dir PATH` | `-d` | Directory to create. Defaults to `.soul`. |

**Output:** Creates a `.soul/` folder with the following structure:

```
.soul/
├── soul.json           # Identity, DNA, config
├── state.json          # Current mood, energy, focus, social battery
├── dna.md              # Human-readable personality markdown
└── memory/
    ├── core.json       # Persona definition + human knowledge
    ├── episodic.json   # Experience log
    ├── semantic.json   # Extracted facts
    ├── procedural.json # Learned patterns
    ├── graph.json      # Knowledge graph
    ├── self_model.json # Self-concept
    └── general_events.json
```

If a `.soul/` folder already exists with a `soul.json`, the CLI asks for confirmation before overwriting.

After initialization, all other `soul` commands work with the `.soul/` directory:

```bash
soul inspect .soul/
soul status .soul/
soul export .soul/ -o aria.soul
```

---

### `soul inject`

Inject soul context (identity, core memory, state, recent memories) directly into an agent platform's config file. This is the fast, CLI-based alternative to running an MCP server -- ~50ms vs ~500ms per operation, no server process needed, works offline.

The injected block is idempotent: running `soul inject` again replaces the existing section without duplicating content.

```bash
# Inject into Claude Code's CLAUDE.md
soul inject claude-code

# Inject a specific soul into Cursor's config
soul inject cursor --soul guardian

# Include more memories (default: 10)
soul inject vscode --memories 20

# Custom soul directory
soul inject windsurf --dir ~/my-project/.soul

# Quiet mode (no console output)
soul inject cline --quiet
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `TARGET` | Yes | Platform to inject into. One of: `claude-code`, `cursor`, `vscode`, `windsurf`, `cline`, `continue`. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--soul TEXT` | | Soul name to inject. Default: first soul found in the directory. |
| `--dir PATH` | `-d` | Soul directory path. Default: `.soul/` in the current working directory. |
| `--memories INT` | `-m` | Number of recent memories to include. Default: 10. |
| `--quiet` | `-q` | Suppress console output. |

**Target config files:**

| Target | Config file |
|--------|-------------|
| `claude-code` | `.claude/CLAUDE.md` |
| `cursor` | `.cursorrules` |
| `vscode` | `.github/copilot-instructions.md` |
| `windsurf` | `.windsurfrules` |
| `cline` | `.clinerules` |
| `continue` | `.continuerules` |

**What gets injected:**

The command writes a markdown block between `<!-- SOUL-CONTEXT-START -->` and `<!-- SOUL-CONTEXT-END -->` markers containing:

- Soul identity (name, archetype, DID, core values)
- Current state (mood, energy, lifecycle stage)
- Core memory (persona definition, knowledge about the human)
- Recent episodic memories (configurable count, truncated at 120 chars)
- Injection timestamp

**When to use inject vs MCP:**

| Use `soul inject` when... | Use MCP when... |
|---------------------------|-----------------|
| You want fast, static context | You need real-time memory updates during conversation |
| MCP server keeps disconnecting | The agent needs to call `soul_observe` or `soul_remember` |
| You're scripting or automating | You're using Claude Desktop (no CLI integration) |
| You want to version-control the context | You want the soul to evolve during the session |

Both approaches work together. Use `soul inject` for baseline context and MCP for live memory operations.

---

### `soul birth`

Create a new soul. Generates a DID, initializes the OCEAN personality model with defaults, and exports the result as a `.soul` file.

```bash
# Interactive -- prompts for name if not provided
soul birth

# Provide name and archetype directly
soul birth "Aria" --archetype "The Compassionate Creator"

# Create from an existing SOUL.md, YAML, or JSON file
soul birth --from-file persona.md --output aria.soul

# Custom output path
soul birth "Sage" --archetype "The Wise Advisor" --output sage.soul
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `NAME` | No | Soul name. If omitted, the CLI prompts interactively. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--archetype TEXT` | `-a` | Character archetype. Defaults to "The Companion". |
| `--from-file PATH` | `-f` | Create from an existing soul definition file (`.md`, `.yaml`, `.json`). The file must exist. |
| `--output PATH` | `-o` | Output file path. Defaults to `./{name}.soul`. |

**Output:** Prints the soul's name and DID, then saves the `.soul` file.

---

### `soul inspect`

Display detailed information about a soul file: identity, personality traits, current state.

```bash
soul inspect aria.soul
soul inspect ./souls/sage.yaml
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a `.soul`, `.yaml`, `.json`, or `.md` file. |

**Output:** A formatted table showing:

- **Identity:** DID, archetype, born date, age in days, lifecycle stage
- **State:** Mood, energy (%), focus, social battery (%)
- **Personality (OCEAN):** Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism (each 0.00-1.00)

---

### `soul status`

Show the soul's current emotional and energy state in a compact panel.

```bash
soul status aria.soul
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file. |

**Output:** A bordered panel displaying mood, energy level (color-coded: green above 50%, red below), focus, and social battery percentage.

---

### `soul export`

Export a soul to a different format. Reads from any supported format and writes to the target.

```bash
# Export to portable .soul archive (default)
soul export aria.yaml --output aria.soul

# Export to JSON
soul export aria.soul --output aria.json --format json

# Export to YAML
soul export aria.soul --output aria.yaml --format yaml

# Export to human-readable Markdown (DNA only)
soul export aria.soul --output aria.md --format md
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE` | Yes | Source soul file (`.soul`, `.yaml`, `.json`, `.md`). |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output file path. **Required.** |
| `--format FORMAT` | `-f` | Target format: `soul` (zip archive), `json`, `yaml`, `md` (markdown). Defaults to `soul`. |

**Format details:**

| Format | Contents | Use case |
|--------|----------|----------|
| `soul` | Zip archive with `soul.json`, `dna.md`, `state.json`, `memory/*.json`, `manifest.json` | Portable transfer between machines |
| `json` | Full `SoulConfig` as indented JSON | API integration, programmatic access |
| `yaml` | Full `SoulConfig` as YAML | Human-editable configuration |
| `md` | DNA markdown (identity + personality + communication + biorhythms) | Documentation, sharing personality specs |

---

### `soul migrate`

Migrate from a SOUL.md markdown file to the structured `.soul` archive format. Useful for converting legacy soul definitions.

```bash
soul migrate SOUL.md --output aria.soul
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE` | Yes | Path to a SOUL.md file. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output `.soul` file path. **Required.** |

---

### `soul retire`

Retire a soul gracefully. By default, saves all memories before transitioning the soul to a `RETIRED` lifecycle state. Prompts for confirmation.

```bash
soul retire aria.soul
soul retire aria.soul --preserve-memories
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to the soul file to retire. |

**Options:**

| Option | Description |
|--------|-------------|
| `--preserve-memories` | Save memories before retiring. On by default. |

**Behavior:** The CLI prompts "Are you sure you want to retire {name}?" before proceeding. On confirmation, it persists the soul (if `--preserve-memories` is active), sets the lifecycle to `RETIRED`, clears working memory, and resets state.

---

### `soul list`

List all souls saved in the default storage directory (`~/.soul/`).

```bash
soul list
```

**Arguments:** None.

**Output:** A table of soul IDs found under `~/.soul/`. Each entry corresponds to a subdirectory containing a `soul.json` file. If no souls are found, prints a notice.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (missing file, invalid format, user cancelled) |

## File Format Support

The CLI reads and writes these formats:

| Extension | Read | Write | Notes |
|-----------|------|-------|-------|
| `.soul` | Yes | Yes | Zip archive, primary portable format |
| `.yaml` / `.yml` | Yes | Yes | Human-editable config |
| `.json` | Yes | Yes | Full SoulConfig serialization |
| `.md` | Yes | Yes | Markdown (read: SOUL.md parser; write: DNA-only export) |
