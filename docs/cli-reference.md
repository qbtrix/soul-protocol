<!-- Covers: CLI installation, all 7 commands (birth, inspect, status, export, migrate, retire, list)
     with usage examples, options tables, and output descriptions. -->

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
