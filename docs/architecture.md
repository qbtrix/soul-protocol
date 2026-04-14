# Soul Protocol -- Architecture

> Current implementation architecture, module dependencies, memory layers, and data flow.

**Date:** 2026-04-13
**Version:** 0.3.0 (draft — org-level architecture additions pending merge)

---

## 0. Architectural Evolution: Per-Soul → Per-Org

Up through v0.2.x, Soul Protocol was a per-soul memory system — one `.soul` file held identity, OCEAN personality, and a multi-tier memory system for a single agent or user. That model is unchanged and still works standalone.

**v0.3 adds a new layer above it:** the **Org** — a boundary that holds multiple souls (root, users, agents), a shared append-only event journal, and a credential broker for external data sources. The new primitives are:

- **Org Journal** — append-only, UTC-stamped, scope-tagged `EventEntry` stream. Every action in the org writes one event. SQLite WAL at `~/.pocketpaw/org/journal.db`.
- **Root Agent** — one per org. Undeletable governance identity. Owns the journal, the scope tree, the DID chain. No conversational surface — structured inputs only.
- **Retrieval Router + Credential Broker** — dispatches queries across local projections and external sources. `DataRef` payloads enable Zero-Copy federation to live systems (Salesforce, Drive, Snowflake) without ETL.
- **Decision Traces** — `agent.proposed` + `human.corrected` event pairs chained via `causation_id`. Foundation for the compounding pattern that differentiates Paw OS from bolted-on agent products.
- **Pockets as scope nodes** — pockets (workspaces where agents + humans collaborate) are not souls; they're scope tree entries with journal slices. Identity stays with souls; activity stays in the journal.

The per-soul architecture in Sections 1–6 below is still authoritative for how a single soul works. Sections 7–12 describe the new org layer and how it relates.

**Migration posture:** additive. Existing `.soul` files work unchanged. The journal is opt-in via `paw os init`. Future phases will reposition soul memory as a projection over the journal; for now both remain independent write paths.

---

## 1. Two-Layer Architecture

The codebase separates concerns into a data/storage layer ("core") and an intelligence layer ("engine"). This was not in the original vision -- it emerged from the v0.2.0 psychology-informed memory work.

```
+===========================================================================+
|                          ENGINE LAYER                                      |
|  Intelligence, scoring, and cognition                                      |
|                                                                            |
|  +------------------+  +------------------+  +------------------+          |
|  | cognitive/       |  | memory/          |  | memory/          |          |
|  |   engine.py      |  |   activation.py  |  |   self_model.py  |          |
|  |   prompts.py     |  |   attention.py   |  |   sentiment.py   |          |
|  |                  |  |   strategy.py    |  |                  |          |
|  +------------------+  +------------------+  +------------------+          |
|                                                                            |
|  CognitiveEngine protocol       ACT-R scoring          Klein self-concept  |
|  HeuristicEngine fallback       Significance gate       Somatic markers    |
|  CognitiveProcessor orchestrator  Spreading activation   EMA mood inertia  |
+===========================================================================+
           |                    |                    |
           v                    v                    v
+===========================================================================+
|                           CORE LAYER                                       |
|  Data models, stores, serialization, and I/O                               |
|                                                                            |
|  +----------+  +----------+  +----------+  +----------+  +----------+     |
|  | types.py |  | memory/  |  | export/  |  | storage/ |  | parsers/ |     |
|  | (models) |  |  core.py |  |  pack.py |  |  file.py |  |  md.py   |     |
|  |          |  | epis.py  |  | unpack.py|  | proto.py |  |  yaml.py |     |
|  |          |  |  sem.py  |  |          |  | mem.py   |  |  json.py |     |
|  |          |  | proc.py  |  |          |  |          |  |          |     |
|  |          |  | graph.py |  |          |  |          |  |          |     |
|  |          |  | recall.py|  |          |  |          |  |          |     |
|  |          |  | search.py|  |          |  |          |  |          |     |
|  +----------+  +----------+  +----------+  +----------+  +----------+     |
|                                                                            |
|  +----------+  +----------+  +----------+  +----------+  +----------+     |
|  | soul.py  |  |identity/ |  |  dna/    |  |  state/  |  |evolution/|     |
|  | (facade) |  |  did.py  |  | prompt.py|  | manager  |  | manager  |     |
|  +----------+  +----------+  +----------+  +----------+  +----------+     |
+===========================================================================+
           |                    |
           v                    v
+===========================================================================+
|                       INTERFACE LAYER                                      |
|  External-facing APIs                                                      |
|                                                                            |
|  +------------------+     +------------------+                             |
|  | cli/main.py      |     | mcp/server.py    |                             |
|  | (Click commands)  |     | (FastMCP tools)  |                             |
|  +------------------+     +------------------+                             |
+===========================================================================+
```

---

## 2. Module Dependency Graph

Arrows indicate "imports from". Only significant dependencies shown.

```
soul.py (main facade)
  |
  +---> types.py (all Pydantic models)
  +---> identity/did.py
  +---> dna/prompt.py
  +---> memory/manager.py
  |       |
  |       +---> memory/core.py -------> types.py
  |       +---> memory/episodic.py ---> types.py
  |       +---> memory/semantic.py ---> types.py
  |       +---> memory/procedural.py -> types.py
  |       +---> memory/graph.py
  |       +---> memory/recall.py
  |       |       +---> memory/activation.py
  |       |       |       +---> memory/search.py
  |       |       |       +---> memory/strategy.py (protocol)
  |       |       +---> memory/episodic.py
  |       |       +---> memory/semantic.py
  |       |       +---> memory/procedural.py
  |       +---> memory/self_model.py --> memory/search.py
  |       +---> memory/attention.py ---> memory/sentiment.py
  |       +---> memory/search.py
  |       +---> cognitive/engine.py (lazy import)
  |
  +---> state/manager.py ---------> types.py
  +---> evolution/manager.py -----> types.py
  +---> export/pack.py -----------> dna/prompt.py, types.py
  +---> export/unpack.py ---------> types.py
  +---> storage/file.py ----------> dna/prompt.py, types.py
  +---> cognitive/engine.py ------> cognitive/prompts.py, types.py

cli/main.py
  +---> soul.py (lazy import)
  +---> storage/file.py

mcp/server.py
  +---> soul.py
  +---> types.py
  +---> exceptions.py

crypto/encrypt.py
  +---> cryptography (external, no internal deps)

parsers/markdown.py
  +---> identity/did.py, types.py, yaml (external)

parsers/yaml_parser.py
  +---> types.py, yaml (external)

parsers/json_parser.py
  +---> types.py
```

### Circular Dependency Avoidance

The primary circular risk is `cognitive/engine.py <-> memory/manager.py`. This is resolved via:
- `memory/manager.py` uses a lazy import (`from soul_protocol.cognitive.engine import ...` inside `__init__`)
- `cognitive/engine.py` uses `TYPE_CHECKING` for `SelfModelManager`
- `memory/attention.py` and `memory/sentiment.py` have no dependency on `cognitive/`

---

## 3. Memory System Layers

```
+=======================================================================+
|                    SOUL MEMORY SYSTEM                                  |
|                                                                        |
|  +--------- CORE MEMORY (CoreMemoryManager) ---------+               |
|  |  Always in context. ~500 tokens each.              |               |
|  |                                                    |               |
|  |  persona: "I am Aria, warm and creative..."       |               |
|  |  human:   "Alex prefers Python, works late..."    |               |
|  |                                                    |               |
|  |  Editable via edit_core_memory()                   |               |
|  +----------------------------------------------------+               |
|                          |                                             |
|                          v                                             |
|  +--------- RECALL MEMORY (RecallEngine) ------------+               |
|  |  Searchable via token overlap + ACT-R activation   |               |
|  |                                                    |               |
|  |  +-----------+  +-----------+  +-------------+    |               |
|  |  | EPISODIC  |  | SEMANTIC  |  | PROCEDURAL  |    |               |
|  |  | (events)  |  | (facts)   |  | (how-to)    |    |               |
|  |  |           |  |           |  |             |    |               |
|  |  | Capped at |  | Capped at |  | Uncapped    |    |               |
|  |  | 10,000    |  | 1,000     |  |             |    |               |
|  |  +-----------+  +-----------+  +-------------+    |               |
|  |                                                    |               |
|  |  Scoring: base_activation (ACT-R decay)            |               |
|  |         + spreading_activation (query relevance)   |               |
|  |         + emotional_boost (somatic markers)        |               |
|  +----------------------------------------------------+               |
|                          |                                             |
|                          v                                             |
|  +--------- KNOWLEDGE GRAPH (KnowledgeGraph) --------+               |
|  |  Entities + directed relationships                 |               |
|  |                                                    |               |
|  |  [Python] --type--> [technology]                   |               |
|  |  [Alex]   --uses--> [Python]                       |               |
|  |  [Alex]   --works_at--> [Interacly]               |               |
|  |                                                    |               |
|  |  Auto-populated from entity extraction             |               |
|  +----------------------------------------------------+               |
|                          |                                             |
|                          v                                             |
|  +--------- SELF-MODEL (SelfModelManager) -----------+               |
|  |  Klein's self-concept: "who am I based on what    |               |
|  |  I do?"                                            |               |
|  |                                                    |               |
|  |  Domains:  technical_helper (conf: 0.87, 42 ev)   |               |
|  |            problem_solver   (conf: 0.65, 18 ev)   |               |
|  |            creative_writer  (conf: 0.23, 3 ev)    |               |
|  |                                                    |               |
|  |  Relationship notes: {user: "Name: Alex;          |               |
|  |                        Works at: Interacly"}      |               |
|  +----------------------------------------------------+               |
|                                                                        |
|  +--------- GENERAL EVENTS (Conway Hierarchy) -------+               |
|  |  Theme-based episode clustering                    |               |
|  |                                                    |               |
|  |  "debugging session" -> [ep-001, ep-003, ep-007]  |               |
|  |  "architecture work" -> [ep-002, ep-005]          |               |
|  |                                                    |               |
|  |  Created during reflect() + consolidate()          |               |
|  +----------------------------------------------------+               |
+=======================================================================+
```

### Missing Memory Layers (from Vision)

```
  NOT IMPLEMENTED:

  +--------- WORKING MEMORY (volatile) ----------------+
  |  Current conversation context                       |
  |  Managed by the runtime, not the soul              |
  +----------------------------------------------------+

  +--------- ARCHIVAL MEMORY (deep storage) -----------+
  |  Full conversation transcripts                      |
  |  Compressed summaries                               |
  |  External storage links (vector DB, IPFS, etc.)    |
  +----------------------------------------------------+
```

---

## 4. Data Flow

### 4.1 Birth -> Interact -> Remember -> Recall -> Evolve -> Save

```
   BIRTH                        INTERACT
     |                              |
     v                              v
 Soul.birth()                 Soul.observe(interaction)
     |                              |
     |  Creates:                    |  Pipeline:
     |  - Identity (DID)            |  1. detect_sentiment() -> SomaticMarker
     |  - DNA (OCEAN)               |  2. assess_significance() -> SignificanceScore
     |  - Empty core memory         |  3. IF significant: store episodic
     |  - Default state             |  4. extract_facts() -> semantic memories
     |  - Evolution config          |  5. extract_entities() -> knowledge graph
     |                              |  6. update_self_model()
     v                              |  7. update state (energy, mood)
 Soul instance                      |  8. check evolution triggers
                                    v
                              Soul with memories
                                    |
                  +-----------------+-----------------+
                  |                                   |
                  v                                   v
            Soul.recall(query)                  Soul.reflect()
                  |                                   |
                  |  1. Search episodic               |  1. Review recent episodes
                  |  2. Search semantic               |  2. Identify themes
                  |  3. Search procedural             |  3. Summarize patterns
                  |  4. ACT-R activation score        |  4. Generate self-insight
                  |  5. Rank + return top N            |  5. Consolidate into memory
                  |  6. Update access timestamps       |
                  v                                   v
            List[MemoryEntry]                   ReflectionResult
                                                      |
                                               (auto-apply if enabled)
                  |                                   |
                  v                                   v
            Soul.save(path)                     Soul.export(path)
                  |                                   |
                  |  Atomic write to:                 |  Creates zip with:
                  |  ~/.soul/<soul_id>/               |  - manifest.json
                  |    soul.json                      |  - soul.json
                  |    state.json                     |  - dna.md
                  |    dna.md                         |  - state.json
                  |    memory/                        |  - memory/
                  |      core.json                    |    core.json
                  |      episodic.json                |    episodic.json
                  |      semantic.json                |    semantic.json
                  |      procedural.json              |    procedural.json
                  |      graph.json                   |    graph.json
                  |      self_model.json              |    self_model.json
                  |      general_events.json          |    general_events.json
                  v                                   v
            Saved to disk                       .soul file (portable)
```

### 4.2 Observe Pipeline Detail

```
Interaction (user_input + agent_output)
    |
    v
CognitiveProcessor.detect_sentiment(user_input)
    |
    |  HeuristicEngine path:           LLM path:
    |    Word-list matching              SENTIMENT_PROMPT -> engine.think()
    |    Intensity modifiers             Parse JSON response
    |    Negation detection              Validate valence/arousal
    |
    v
SomaticMarker (valence, arousal, label)
    |
    v
CognitiveProcessor.assess_significance(interaction, core_values, recent)
    |
    |  HeuristicEngine path:           LLM path:
    |    Token overlap for novelty       SIGNIFICANCE_PROMPT -> engine.think()
    |    Arousal for emotion             Parse JSON response
    |    Value word matching             Validate 3 dimensions
    |
    v
SignificanceScore (novelty, emotional_intensity, goal_relevance)
    |
    |  overall = 0.4*novelty + 0.35*emotion + 0.25*goal
    |  threshold = 0.25
    |
    +----> NOT significant?  Skip episodic storage
    |                        (but still extract facts)
    |
    +----> Significant?  Store in EpisodicStore
    |                    with somatic marker + significance
    |
    v
CognitiveProcessor.extract_facts(interaction, existing_facts)
    |
    |  HeuristicEngine path:           LLM path:
    |    18 regex patterns               FACT_EXTRACTION_PROMPT -> engine.think()
    |    Token-overlap dedup             Parse JSON array
    |    Template-based output           Validate each entry
    |
    v
List[MemoryEntry] (semantic facts)
    |
    |  Resolve conflicts (supersede old contradicting facts)
    |  Store in SemanticStore
    |
    |  If facts extracted but wasn't significant: promote to episodic
    |
    v
CognitiveProcessor.extract_entities(interaction)
    |
    |  Known tech terms + proper nouns
    |  Infer relationships (uses, builds, prefers, etc.)
    |
    v
List[entity dicts] --> Update KnowledgeGraph
    |
    v
CognitiveProcessor.update_self_model(interaction, facts, self_model)
    |
    |  HeuristicEngine path:           LLM path:
    |    Token matching vs domains       SELF_REFLECTION_PROMPT -> engine.think()
    |    Dynamic domain creation         Parse self_images + relationship_notes
    |    Keyword expansion               Update SelfModelManager
    |
    v
Updated SelfModelManager
    |
    v
StateManager.on_interaction(interaction, somatic)
    |
    |  Energy -= 2, Social Battery -= 5
    |  EMA-smooth valence
    |  Map to mood via label or quadrant
    |  Energy < 20? Override to TIRED
    |
    v
Updated SoulState
```

---

## 5. File Format (.soul Archive)

```
name.soul (zip, deflated)
|
+-- manifest.json          # SoulManifest: format version, dates, stats
+-- soul.json              # Full SoulConfig: identity, DNA, settings
+-- dna.md                 # Human-readable personality markdown
+-- state.json             # Current SoulState snapshot
+-- memory/
    +-- core.json          # CoreMemory: persona + human text
    +-- episodic.json      # List of MemoryEntry (episodic type)
    +-- semantic.json      # List of MemoryEntry (semantic type)
    +-- procedural.json    # List of MemoryEntry (procedural type)
    +-- graph.json         # KnowledgeGraph: entities + edges
    +-- self_model.json    # SelfModelManager: images + notes + keywords
    +-- general_events.json # List of GeneralEvent (Conway themes)
```

### Directory Format (.soul/ folder)

Same structure but unpacked on disk. Created by `soul init` or `soul.save_local()`.

```
.soul/
|
+-- soul.json
+-- dna.md
+-- state.json
+-- memory/
    +-- core.json
    +-- episodic.json
    +-- semantic.json
    +-- procedural.json
    +-- graph.json
    +-- self_model.json
    +-- general_events.json
```

---

## 6. External Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| pydantic >= 2.0 | All data models, validation, serialization | Yes |
| click >= 8.0 | CLI framework | Yes |
| pyyaml >= 6.0 | YAML parsing (soul.yaml, config files) | Yes |
| rich >= 13.0 | CLI rich text output (inspect, status) | Yes |
| cryptography >= 42.0 | Fernet encryption, PBKDF2, Ed25519 signing keys for root agent | Yes |
| fastmcp >= 0.4 | MCP server (optional extra) | No (mcp extra) |

No new runtime deps were added for the v0.3 org layer. SQLite is stdlib; Ed25519 uses the existing `cryptography` dependency; the retrieval router uses `concurrent.futures.ThreadPoolExecutor` from stdlib.

---

## 7. Org-Level Journal (v0.3+)

### 7.1 Purpose

Before v0.3, each subsystem (soul memory, kb-go, retrieval log, Fabric objects) had its own write path. That worked per-subsystem but produced drift across subsystems — timestamp formats, audit rules, and scope handling all diverged.

The journal unifies the write path. Every action in the org — retrievals, ingests, decisions, graduations, admin changes, agent spawns — appends one `EventEntry`. Existing subsystems become projections (materialized views) over the journal, rebuildable from events alone.

### 7.2 Module Layout

```
src/soul_protocol/
+-- spec/
|   +-- journal.py              # EventEntry, Actor, DataRef Pydantic models + ACTION_NAMESPACES
|   +-- decisions.py            # AgentProposal, HumanCorrection, DecisionGraduation
|   +-- retrieval.py            # RetrievalRequest/Result/Candidate, CandidateSource
|
+-- engine/
|   +-- journal/
|   |   +-- journal.py          # Journal high-level API + invariants
|   |   +-- backend.py          # JournalBackend Protocol
|   |   +-- sqlite.py           # SQLiteJournalBackend (WAL mode)
|   |   +-- schema.py           # SQL schema + migration helper
|   |   +-- exceptions.py
|   |
|   +-- retrieval/
|       +-- router.py           # RetrievalRouter (first/parallel/sequential)
|       +-- broker.py           # CredentialBroker Protocol + InMemoryCredentialBroker
|       +-- adapters.py         # SourceAdapter Protocol + MockAdapter + ProjectionAdapter
|       +-- exceptions.py
|
+-- cli/
    +-- paw_os.py               # paw os init / status / destroy subcommands
```

### 7.3 EventEntry

```python
class EventEntry(BaseModel):
    id: UUID
    ts: datetime                 # tz-aware UTC, monotonic per journal
    actor: Actor                 # kind + id + scope_context
    action: str                  # dot-separated namespace (e.g. "retrieval.query")
    scope: list[str]             # scope tags, non-empty, grammar matches spec #162
    causation_id: UUID | None    # prior event that caused this one
    correlation_id: UUID | None  # session/flow id
    payload: DataRef | dict      # inline data or external reference
    prev_hash: bytes | None      # optional hash-chain link
    sig: bytes | None            # optional signature over (id, ts, actor, action, prev_hash)
```

Invariants enforced at `Journal.append()`:

1. `ts` must be tz-aware UTC (naive datetimes rejected)
2. `ts` must be >= previous event's `ts` (monotonic)
3. `scope` must be non-empty
4. `actor` must be set (no anonymous writes)
5. `seq` auto-assigned by backend inside a `BEGIN IMMEDIATE` transaction for concurrent-writer safety

### 7.4 Action Namespace Catalog (initial)

```
# Governance (root-signed)
org.created, schema.migrated, user.admin_granted, user.admin_revoked,
scope.created, key.rotated, paw.os.destroyed

# Identity
agent.spawned, agent.retired, user.joined, user.left,
team.created, team.disbanded, soul.exported, soul.imported

# Memory & Knowledge
memory.remembered, memory.graduated, memory.forgotten,
kb.source.ingested, kb.article.compiled, kb.article.revised

# Retrieval & Fabric
retrieval.query, fabric.object.created, fabric.object.updated,
fabric.object.archived, scope.assigned, scope.revoked

# Decisions (the moat)
agent.proposed, human.corrected, decision.graduated

# Credentials & Zero-Copy
credential.acquired, credential.used, credential.expired, dataref.resolved

# Graduation & Policy
graduation.applied, policy.evaluated
```

New namespaces can be added additively; callers are free to ship unregistered actions (the catalog is a tuple, not a closed enum). Every action must remain past-tense and dot-separated.

### 7.5 Storage Tiers

| Tier | Backend | When to use | Capacity |
|------|---------|-------------|----------|
| Default | SQLite WAL, single file `journal.db` | Every install. Zero-ops, one file. | ~100GB |
| Cold | Parquet partitions + DuckDB | Events older than N months | TB-scale |
| Enterprise | Postgres | Multi-node, opt-in | Horizontally scalable |

Only SQLite WAL ships in v0.3. The `JournalBackend` protocol is designed to make Parquet/Postgres implementations additive without changing the Journal API.

### 7.6 Replay Semantics

Projections rebuild from the journal via `Journal.replay_from(seq)`:

- **Hermetic** for every action except `retrieval.query` with a DataRef payload. Rebuild is deterministic from the journal file alone.
- **Non-hermetic (bounded)** for `retrieval.query` events carrying DataRef payloads. Replay against a down/rate-limited/schema-changed source will produce different results or fail. This is acknowledged, not a bug — DataRef events are receipts of live queries, not reproducible facts.

Projections that consume DataRef events must declare themselves DataRef-aware. Consumers that aren't DataRef-aware subscribe only to the structured metadata (actor, ts, scope, causation_id) and ignore the payload.

---

## 8. Root Agent + Onboarding

### 8.1 Root Agent

One per Paw OS instance. Created during `paw os init`. Cannot be deleted. Signs every event that mutates governance state.

**Owns:**
- The journal (every event chains optionally to a `genesis` event signed by root's first keypair)
- The `org:*` scope tree root (all downstream scopes are children)
- The DID chain (every other agent/user DID is countersigned by root at creation)

**Does not do:**
- Conversational surface — never reachable by chat, DM, email, any channel adapter
- Free-text CLI input — admin CLI accepts structured inputs only (UUIDs, enums, integers, validated file paths). No argument is passed to an LLM as part of any root-signed operation. Human-readable output is rendered from structured journal data.
- Day-to-day workflow involvement — routine agent work happens through user-spawned agents. Root signs the *spawn* event, then stays out.
- Memory tier writes — root's "memory" is the journal itself.

### 8.2 Undeletability (three layers)

| Layer | Enforcement |
|-------|-------------|
| **File system** | `Soul.delete()` raises `SoulProtectedError` when `Identity.role == "root"`. `Soul.role` is stored in both `soul.json` and `manifest.json.stats.role` so the guard works without decrypting. |
| **Protocol** | Helper `check_root_undeletable(event, root_did)` rejects `agent.retired` / `soul.deleted` events whose actor.id matches root's DID. Called by projections + advisory. |
| **CLI** | `soul delete <path>` refuses on role=root. The only path to remove a root is `paw os destroy`, which tarballs the org state to `~/.pocketpaw/archives/` before wiping. |

### 8.3 Onboarding (`paw os init`)

Eight steps. Target runtime under five minutes.

| Step | What it does |
|------|--------------|
| 1. Org identity | Prompts/accepts org name, purpose, 3–5 values |
| 2. Founder user | Creates first user soul at `~/.pocketpaw/users/<name>.soul`, marked admin |
| 3. Root agent | Creates root soul with governance persona (hardcoded for now; swaps to #163's `load_template("governance")` once that lands) |
| 4. Keys | Generates Ed25519 keypair, stores private key at `~/.pocketpaw/org/keys/root.ed25519` with 0600 permissions (set via `os.open`, not post-chmod) |
| 5. Journal init | Creates `~/.pocketpaw/org/journal.db`, runs schema migration to v1 |
| 6. Genesis event | Appends `org.created` signed by root (event #1 for the life of the org) |
| 6b. Scope tree | Emits `scope.created` for `org:*` and up to 5 first-level scopes |
| 7. Starter fleet | Stub — records fleet choice as placeholder `agent.spawned` events; real install wires into pocketpaw #940 |
| 8. Invites | Stub — prints copy-paste hint for `paw user invite <email>`; actual invite flow is a future PR |

Idempotent: running twice on the same dir without `--force` refuses cleanly.

### 8.4 Status + Destroy

- `paw os status [--json]` — reads the journal, prints org name, values, root DID, event count, user count, agent count, scope tree
- `paw os destroy --data-dir PATH --confirm --i-mean-it` — tarballs the full org state to `~/.pocketpaw/archives/org-destroyed-<timestamp>.tar.gz`, then wipes the data dir. Without both flags or the typed org-name confirmation in interactive mode, refuses. Tarball failure aborts cleanly — wipe never happens without a successful archive.

---

## 9. Retrieval Router + Credential Broker

### 9.1 RetrievalRouter

Dispatches queries across candidate sources. Each source is either a local **projection** (soul memory, kb articles, fabric objects — built over the journal) or a **DataRef** source (live external system, queried at retrieval time).

```python
router = RetrievalRouter(journal=journal, broker=broker)
router.register_source(
    CandidateSource(name="soul_memory", kind="projection", scopes=["org:*"], adapter_ref="..."),
    ProjectionAdapter(callback=soul_recall_fn),
)
router.register_source(
    CandidateSource(name="drive", kind="dataref", scopes=["org:sales:*"], adapter_ref="..."),
    DriveAdapter(...),  # future — C2
)

result = router.dispatch(RetrievalRequest(
    query="Q3 pipeline forecasts",
    actor=actor,
    scopes=["org:sales:*"],
    strategy="parallel",
    timeout_s=10.0,
))
```

**Strategies:**
- `first` — tries sources one-by-one, returns the first non-empty result
- `parallel` — thread-pool across all scope-matching sources, merges by score
- `sequential` — walks sources in order, accumulates up to `limit` candidates

**Scope enforcement:** sources whose registered `scopes` don't overlap the request `scopes` are filtered out before dispatch. Scope match is bidirectional (a source registered `org:sales:*` matches a request `org:sales:leads` and vice versa).

**Journal emission:** if a journal is passed, the router emits a `retrieval.query` event per dispatch, payload is either inline (projection source) or DataRef (federated source). This is the audit trail for every retrieval.

### 9.2 CredentialBroker

Safe credential delegation for external sources:

```python
credential = broker.acquire(source="drive", scopes=["org:sales:*"])
# Short-lived (TTL 300s default). Per-scope scoping enforced.

result = adapter.query(request, credential)  # broker.ensure_usable + mark_used inside

broker.revoke(credential.id)  # optional; auto-expires otherwise
```

Rules:
1. Short-lived tokens only — `Credential.token` is `secrets.token_urlsafe(16)`, opaque to callers
2. Per-scope scoping — a credential acquired for `org:sales:*` raises `CredentialScopeError` if used by a requester in `org:support:*`
3. Full lifecycle audit — every acquire/use/expire emits a corresponding journal event (`credential.acquired`, `credential.used`, `credential.expired`)

### 9.3 SourceAdapter Protocol

```python
class SourceAdapter(Protocol):
    supports_dataref: bool

    def query(self, request: RetrievalRequest, credential: Credential | None) -> list[RetrievalCandidate]:
        ...
```

Two reference implementations ship:
- `MockAdapter` — fixed candidates + invocation tracking (tests)
- `ProjectionAdapter` — wraps a callable; represents the local-projection case (soul memory, kb, fabric)

Concrete adapters (Google Drive, Salesforce, Snowflake) are future work (C2).

---

## 10. Decision Traces

### 10.1 The loop

```
agent.proposed           human.corrected              decision.graduated
(proposal payload)  -->  (causation_id = ^)    -->    (supporting_correction_ids = [...])
```

An agent proposes an action. A human edits, accepts, or rejects it. A correction is recorded with `causation_id` pointing back to the proposal. Over N similar corrections with matching `structured_reason_tags`, the pattern graduates from episodic to semantic memory.

### 10.2 Payload Types

```python
class AgentProposal(BaseModel):
    proposal_kind: str              # "tool_call" | "message_draft" | "decision" | "custom:<ns>"
    summary: str                    # 1-3 sentence human-readable
    proposal: dict                  # structured (tool args, draft body, decision options)
    confidence: float | None
    alternatives: list[dict]
    context_refs: list[UUID]        # prior event IDs the agent consulted

class HumanCorrection(BaseModel):
    disposition: Literal["accepted", "edited", "rejected", "deferred"]
    corrected_value: dict | None
    correction_reason: str | None
    structured_reason_tags: list[str]   # for clustering
    edit_distance: float | None

class DecisionGraduation(BaseModel):
    pattern_summary: str
    supporting_correction_ids: list[UUID]
    graduated_to_tier: Literal["semantic", "core"]
    confidence: float
    applies_to: dict
```

### 10.3 Helpers

- `build_proposal_event()` / `build_correction_event()` — convenience constructors with correct `action` + payload wrapping
- `find_corrections_for(journal, proposal_id)` — query journal for all `human.corrected` events with matching causation_id
- `trace_decision_chain(journal, correlation_id)` — ordered proposal/correction events for a session or flow
- `cluster_correction_patterns(journal, since=None, min_occurrences=3)` — surfaces candidate patterns by clustering on sorted tag tuples. Floor for graduation logic (promotion itself is future work).

### 10.4 Wire-in (pending)

The spec lives in soul-protocol. The pocketpaw-side emit points — agent tool-call previews, draft approval UIs, edit-captured hooks — are a follow-up PR in that repo.

---

## 11. Projections (future, Phase 2)

Today's stores (soul memory, kb-go, Fabric) remain independent writers. Phase 2 of the migration repositions them as projections over the journal:

| Store | Becomes | Read pattern |
|-------|---------|--------------|
| Soul memory tiers | Projection: identity + bounded recent-N per tier | Semantic/episodic recall |
| kb-go wiki | Projection: compiled articles + BM25 index | "What do we know about X" |
| Fabric objects | Projection: scoped object store with filter-at-retrieval | "Give me visible deals in Q3" |
| Retrieval log | *Deleted as separate store* | Filter over journal `retrieval.query` events |

Rebuild is via `projection.rebuild_from_journal(start_event_id=None)`. Incremental projection updates record their last-seen event ID and resume from there.

---

## 12. Updated Storage Layout (v0.3+)

```
~/.pocketpaw/
+-- org/
|   +-- root.soul                    # undeletable root agent (zip)
|   +-- journal.db                   # SQLite WAL, append-only org truth
|   +-- journal_archive/             # cold Parquet partitions (future)
|   +-- keys/
|       +-- root.ed25519             # root signing key, 0600 perms
|
+-- teams/
|   +-- sales.soul                   # optional team souls
|
+-- agents/
|   +-- sales-lead.soul
|   +-- support-triage.soul
|
+-- users/
|   +-- prakash.soul                 # travels with human (identity only — activity stays in journal)
|
+-- archives/                        # tarballs from paw os destroy
|
+-- config.toml
```

Standalone `.soul` file mode (no org layer) is still supported for single-user / dev setups. Running the protocol against a `.soul` without an org journal is the v0.2.x behavior.

---

*Document updated 2026-04-13 for v0.3 org-layer additions. Sections 1-6 remain authoritative for per-soul internals; sections 7-12 describe the new org layer.*
