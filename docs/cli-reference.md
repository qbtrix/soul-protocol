<!-- Covers: CLI installation, all 10 commands (init, birth, open, inspect, status, export, migrate, retire, list, dashboard)
     with usage examples, options tables, and output descriptions.
     Updated: Added soul open command. -->

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
soul dashboard .soul/
soul export .soul/ -o aria.soul
```

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

### `soul dashboard`

Open a visual web dashboard for a soul. Starts a local HTTP server that displays identity, OCEAN personality, state gauges, memory browser, knowledge graph, and self-model.

```bash
# Open dashboard for .soul/ folder (default)
soul dashboard

# Open dashboard for a specific path
soul dashboard aria.soul
soul dashboard .soul/

# Use a different port
soul dashboard --port 8080

# Don't auto-open browser
soul dashboard --no-open
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | No | Path to `.soul` file or `.soul/` directory. Defaults to `.soul`. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--port INT` | `-p` | HTTP server port. Defaults to 5678. |
| `--no-open` | | Don't automatically open the browser. |

**Behavior:** The dashboard loads the soul's data (identity, DNA, state, all memory tiers, knowledge graph, self-model) and serves a single-page web application at `http://localhost:<port>`. The page features:

- **Identity card** with name, archetype, DID, values, lifecycle
- **OCEAN personality bars** with animated fills
- **State gauges** for mood, energy, focus, and social battery
- **Core memory viewer** (persona + human knowledge)
- **Memory browser** with search, type filtering, and sort
- **Knowledge graph** entity and relationship display
- **Self-model** with confidence bars and relationship notes

The dashboard uses mood-reactive accent colors -- the entire color scheme shifts based on the soul's current mood. Zero external dependencies (pure HTML/CSS/JS served via Python stdlib).

Press `Ctrl+C` to stop the server.

---

### `soul open`

Quick shortcut to open a soul in the visual dashboard. Accepts any soul path — `.soul` file, `.soul/` directory, or any directory containing `soul.json`. If no path is given, opens `.soul/` in the current directory.

```bash
# Open .soul/ in current directory (default)
soul open

# Open a specific .soul file
soul open aria.soul

# Open a .soul/ directory
soul open .soul/

# Use a different port
soul open --port 8080
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | No | Path to `.soul` file or directory. Defaults to `.soul`. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--port INT` | `-p` | HTTP server port. Defaults to 5678. |

**Behavior:** Same as `soul dashboard`, but simpler to type and always auto-opens the browser. Designed for the common case: you're in a project with a `.soul/` folder and just want to see it.

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
