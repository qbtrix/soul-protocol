<!-- Covers: CLI installation, all 44 commands with usage examples, options tables, and output descriptions.
     Updated: 2026-04-14 — v0.3.1: Added `soul org` (init/status/destroy), `soul template` (list/show),
       `soul user invite`, and `soul create --template` command sections. New "Environment Variables"
       section documents SOUL_DATA_DIR, SOUL_USERS_DIR, SOUL_ARCHIVES_DIR resolution order. Count: 38 → 44.
     Updated: 2026-04-06 — Added `soul dream` command for offline batch memory consolidation.
     Updated: 2026-03-27 — v0.2.8: Added archive, recover, and eternal-status command documentation.
     Updated: 2026-03-26 — v0.2.7: Added 3 maintenance commands (health, cleanup, repair).
     Total: 38 commands. Biorhythms defaults changed to always-on (no energy/social drain).
     Updated: 2026-03-24 — v0.2.6: Added 13 runtime commands (observe, reflect, feel, prompt, forget,
     edit-core, evolve, evaluate, learn, skills, bond, events, context) and 6 import/export commands
     (import-soulspec, export-soulspec, import-tavernai, export-tavernai, import-a2a, export-a2a).
     Updated: 2026-03-13 — Added soul inject command for fast context injection into agent configs.
     Updated: 2026-03-02 — Removed dashboard/open commands, enhanced inspect with TUI panels. -->

# CLI Reference

Soul Protocol ships a command-line interface with 44 commands for creating, inspecting, exporting, and managing souls — plus the org-layer commands added in v0.3.1 (`soul org`, `soul template`, `soul user`, `soul create`). Built on Click with Rich output formatting.

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

### `soul import-soulspec`

Import a soul from a SoulSpec directory. Reads `SOUL.md`, `IDENTITY.md`, `STYLE.md`, and `soul.json` from the given directory and creates a new Soul with the mapped data.

```bash
# Import from a SoulSpec directory
soul import-soulspec ./my-character/

# Specify output path
soul import-soulspec ./specs/ -o aria.soul
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE` | Yes | Path to a SoulSpec directory. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output `.soul` file path. Defaults to `./{name}.soul`. |

---

### `soul export-soulspec`

Export a soul to SoulSpec directory format. Creates a directory with `SOUL.md`, `IDENTITY.md`, `STYLE.md`, and `soul.json` files compatible with the SoulSpec format (soulspec.org).

```bash
# Export to SoulSpec directory
soul export-soulspec aria.soul

# Specify output directory
soul export-soulspec .soul/ -o ./output/
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE` | Yes | Path to a `.soul` file or soul directory. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output directory. Defaults to `./{name}-soulspec`. |

---

### `soul import-tavernai`

Import a soul from a TavernAI Character Card V2. Reads a Character Card V2 JSON file or PNG with embedded character data. Automatically detects whether the source is JSON or PNG.

```bash
# Import from JSON
soul import-tavernai character.json

# Import from PNG with embedded card
soul import-tavernai avatar.png -o aria.soul
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE` | Yes | Path to a TavernAI Character Card V2 file (`.json` or `.png`). |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output `.soul` file path. Defaults to `./{name}.soul`. |

---

### `soul export-tavernai`

Export a soul to TavernAI Character Card V2 format. Creates a Character Card V2 JSON file. Optionally embeds the card in a PNG file with `--png`.

```bash
# Export to JSON
soul export-tavernai aria.soul

# Export with PNG embedding
soul export-tavernai .soul/ -o card.json --png avatar.png
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE` | Yes | Path to a `.soul` file or soul directory. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output JSON file path. Defaults to `./{name}-card.json`. |
| `--png PATH` | | Also export as PNG with embedded card data. |

---

### `soul import-a2a`

Create a soul from an A2A Agent Card JSON file. Reads an Agent Card and creates a new soul with the card's identity, personality (from `extensions.soul`), and skills.

```bash
# Import from Agent Card
soul import-a2a agent-card.json

# Specify output
soul import-a2a card.json -o my-agent.soul
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `FILE` | Yes | Path to an A2A Agent Card JSON file. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output `.soul` file path. Defaults to `./{name}.soul`. |

---

### `soul export-a2a`

Generate an A2A Agent Card from a soul. Reads a `.soul` file or directory and outputs a JSON Agent Card compatible with Google's Agent-to-Agent protocol.

```bash
# Export to Agent Card
soul export-a2a .soul/

# With endpoint URL
soul export-a2a aria.soul -o card.json --url https://aria.example.com
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE` | Yes | Path to a `.soul` file or soul directory. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output JSON file path. Defaults to `./{name}-agent-card.json`. |
| `--url TEXT` | `-u` | Agent endpoint URL for the card. |

---

### `soul remember`

Store a memory directly in a soul. Use this when you already know what tier the memory belongs in and don't need the cognitive pipeline to decide for you (see `soul observe` for the pipeline-driven alternative).

```bash
# Semantic by default — facts the soul should know
soul remember aria.soul "User prefers Python over JavaScript" --importance 8

# Episodic — events that happened
soul remember aria.soul "Shipped v0.3 today" --type episodic --importance 8

# Procedural — how to do things
soul remember aria.soul "To deploy: run make deploy" --type procedural

# With emotion tagging
soul remember aria.soul "Had a productive session" --emotion happy
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |
| `TEXT` | Yes | The memory content to store. |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--importance, -i INT` | `5` | Importance score 1-10. |
| `--emotion, -e TEXT` | | Emotion tag (e.g. `happy`, `sad`, `excited`). |
| `--type, -t [episodic\|semantic\|procedural]` | `semantic` | Memory tier (v0.2.9+). |

**Memory tiers:**

- **episodic** — what happened. Events, sessions, shipped work, decisions. Use when the memory answers *"when did that happen?"*
- **semantic** — what the soul knows. Facts, preferences, project knowledge. Use when the memory answers *"what do I know about X?"*
- **procedural** — how to do things. Commands, recipes, debugging tips. Use when the memory answers *"how do I...?"*

Core memory (persona and human knowledge) is not writable through `remember`. Use `soul edit-core` instead.

**Output:** A confirmation panel showing the stored text, tier, importance, emotion, and memory ID. The soul is saved automatically.

---

### `soul recall`

Query a soul's memories by text, or list the most recent memories. Returns ranked results using activation-based relevance (recency + importance + match strength).

```bash
# Text query
soul recall aria.soul "user preferences"
soul recall aria.soul "python" --limit 5 --min-importance 7

# Recent memories
soul recall aria.soul --recent 10

# LLM-friendly output
soul recall aria.soul "python" --full            # Untruncated content
soul recall aria.soul "python" --json            # Machine-readable JSON
soul recall aria.soul --recent 5 --json          # Recent memories as JSON
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |
| `QUERY` | No | Search text. If omitted, use `--recent N` instead. |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--limit, -l INT` | `10` | Maximum results to return. |
| `--min-importance INT` | `0` | Filter out memories below this importance score. |
| `--recent, -r INT` | | Show N most recent memories instead of searching. |
| `--full` | off | Return untruncated content (for LLM consumption). |
| `--json` | off | Return results as JSON (for scripting). |

**Output:** A table of ranked memories with type, content, importance, emotion, and timestamp. Use `--full` or `--json` when an agent or script needs machine-readable output.

---

### `soul observe`

Process an interaction through the full cognitive pipeline. Runs sentiment detection, significance gating, memory storage, entity extraction, self-model updates, and evolution triggers.

```bash
soul observe .soul/ --user-input "Hello" --agent-output "Hi there!"
soul observe aria.soul --user-input "Tell me a joke" --agent-output "Why did..." --channel discord
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Description |
|--------|-------------|
| `--user-input TEXT` | User's message. **Required.** |
| `--agent-output TEXT` | Agent's response. **Required.** |
| `--channel TEXT` | Channel name. Defaults to `cli`. |

**Output:** Prints the soul's mood and energy after processing the interaction. Saves the soul automatically.

---

### `soul reflect`

Trigger memory consolidation and reflection. The soul reviews recent interactions, extracts themes, creates summaries, and updates its self-understanding. Call periodically (e.g., every 10-20 interactions, or at session end). Requires a CognitiveEngine (LLM) for full power.

```bash
soul reflect .soul/
soul reflect aria.soul --no-apply
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Description |
|--------|-------------|
| `--no-apply` | Don't consolidate results into memory (dry run). |

**Output:** A panel with themes, summaries, emotional patterns, and self-insights. Saves the soul automatically unless `--no-apply` is set.

---

### `soul dream`

Run an offline dream cycle — batch memory consolidation. Dreaming reviews accumulated episodes to detect topic patterns, extract recurring procedures, consolidate the knowledge graph, and propose personality evolution from behavioral trends.

Unlike `soul reflect` (which only summarizes recent episodes via LLM), `soul dream` performs cross-tier synthesis: episodes → procedures, entities → evolution, and graph → cleanup. No LLM required — all pattern detection is heuristic-based.

```bash
soul dream .soul/
soul dream pocketpaw.soul --since 2026-04-01
soul dream .soul/ --json
soul dream .soul/ --no-archive --no-synthesize
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Description |
|--------|-------------|
| `--since DATETIME` | Only review episodes after this datetime. |
| `--no-archive` | Skip archiving old memories. |
| `--no-synthesize` | Skip creating procedural memories and evolution insights. |
| `--json` | Output as machine-readable JSON. |

**Output:** A panel with topic clusters, recurring patterns, behavioral trends, consolidation stats, and evolution insights. Saves the soul automatically.

**Dream phases:**

1. **Gather** — Collect episodes (optionally filtered by `--since`)
2. **Detect patterns** — Topic clustering (Jaccard token overlap), procedure detection (action signature frequency), behavioral trend analysis (first-half vs second-half token drift)
3. **Consolidate** — Archive old memories, deduplicate semantic facts, merge duplicate graph entities, prune expired/duplicate edges
4. **Synthesize** — Convert detected patterns into procedural memories, analyze OCEAN trait drift from behavioral data
5. **Report** — Full `DreamReport` with all findings and actions taken

---

### `soul feel`

Update a soul's emotional state directly.

```bash
soul feel .soul/ --mood excited
soul feel aria.soul --energy -10
soul feel .soul/ --mood focused --energy 5
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Description |
|--------|-------------|
| `--mood TEXT` | Set mood. One of: `neutral`, `curious`, `focused`, `tired`, `excited`, `contemplative`, `satisfied`, `concerned`. |
| `--energy FLOAT` | Adjust energy (can be negative, e.g. `-10`). Applied as a delta. |

At least one of `--mood` or `--energy` is required.

**Output:** Prints the updated mood and energy. Saves the soul automatically.

---

### `soul prompt`

Generate and print the full system prompt for a soul. Outputs to stdout with no Rich formatting, so it can be piped to other commands or captured in a variable.

```bash
soul prompt .soul/
soul prompt aria.soul > prompt.txt
soul prompt .soul/ | pbcopy
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Output:** Plain text system prompt string including DNA, identity, core memory, current state, and self-model.

---

### `soul forget`

Delete memories by query, entity, or timestamp (GDPR-compliant). Searches and deletes matching memories across all tiers. Records a deletion audit entry without storing deleted content.

```bash
soul forget .soul/ "credit card"
soul forget aria.soul --entity "John Doe"
soul forget .soul/ --before 2026-01-01T00:00:00 --confirm
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |
| `QUERY` | No | Search query for memories to delete. |

**Options:**

| Option | Description |
|--------|-------------|
| `--entity TEXT` | Delete by entity name instead of query. |
| `--before TEXT` | Delete memories before an ISO timestamp. |
| `--confirm` | Skip the confirmation prompt. |

At least one of `QUERY`, `--entity`, or `--before` is required. Prompts for confirmation unless `--confirm` is set.

---

### `soul edit-core`

Edit a soul's core memory — the always-loaded persona and human knowledge sections.

```bash
soul edit-core .soul/ --persona "I am a helpful coding assistant"
soul edit-core aria.soul --human "User prefers Python and dark mode"
soul edit-core .soul/ --persona "New persona" --human "New human"
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Description |
|--------|-------------|
| `--persona TEXT` | Set the persona text. |
| `--human TEXT` | Set the human knowledge text. |

At least one of `--persona` or `--human` is required.

**Output:** A panel showing the updated core memory. Saves the soul automatically.

---

### `soul evolve`

Manage soul evolution — propose, approve, reject, or list mutations.

```bash
# Propose a mutation
soul evolve .soul/ --propose --trait communication.warmth --value high --reason "User prefers warmth"

# List pending and historical mutations
soul evolve .soul/ --list

# Approve or reject
soul evolve .soul/ --approve abc123
soul evolve .soul/ --reject abc123
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Description |
|--------|-------------|
| `--propose` | Propose a new mutation. Requires `--trait`, `--value`, and `--reason`. |
| `--trait TEXT` | Trait to mutate (with `--propose`). |
| `--value TEXT` | New value for trait (with `--propose`). |
| `--reason TEXT` | Reason for mutation (with `--propose`). |
| `--approve ID` | Approve a pending mutation by ID. |
| `--reject ID` | Reject a pending mutation by ID. |
| `--list` | List pending mutations and evolution history. |

---

### `soul evaluate`

Evaluate an interaction against a rubric. Scores the interaction, stores learning as procedural memory, and adjusts skill XP based on the score.

```bash
soul evaluate .soul/ --user-input "Explain recursion" --agent-output "Recursion is..."
soul evaluate aria.soul --user-input "Fix this bug" --agent-output "Here's the fix" --domain coding
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Description |
|--------|-------------|
| `--user-input TEXT` | User's message. **Required.** |
| `--agent-output TEXT` | Agent's response. **Required.** |
| `--domain TEXT` | Domain for rubric selection. |

**Output:** A panel showing overall score, rubric ID, individual criteria results, and extracted learning.

---

### `soul learn`

Evaluate an interaction and create a learning event if notable. Combines evaluation with the learning pipeline — extracts lessons, grants XP, and stores procedural memory.

```bash
soul learn .soul/ --user-input "Explain recursion" --agent-output "Recursion is..."
soul learn aria.soul --user-input "Fix this bug" --agent-output "Here's the fix" --domain coding
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Description |
|--------|-------------|
| `--user-input TEXT` | User's message. **Required.** |
| `--agent-output TEXT` | Agent's response. **Required.** |
| `--domain TEXT` | Domain for rubric selection. |

**Output:** A panel showing the lesson, domain, confidence, score, and associated skill. Prints a notice if no notable learning was found.

---

### `soul skills`

View a soul's skills with level, XP, and progress bars.

```bash
soul skills .soul/
soul skills aria.soul
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Output:** A table showing each skill's name, level, current XP, XP to next level, and a progress bar.

---

### `soul bond`

View or modify the soul's bond with its bonded entity.

```bash
soul bond .soul/
soul bond aria.soul --strengthen 5.0
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Description |
|--------|-------------|
| `--strengthen FLOAT` | Strengthen the bond by this amount. |

**Output:** A panel showing bonded entity, bond strength (with progress bar), interaction count, and bond start date.

---

### `soul events`

View general events (Conway's autobiographical memory hierarchy). Shows themed event clusters from the soul's history.

```bash
soul events .soul/
soul events aria.soul --recent 20
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a soul file or `.soul/` directory. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--recent INT` | `-n` | Number of recent events to show. Defaults to 10. |

**Output:** A table showing each event's theme, episode count, start date, and last update date.

---

### `soul context`

LCM (Lossless Context Management) operations — ingest messages, assemble context windows, search history, and view metadata. Works standalone with an in-memory SQLite store.

```bash
# Ingest a message
soul context --ingest --role user --content "Hello there"

# Assemble a context window
soul context --assemble --max-tokens 4000

# Search context history
soul context --grep "hello"

# View store metadata
soul context --describe
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | No | Path to a soul file (optional, for soul-scoped context). |

**Options:**

| Option | Description |
|--------|-------------|
| `--ingest` | Ingest a message into context. Requires `--role` and `--content`. |
| `--role TEXT` | Message role (with `--ingest`). |
| `--content TEXT` | Message content (with `--ingest`). |
| `--assemble` | Assemble a context window from stored messages. |
| `--max-tokens INT` | Token budget (with `--assemble`). |
| `--grep PATTERN` | Search context history by regex pattern. |
| `--describe` | Show context store metadata (message count, tokens, date range). |

---

## Org Layer (v0.3.1)

The `soul org`, `soul template`, `soul user`, and `soul create` command groups ship in v0.3.1. See also [Org Management](org.md) for the bootstrap walkthrough and [Org Journal Spec](org-journal-spec.md) for the wire-level contract.

### `soul org init`

Bootstrap an empty directory into a working org. Creates a root governance soul, generates an Ed25519 signing keypair, opens a SQLite WAL journal, and writes the genesis events (`org.created`, one `scope.created` per first-level scope). Optionally seeds a starter fleet.

```bash
soul org init --org-name "Acme" --purpose "AI tooling" --non-interactive
soul org init --org-name "Acme" --values "audit,velocity,kindness" \
  --founder-name "Pat" --founder-email "pat@acme.com" \
  --scopes "org:sales,org:ops" --fleet sales --non-interactive
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--org-name TEXT` | | Organization name. Required in `--non-interactive` mode. |
| `--purpose TEXT` | | Mission statement. Lands in the root soul's persona. |
| `--values TEXT` | | Comma-separated org values (3-5 recommended). |
| `--founder-name TEXT` | | Founder's display name. |
| `--founder-email TEXT` | | Founder's email. |
| `--scopes TEXT` | | Comma-separated first-level scopes, e.g. `org:sales,org:ops`. |
| `--fleet [sales\|support\|solo\|skip]` | `skip` | Starter fleet to seed. |
| `--data-dir PATH` | `~/.soul/` | Where to create the org. Also honors `$SOUL_DATA_DIR`. |
| `--users-dir PATH` | nested under `--data-dir` | Where founder user souls live. Also honors `$SOUL_USERS_DIR`. |
| `--force` | off | Overwrite an existing non-empty data-dir. |
| `--non-interactive` | off | Fail instead of prompting. Requires `--org-name`. |

Re-running `init` against an initialized directory refuses to proceed unless `--force` is passed. Every step emits a journal event so the org state is reconstructable from the event log alone.

---

### `soul org status`

Print a human-readable snapshot of an initialized org: DID, journal head, event count, data-dir location, root soul seal status. Read-only.

```bash
soul org status
soul org status --data-dir /path/to/org
soul org status --json
```

**Options:**

| Option | Description |
|--------|-------------|
| `--data-dir PATH` | Org dir to inspect. Defaults to `~/.soul/` or `$SOUL_DATA_DIR`. |
| `--json` | Emit machine-readable JSON instead of a Rich panel. |

---

### `soul org destroy`

Tarball the org to the archives dir, then wipe the data-dir. Terminal — there is no undo. Requires two explicit flags plus (in interactive mode) typing the org name at a prompt.

```bash
soul org destroy --confirm --i-mean-it
soul org destroy --confirm --i-mean-it --non-interactive  # tests, scripted teardown
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--data-dir PATH` | `~/.soul/` | Org dir to destroy. Also honors `$SOUL_DATA_DIR`. |
| `--archives-dir PATH` | `~/.soul-archives/` | Where the tarball lands. Sibling of the org dir by default, so the archive survives the wipe. Also honors `$SOUL_ARCHIVES_DIR`. |
| `--confirm` | | Required guard rail. |
| `--i-mean-it` | | Required guard rail (second one). |
| `--non-interactive` | | Skip the typed-name prompt. |

The destroy path writes the archive *first* and removes the data-dir only on success. If the archive write fails, the org is left intact.

---

### `soul template list`

List every bundled role archetype. v0.3.1 ships Arrow, Flash, Cyborg, and Analyst — each with pre-baked DNA, communication style, and scope defaults.

```bash
soul template list
```

---

### `soul template show`

Print the raw YAML for a single bundled template. Useful for copying into your own overrides.

```bash
soul template show arrow
```

---

### `soul create`

Instantiate a new `.soul/` directory from a bundled template. Pairs with `soul template list` — pick a name, stamp it out.

```bash
soul create --template arrow
soul create --template analyst --name Sage --dir .sage --format zip
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--template TEXT` | Required | Bundled template name (`arrow`, `flash`, `cyborg`, `analyst`). |
| `--name TEXT` | template default | Override the soul's display name. |
| `--dir TEXT` | `.soul` | Directory to write the new soul to. |
| `--format [dir\|zip]` | `dir` | Write as an unpacked directory or a `.soul` zip archive. |

---

### `soul user invite`

Placeholder for the org invite flow. Accepted today so hooks can wire it up in advance; the real implementation lands in a follow-up PR. Prints a hint and exits non-zero so callers don't mistake it for a completed invite.

```bash
soul user invite pat@acme.com
```

---

## Environment Variables

The CLI resolves paths in this order: **explicit flag > environment variable > default**. All three variables are honored by `soul org init`, `soul org status`, `soul org destroy`, and any other command that touches the org data-dir.

| Variable | Affects | Default | Description |
|----------|---------|---------|-------------|
| `SOUL_DATA_DIR` | `--data-dir` | `~/.soul/` | Root directory for the org: `root.soul`, `keys/`, `journal.db`. |
| `SOUL_USERS_DIR` | `--users-dir` | nests under `--data-dir` (so `--data-dir /tmp/foo` yields `/tmp/foo/users/`); falls back to `~/.soul/users/` when neither is set | Where founder and invited user souls live. Pre-v0.3.1 this was hardcoded to `~/.soul/users/`, which silently polluted home directories during isolated demos and CI runs. |
| `SOUL_ARCHIVES_DIR` | `--archives-dir` | `~/.soul-archives/` | Archive destination for `soul org destroy`. Sibling of the org dir so it survives the wipe. |

These are also documented in [Configuration](configuration.md#environment-variables).

---

## Soul Maintenance (v0.2.7)

### `soul health <path>`

Audit a soul's health — memory tiers, duplicates, orphan graph nodes, skills, bond.

```bash
soul health .soul/
```

Shows a panel with:
- Memory tier counts (episodic, semantic, procedural)
- Knowledge graph nodes, skills, evaluation history count
- Bond strength and interaction count
- Issues: duplicates (>80% overlap), orphan graph nodes, skill/bond integrity

### `soul cleanup <path>`

Remove duplicates, stale evaluations, and orphan graph nodes.

```bash
soul cleanup .soul/ --dry-run          # preview without changes
soul cleanup .soul/ --auto             # apply all cleanups
soul cleanup .soul/ --no-dedup         # skip duplicate removal
soul cleanup .soul/ --low-importance 2 # remove memories with importance ≤ 2
```

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview what would be cleaned without changing anything |
| `--auto` | Apply all cleanups without prompting |
| `--dedup / --no-dedup` | Toggle near-duplicate removal (default: on) |
| `--stale-evals / --no-stale-evals` | Toggle stale evaluation procedural cleanup (default: on) |
| `--orphan-nodes / --no-orphan-nodes` | Toggle orphan graph node cleanup (default: on) |
| `--low-importance N` | Remove memories with importance ≤ N (default: 0 = skip) |

### `soul repair <path>`

Targeted fixes for corrupted or stale soul state.

```bash
soul repair .soul/ --reset-energy      # energy + social battery → 100%
soul repair .soul/ --reset-bond        # bond strength → 50.0
soul repair .soul/ --rebuild-graph     # re-extract entities from all memories
soul repair .soul/ --clear-evals       # wipe evaluation history
soul repair .soul/ --clear-skills      # wipe all learned skills
soul repair .soul/ --clear-procedural  # wipe procedural memories
```

| Option | Description |
|--------|-------------|
| `--reset-energy` | Reset energy and social battery to 100% |
| `--reset-bond` | Reset bond strength to 50.0 |
| `--rebuild-graph` | Clear graph and re-extract entities from all memories |
| `--clear-evals` | Clear evaluation history |
| `--clear-skills` | Clear all learned skills |
| `--clear-procedural` | Clear all procedural memories |

---

## Eternal Storage

### `soul archive`

Archive a `.soul` file to eternal storage tiers (IPFS, Arweave, Blockchain). Uses mock providers by default.

```bash
soul archive my-soul.soul
soul archive .soul/ --tiers ipfs arweave
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a `.soul` file or `.soul/` directory. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--tiers TIER` | `-t` | Storage tiers to archive to (repeatable). If omitted, archives to all mock providers. |

**Output:** A table showing each tier's name, reference hash (truncated), cost, and whether storage is permanent. Archive references are persisted into the `.soul` manifest.

---

### `soul recover`

Recover a soul from eternal storage by its reference hash.

```bash
soul recover QmRef123... --tier ipfs --output recovered.soul
soul recover arweave_ref_456 --tier arweave --output my-soul.soul
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `REFERENCE` | Yes | The storage reference hash returned by `soul archive`. |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--tier TIER` | `-t` | Which tier to recover from: `ipfs`, `arweave`, or `blockchain`. Default: `ipfs`. |
| `--output PATH` | `-o` | Output file path (required). |

**Output:** Writes the recovered `.soul` file to the output path and prints the byte count.

---

### `soul eternal-status`

Show eternal storage references for a `.soul` file. Reads the manifest inside the archive and displays any previously archived tiers and their references.

```bash
soul eternal-status my-soul.soul
soul eternal-status .soul/
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Path to a `.soul` file or `.soul/` directory. |

**Output:** A table showing each archived tier, its reference, and timestamp.

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
