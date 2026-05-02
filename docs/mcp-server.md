<!-- Covers: MCP server setup, configuration for Claude Desktop/Cursor, all 28 tools
     (14 soul/memory + 5 context + 5 psychology + 3 trust chain + 1 eval), 3 resources,
     2 prompts, auto-detect, MCP Sampling Engine, programmatic usage, and design notes.
     Updated: 2026-04-30 — v0.5.0 (#203): Added soul_prune_chain MCP tool for touch-time
     chain pruning. Dry-run by default; pass apply=true to mutate the chain. Tool count: 27 → 28.
     Updated: 2026-04-29 — v0.5.0 (#142): Added soul_optimize MCP tool for the autonomous
       self-improvement loop. Defaults to apply=False (dry-run). When apply=True, kept
       changes write soul.optimize.applied trust chain entries.
     Updated: 2026-04-29 — v0.5.0 (#160): Added soul_eval MCP tool for running YAML eval
     specs against the active soul. Accepts yaml_path or yaml_string. Returns the EvalResult
     as JSON. Tool count: 26 → 27.
     Updated: 2026-04-29 — v0.4.0 (#42): Added soul_verify and soul_audit MCP tools for
     trust-chain integrity checks and signed-action timelines. Tool count: 24 → 26.
     Updated: 2026-04-06 — Added soul_dream tool for offline batch memory consolidation.
     Updated: 2026-03-27 — v0.2.8: Fixed section header "Tools (18)" → "Tools (23)".
     Updated: 2026-03-26 — v0.2.7: Added 5 psychology pipeline tools (soul_skills,
     soul_evaluate, soul_learn, soul_evolve, soul_bond). Tool count: 18 → 23.
     Updated: 2026-03-24 — v0.2.6: Added 5 LCM context tools (soul_context_ingest,
     soul_context_assemble, soul_context_grep, soul_context_expand, soul_context_describe),
     soul_reload tool, auto-detect section, MCP Sampling Engine section. Tool count: 12 → 18.
     Updated: 2026-03-13 — added soul_list + soul_switch tools, SOUL_DIR env var, multi-soul registry notes,
     renamed soul_system_prompt to soul_system_prompt_template, added optional soul parameter docs. -->

# MCP Server

Soul Protocol includes a FastMCP-based Model Context Protocol server for agent integration. Any MCP-compatible client (Claude Desktop, Cursor, custom agents) can connect to a soul and interact with its memory, identity, and emotional state in real time.

## Installation

The MCP server requires the optional `mcp` extra:

```bash
pip install soul-protocol[mcp]
```

This pulls in `fastmcp` as a dependency. The core `soul-protocol` package has no dependency on it.

## Running

```bash
# Start with an existing soul file
SOUL_PATH=aria.soul soul-mcp

# Start empty (create a soul at runtime via the soul_birth tool)
soul-mcp
```

The server reads `SOUL_PATH` from the environment on startup. If set, it loads that soul file (`.soul`, `.json`, `.yaml`, or `.md`) before accepting connections. If not set, the server starts with no soul loaded -- clients must call `soul_birth` before using any other tool.

You can also set `SOUL_DIR` to point to a directory containing multiple soul folders (e.g. `~/.soul/`). When `SOUL_DIR` is set, the server discovers all souls in that directory and loads them into the `SoulRegistry`. The first soul found becomes the active soul. Use `soul_list` and `soul_switch` to manage which soul is active at runtime. If both `SOUL_PATH` and `SOUL_DIR` are set, `SOUL_PATH` takes priority as the initially active soul.

### Auto-detect (no env var needed)

When neither `SOUL_DIR` nor `SOUL_PATH` is set, the server auto-detects soul files:

1. **`.soul/` in CWD** — if a non-empty `.soul/` directory exists in the current working directory, it is used as `SOUL_DIR`.
2. **`~/.soul/` fallback** — if CWD has no `.soul/` (or it is empty), the server checks `~/.soul/` as a user-level default.

This means running `soul-mcp` in a project with a `.soul/` folder just works — no env vars needed.

## Configuration

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/path/to/aria.soul"
      }
    }
  }
}
```

### Cursor / VS Code

Add to your MCP settings (`.cursor/mcp.json` or equivalent):

```json
{
  "mcpServers": {
    "soul": {
      "command": "soul-mcp",
      "env": {
        "SOUL_PATH": "/path/to/aria.soul"
      }
    }
  }
}
```

### Custom MCP Client

Any client that speaks the Model Context Protocol over stdio can connect. The server uses FastMCP's default stdio transport.

## Tools (29)

All tools are prefixed `soul_` to avoid name collisions when running alongside other MCP servers. The 29 tools break down as: 9 soul management, 5 memory, 5 context (LCM), 5 psychology pipeline (v0.2.7), 3 trust chain (`soul_verify`, `soul_audit`, `soul_prune_chain`), 1 eval (v0.5.0 #160), and 1 graph (`soul_graph_query`, v0.5.0 #108/#190).

**Multi-soul targeting:** When the server is running with `SOUL_DIR` and multiple souls are loaded, all tools accept an optional `soul` parameter (string) to target a specific soul by name or ID. If omitted, the tool operates on the currently active soul.

---

### `soul_birth`

Create a new soul with persistent identity and memory.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | The soul's name |
| `archetype` | `str` | `""` | Archetype (e.g. "The Compassionate Creator") |
| `values` | `list[str]` | `[]` | Core values for significance scoring |

**Returns:** JSON with `name`, `did`, and `status: "born"`.

---

### `soul_observe`

Process an interaction through the full psychology pipeline. Extracts facts, detects sentiment, gates episodic storage, updates the self-model.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_input` | `str` | required | What the user said |
| `agent_output` | `str` | required | What the agent responded |
| `channel` | `str` | `"mcp"` | Source channel identifier |
| `soul` | `str \| None` | `None` | Target soul name (uses active soul if omitted) |
| `user_id` | `str \| None` | `None` | Multi-user attribution (#46). When set, every memory written during this call is stamped with the user_id, and the per-user bond is strengthened instead of the default bond. |

**Returns:** JSON with `status`, `soul`, `mood`, `energy`, and `user_id` (echoed back).

---

### `soul_remember`

Store a memory directly, bypassing the observe pipeline.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | required | The memory content |
| `importance` | `int` | `5` | Importance on a 1-10 scale |
| `memory_type` | `str` | `"semantic"` | One of: `episodic`, `semantic`, `procedural`, `social`. The `core` type is rejected — use `soul://memory/core` resource to read core memory. The `social` value (#41) targets the relationship layer. |
| `emotion` | `str` | `None` | Optional emotion label (e.g. "joy", "frustration") |
| `domain` | `str` | `"default"` | Domain sub-namespace inside the layer (#41), e.g. `"finance"` or `"legal"`. |

**Returns:** JSON with `memory_id`, `type`, `domain`, and `importance`.

---

### `soul_recall`

Search the soul's memories by natural language query. Results are ranked by ACT-R activation scoring (recency, frequency, emotional intensity, query relevance).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Search query |
| `limit` | `int` | `5` | Maximum number of results |
| `soul` | `str \| None` | `None` | Target soul name (uses active soul if omitted) |
| `user_id` | `str \| None` | `None` | Multi-user filter (#46). When set, restrict results to memories attributed to this `user_id`, plus any legacy entries with no `user_id`. When unset, returns all memories regardless of attribution. |
| `layer` | `str \| None` | `None` | Restrict recall to one layer (#41). Accepts built-in names (`episodic`, `semantic`, `procedural`, `social`) or any custom layer name. |
| `domain` | `str \| None` | `None` | Restrict recall to one domain sub-namespace (#41), e.g. `"finance"`. |

**Returns:** JSON with `count`, `soul`, and `memories` array. Each memory includes `id`, `type`, `layer`, `domain`, `content`, `importance`, `emotion`, and `user_id`.

---

### `soul_reflect`

Trigger a reflection and memory consolidation pass. The soul reviews recent interactions, identifies themes, summarizes patterns, and generates self-insights. Requires a `CognitiveEngine` (LLM) for full power; returns a skip status without one.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| (none) | | | |

**Returns:** JSON with `status` and either `themes`, `emotional_patterns`, `self_insight` (on success) or `reason` (on skip).

---

### `soul_dream`

Run an offline dream cycle — batch memory consolidation. Reviews accumulated episodes to detect topic patterns, extract recurring procedures, consolidate the knowledge graph, and propose personality evolution. No LLM required — all pattern detection is heuristic-based.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |
| `since` | `str` | `None` | ISO datetime — only review episodes after this time |

**Returns:** JSON `DreamReport` with `topic_clusters`, `detected_procedures`, `behavioral_trends`, `graph_consolidation`, `evolution_insights`, and consolidation stats.

---

### `soul_state`

Get the soul's current mood, energy, focus, social battery, and lifecycle stage.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| (none) | | | |

**Returns:** JSON with `mood`, `energy`, `focus`, `social_battery`, and `lifecycle`.

`focus` is recomputed from interaction density at call time (unless a manual override is in place — see `soul_feel` below). Bands with default thresholds: `low` (no interactions in the last hour), `medium` (1-2), `high` (3-9), `max` (10+).

---

### `soul_feel`

Update the soul's emotional state directly.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mood` | `str` | `None` | One of: `neutral`, `curious`, `focused`, `tired`, `excited`, `contemplative`, `satisfied`, `concerned` |
| `energy` | `float` | `None` | Energy **delta** (-100 to 100). Positive increases, negative decreases. Clamped to 0-100 after application. |
| `focus` | `str` | `None` | Lock focus to `low`, `medium`, `high`, or `max`. Pass `auto` to clear the lock and re-enable density-driven focus. |

**Returns:** JSON with updated `mood`, `energy`, `focus`, and `focus_override`.

Note: `energy` is a delta, not an absolute value. Passing `energy: -10` drains 10 points from the current level. `focus` is an absolute level, not a delta.

---

### `soul_prompt`

Generate the complete system prompt for LLM injection. Includes identity, DNA, personality traits, core memory, current state, and self-model insights.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| (none) | | | |

**Returns:** Plain text system prompt string.

---

### `soul_save`

Persist the soul to disk. Creates a directory structure with config, memory, and state files.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | `None` | Base directory path. Creates `<path>/<soul_id>/` with soul data. Uses original `SOUL_PATH` or `~/.soul/<soul_id>/` if omitted. |

**Returns:** JSON with `status` and `name`.

---

### `soul_export`

Export the soul as a portable `.soul` file (zip archive). Contains identity, DNA, memory tiers, state, and self-model -- everything needed to restore the soul on another machine.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Output file path (should end in `.soul`) |

**Returns:** JSON with `status`, `path`, and `name`.

---

### `soul_list`

List all souls known to the server. When running with `SOUL_DIR`, this returns every soul in the registry. When running with a single `SOUL_PATH`, it returns that one soul.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| (none) | | | |

**Returns:** JSON with `souls` array. Each entry includes `name`, `did`, `active` (boolean), and `lifecycle`.

---

### `soul_switch`

Switch the active soul. The newly active soul becomes the target for all subsequent tool calls that omit the `soul` parameter.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `soul` | `str` | required | Name or DID of the soul to activate |

**Returns:** JSON with `status`, `name`, and `did` of the newly active soul. Returns an error if the soul is not found in the registry.

---

### `soul_reload`

Reload a soul from disk, picking up any changes made externally (e.g. by another process, a different session, or manual editing). The in-memory soul is replaced with the freshly loaded version.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON with `status`, `name`, `path`, `format`, and `memories` count.

---

## Psychology Pipeline Tools (5) — v0.2.7

### `soul_skills`

View the soul's learned skills with level, XP, and progress.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `soul` | string | No | Target soul name (uses active soul if omitted) |

**Returns:** JSON with `skills` array (id, name, level, xp, xp_to_next) and `total` count.

### `soul_evaluate`

Evaluate an interaction against a rubric and build evaluation history.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_input` | string | Yes | What the user said |
| `agent_output` | string | Yes | What the agent responded |
| `domain` | string | No | Self-model domain for rubric selection (auto-detected if omitted) |
| `soul` | string | No | Target soul name |

**Returns:** JSON with `rubric`, `overall_score`, `criteria` array, `learning` string, and `eval_history_size`.

### `soul_learn`

Evaluate an interaction and create a learning event if notable.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_input` | string | Yes | What the user said |
| `agent_output` | string | Yes | What the agent responded |
| `domain` | string | No | Domain for rubric selection |
| `soul` | string | No | Target soul name |

**Returns:** JSON with `learning_event` (id, lesson, domain, score, confidence, skill_id) or null if score is in medium range.

### `soul_evolve`

Manage soul evolution — propose, approve, reject, or list trait mutations.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | No | One of: `list`, `propose`, `approve`, `reject` (default: `list`) |
| `trait` | string | No | Trait path (e.g. `communication.warmth`) — for propose |
| `new_value` | string | No | New value for the trait — for propose |
| `reason` | string | No | Why this mutation is proposed — for propose |
| `mutation_id` | string | No | ID of mutation to approve/reject |
| `soul` | string | No | Target soul name |

**Returns:** JSON with `pending` mutations array and `history_count` (for list), or mutation details (for propose/approve/reject).

### `soul_bond`

View or modify the soul's bond strength.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `strengthen` | float | No | Amount to strengthen (negative to weaken). Omit to just view. |
| `soul` | string | No | Target soul name |

**Returns:** JSON with `bond_strength` and `interaction_count`.

---

## Context Tools — LCM (5)

Lossless Context Management tools for within-session context. Messages go into an immutable SQLite store. Three-level compaction runs automatically when the token budget is approached: Summary (LLM), Bullets (LLM), Truncation (deterministic). After compaction, `grep` still searches originals and `expand` recovers them — nothing is lost.

---

### `soul_context_ingest`

Ingest a message into the soul's context store. Messages are immutable once stored. Compaction runs automatically when the token budget is approached.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role` | `str` | required | Message role (e.g. `"user"`, `"assistant"`, `"system"`) |
| `content` | `str` | required | Message content text |
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON with `message_id`, `soul`, `total_messages`, and `total_tokens`.

---

### `soul_context_assemble`

Assemble a context window that fits within the token budget. Returns ordered nodes (verbatim + compacted) ready for LLM injection. Applies three-level compaction as needed.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_tokens` | `int` | `100000` | Token budget for the assembled context |
| `system_reserve` | `int` | `0` | Tokens to reserve for system prompts / tool schemas |
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON with `soul`, `node_count`, `total_tokens`, `compaction_applied`, and `nodes` array. Each node includes `level`, `content`, `token_count`, and `seq_range`.

---

### `soul_context_grep`

Search the soul's context history by regex pattern. Searches the immutable message store — even compacted messages are searchable since originals are never deleted.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern` | `str` | required | Regex pattern to search for |
| `limit` | `int` | `20` | Maximum number of results |
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON with `soul`, `count`, and `results` array. Each result includes `message_id`, `seq`, `role`, and `snippet`.

---

### `soul_context_expand`

Expand a compacted node back to its original messages. Walks the DAG to recover verbatim content that was summarized or truncated. This is the "lossless" in Lossless Context Management.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_id` | `str` | required | The ID of the compacted node to expand |
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON with `soul`, `node_id`, `level`, `original_count`, and `messages` array. Each message includes `id`, `role`, `content`, and `seq`.

---

### `soul_context_describe`

Get a metadata snapshot of the soul's context store. Returns message count, token totals, date range, and compaction statistics.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON with `soul`, `total_messages`, `total_nodes`, `total_tokens`, `compaction_stats`, and `date_range`.

---

### `soul_verify`

Verify the trust chain integrity for a soul (#42). The trust chain is the soul's append-only signed history of audit-worthy actions (memory writes, supersedes, evolution events, learning events, bond changes). A chain that fails verification has been tampered with.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `{soul, did, valid, length, signers, first_failure}`.

`first_failure` is `null` on a valid chain, or `{seq, reason}` on a tampered chain.

---

### `soul_audit`

Return a human-readable timeline of signed actions on the soul's trust chain (#42). Each row carries `{seq, timestamp, action, actor_did, payload_hash}`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `action_prefix` | `str` | `None` | Filter to actions starting with this prefix (e.g. `memory.`) |
| `limit` | `int` | `None` | Show only the most recent N entries |
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `{soul, did, entries: [...]}`.

Payloads themselves are not on chain — only their hashes — so this tool surfaces *what changed when*, not *what was written*.

---

### `soul_graph_query`

Discriminated query tool for the soul's knowledge graph (#108, #190). The `kind` parameter selects the operation:

| `kind` | Required params | Returns |
|--------|----------------|---------|
| `nodes` | none (filters: `type`, `name_match`, `limit`) | `{count, nodes: [...]}` |
| `edges` | none (filters: `source`, `target`, `relation`) | `{count, edges: [...]}` |
| `neighbors` | `node_id` (optional: `depth`, `types`) | `{start, depth, count, nodes: [...]}` |
| `path` | `source_id`, `target_id` (optional: `max_depth`) | `{found, source, target, edges: [...]}` |
| `subgraph` | `node_ids` | `{nodes: [...], edges: [...]}` |
| `mermaid` | none | `{mermaid: "graph LR ..."}` |
| `stats` | none | `{node_count, edge_count, types: {...}, relations: {...}}` |

```json
{
  "kind": "neighbors",
  "node_id": "Alice",
  "depth": 2,
  "types": ["person", "tool"]
}
```

Unknown `kind` values return `{"error": "unknown kind: ..."}` with no exception. All responses are JSON.

The graph is read-mostly: mutations land via `soul_observe` (which runs the typed-ontology extractor and emits `graph.entity_added` / `graph.relation_added` trust-chain entries). There is no MCP tool for direct graph mutation in 0.5.0 — keep edits flowing through observation so the audit trail stays complete.

---

### `soul_prune_chain`

Compress old trust-chain history into a signed `chain.pruned` marker (#203). Touch-time stub for v0.5.0. Returns a dry-run preview by default; pass `apply=true` to actually mutate the chain. Genesis (seq=0) is always preserved.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `keep` | `int` | `None` | Length threshold. When the chain has more than `keep` entries, every non-genesis entry is compressed into a single signed marker. Defaults to `Biorhythms.trust_chain_max_entries`. |
| `apply` | `bool` | `false` | When `false` (default), return a dry-run preview only. When `true`, mutate the chain. |
| `reason` | `str` | `manual` | Free-form label written onto the marker payload. |
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted). |

**Returns:** JSON `{soul, did, applied, summary, chain_length, keep}`. `summary` carries `{count, low_seq, high_seq, reason, marker_seq}`.

When the chain is already at or below `keep`, the tool reports `applied=false` with a zero-count summary even if `apply=true` was passed (no marker is written for a no-op). When neither `keep` nor a biorhythm cap is set, the tool returns `{applied: false, error: "..."}`.

The mutation is staged into the active soul; the registry's auto-save persists it on shutdown. The full archival design (separate archive directory with checkpoint entries) is deferred to v0.5.x.

---

### `soul_eval`

Run a YAML eval spec against the active soul (#160). Unlike the CLI `soul eval` command — which births a fresh soul from the spec's `seed` block — this MCP tool runs against the soul that is already loaded, so an agent can self-evaluate against its current state.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `yaml_path` | `str` | `None` | Filesystem path to a `.yaml` / `.yml` spec (mutually exclusive with `yaml_string`) |
| `yaml_string` | `str` | `None` | Raw YAML text — handy when an agent generates its own cases |
| `case_filter` | `str` | `None` | Run only cases whose name contains this substring |
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `{spec_name, cases: [...], duration_ms, pass_count, fail_count, skip_count, error_count}`.

The `seed` block on the spec is intentionally ignored — the soul's live memories, OCEAN, bonds, and state are the seed. Only `cases` run. Pass `yaml_path` **or** `yaml_string`, not both.

See [eval-format.md](eval-format.md) for the YAML schema and the supported scoring kinds (keyword / regex / semantic / judge / structural).

---

### `soul_confirm` (v0.5.0, #192)

Refresh activation on a memory the agent has just verified.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `memory_id` | `str` | required | ID of the memory to confirm |
| `user_id` | `str \| None` | `None` | Optional user_id recorded on the chain entry |
| `soul` | `str \| None` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `{status, soul, memory_id, tier, weight}`. `status` is `"confirmed"` on hit, `"not_found"` otherwise.

---

### `soul_update` (v0.5.0, #192)

Patch a memory in place inside the reconsolidation window (PE in `[0.2, 0.85)`).

The window opens whenever a recall surfaces this id and stays open for one hour. The tool runs a small recall against the current entry content first so the window opens in this single call. Outside the window the call returns `{status: "error", error: "ReconsolidationWindowClosedError"}` so the agent can promote to `soul_supersede`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `memory_id` | `str` | required | ID of the memory to patch |
| `patch` | `str` | required | Replacement content |
| `prediction_error` | `float` | `0.5` | PE in `[0.2, 0.85)` |
| `user_id` | `str \| None` | `None` | Optional user_id recorded on the chain entry |
| `soul` | `str \| None` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `{status, soul, memory_id, tier, new_content, prediction_error}` on success. PE outside the band returns `{status: "error", error: "PredictionErrorOutOfBandError"}`.

---

### `soul_supersede` (v0.5.0, #192 — extends 0.4.0)

Write a new memory and link the old as superseded (PE >= 0.85).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `old_id` | `str` | required | ID of the memory being replaced |
| `new_content` | `str` | required | Content for the new memory |
| `reason` | `str \| None` | `None` | Optional free-form reason recorded in the audit trail |
| `prediction_error` | `float` | `0.85` | PE in `[0.85, 1.0]` |
| `importance` | `int` | `5` | Importance score for the new memory (1-10) |
| `user_id` | `str \| None` | `None` | Optional user_id recorded on the chain entry |
| `soul` | `str \| None` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `{status, soul, old_id, new_id, reason, prediction_error}` on success. PE below 0.85 returns `{status: "error", error: "PredictionErrorOutOfBandError"}`.

The new entry's `supersedes` back-edge points at `old_id`, and `old.superseded_by` points at the new entry. Recall surfaces the new entry; the provenance walker climbs the chain.

---

### `soul_purge` (v0.5.0, #192)

Hard delete a memory (GDPR / privacy / safety). Defaults to dry-run preview — pass `apply=true` to commit.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `memory_id` | `str` | required | ID of the memory to hard-delete |
| `apply` | `bool` | `false` | Must be true to actually delete |
| `user_id` | `str \| None` | `None` | Optional user_id recorded on the chain entry |
| `soul` | `str \| None` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `{status, soul, memory_id, tier, prior_payload_hash}`. `status` is `"purged"` on hit (with `apply=true`), `"preview"` on dry-run, `"not_found"` when the id can't be resolved.

The trust chain still records the purge with the prior payload hash so verifiers can later prove the entry once existed and was deleted, without storing the deleted content.

---

### `soul_reinstate` (v0.5.0, #192)

Restore a forgotten memory to full retrieval weight. The inverse of `soul_forget`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `memory_id` | `str` | required | ID of the memory to reinstate |
| `user_id` | `str \| None` | `None` | Optional user_id recorded on the chain entry |
| `soul` | `str \| None` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `{status, soul, memory_id, tier, weight}`. `status` is `"reinstated"` on hit, `"not_found"` when the id can't be resolved (typically because the entry was purged).

---

### `soul_forget` (v0.5.0 semantic shift)

Forget memories matching a query — **v0.5.0 (#192) shifted from hard delete to non-destructive weight-decay**. Matched entries have their `retrieval_weight` dropped below the recall floor so they stop surfacing, but stay on disk and can be restored via `soul_reinstate`. For genuine deletion (GDPR / safety) call `soul_purge`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Search query for memories to weight-decay |
| `confirm` | `bool` | `false` | Must be true to actually run the decay (safety gate) |
| `soul` | `str \| None` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `{status, soul, query, total, tiers}`. `status` is `"forgotten"` on apply, `"preview"` on dry-run.

---

### `soul_optimize`

Run the autonomous self-improvement loop against the active soul (#142). Drives the eval-improve-eval cycle: run an eval, propose knob changes (OCEAN traits, persona text, memory thresholds, bond strength) for failing cases, re-run the eval, keep changes that improve the score, revert otherwise. Pairs with [`soul_eval`](#soul_eval) so "improvement" is a measurable signal rather than a vibe.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `yaml_path` | `str` | `None` | Filesystem path to a `.yaml` / `.yml` eval spec (mutually exclusive with `yaml_string`) |
| `yaml_string` | `str` | `None` | Raw YAML eval spec text |
| `iterations` | `int` | `10` | Maximum loop iterations |
| `target_score` | `float` | `1.0` | Stop early when the eval score reaches this threshold |
| `apply` | `bool` | `false` | Keep changes and append `soul.optimize.applied` chain entries when `true` (default `false` — dry-run) |
| `soul` | `str` | `None` | Target soul name (uses active soul if omitted) |

**Returns:** JSON `OptimizeResult`: `spec_name`, `baseline_score`, `final_score`, `target_score`, `iterations_run`, `convergence_iteration`, `applied`, `steps` (each with `iteration`, `knob_name`, `before`, `after`, `score_before`, `score_after`, `kept`, `reason`), `knobs_touched`, `duration_ms`.

The spec's `seed` block is intentionally ignored — the active soul's live state is the seed.

**Safety rails.** `apply=False` is the default. In that mode every change applied during the run is reverted at the end and no trust chain entries are written. Set `apply=True` to keep the winning trajectory; per-kept-change `soul.optimize.applied` entries are appended to the soul's signed audit log. Reverted proposals never write chain entries either way.

See [soul-optimize.md](soul-optimize.md) for the concept overview and the knob model. See [eval-format.md](eval-format.md) for how to author the eval that drives the loop.

---

## MCP Sampling Engine

When running as an MCP server inside Claude Code, Claude Desktop, or any MCP host, the soul delegates cognitive tasks (sentiment analysis, fact extraction, entity extraction, significance scoring, reflection, context compaction) to the **host LLM** via `ctx.sample()`. No API key is needed — the host provides the model.

The engine is lazily constructed on the first tool call that carries a FastMCP Context. Once created, it is wired into all loaded souls via `Soul.set_engine()` and reused for the remainder of the session. Tools that trigger cognitive work (`soul_observe`, `soul_reflect`, `soul_birth`) accept a `ctx` parameter for this purpose.

Without an MCP host (e.g. when using the Python API directly), you can plug in any LLM by implementing the `CognitiveEngine` protocol (`async def think(self, prompt: str) -> str`). Without any engine, the soul falls back to heuristic processing (pattern-based sentiment, rule-based fact extraction).

---

## Resources (3)

Resources provide read-only access to soul data. MCP clients can subscribe to these URIs for live state.

| URI | Returns |
|-----|---------|
| `soul://identity` | Full identity JSON: DID, name, archetype, born date, bonded_to, core values, origin story |
| `soul://memory/core` | Core memory: `persona` (self-description) and `human` (what the soul knows about the user) |
| `soul://state` | Current state: mood, energy, focus, social battery, lifecycle stage |

## Prompts (2)

Prompts are pre-built text templates that MCP clients can request.

| Name | Purpose |
|------|---------|
| `soul_system_prompt_template` | Complete system prompt template for LLM context injection. Combines DNA, identity, core memory, state, and self-model into a single prompt string. (Renamed from `soul_system_prompt` in v0.2.3.) |
| `soul_introduction` | First-person self-introduction. Example: "I'm Aria, The Compassionate Creator. My core values are empathy, curiosity. I'm currently feeling curious with 85% energy." |

## Programmatic Usage

You can also use the MCP server from Python without running it as a subprocess:

```python
from fastmcp import Client
from soul_protocol.mcp import create_server

mcp = create_server()

# Use with FastMCP's in-process client
async with Client(mcp) as client:
    result = await client.call_tool("soul_birth", {"name": "Aria"})
    print(result.data)

# Or compose with other MCP servers in a larger system
```

## Design Notes

- **Multi-soul via SoulRegistry.** When `SOUL_DIR` is set, the server loads all discovered souls into a `SoulRegistry` and exposes `soul_list` / `soul_switch` for runtime selection. One soul is active at a time; all tools default to it unless a `soul` parameter is provided. For single-soul setups (`SOUL_PATH` only), the registry holds one entry and `soul_switch` is a no-op.
- **All tools are prefixed `soul_`.** This avoids name collisions when a client connects to several MCP servers simultaneously (e.g. soul + filesystem + database).
- **Global state -- not thread-safe.** The server uses module-level state. Do not call `soul_observe` concurrently from multiple threads. Sequential tool calls from a single MCP client are fine.
- **Stateful lifecycle.** The soul persists in memory across tool calls within a session. Call `soul_save` or `soul_export` to persist before the server shuts down.
