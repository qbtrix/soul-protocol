<!-- API Reference for soul-protocol v0.2.9+. Covers: Soul class (lifecycle, properties,
     memory, dream, state, evolution, persistence), all Pydantic types, protocols (CognitiveEngine,
     SearchStrategy), implementations (HeuristicEngine, TokenOverlapStrategy), and enums.
     Updated: 2026-04-30 — v0.5.0 (#203): Added Biorhythms.trust_chain_max_entries (touch-time
       chain pruning cap), TrustChainManager.prune(keep)/dry_run_prune(keep)/max_entries.
       Auto-prune fires at append() when the cap is reached.
     Updated: 2026-04-30 — v0.5.0 #201/#202: TrustEntry gains a non-cryptographic
       `summary` field. TrustChainManager.append accepts an optional `summary=` parameter
       that defaults to an action-keyed formatter registry. Soul.audit_log() rows now
       include a `summary` key.
     Updated: 2026-04-29 — v0.5.0 (#160): Added Evaluation section documenting the
       soul_protocol.eval module — EvalSpec, EvalCase, EvalResult, CaseResult, the five
       scoring kinds (keyword/regex/semantic/judge/structural), and run_eval /
       run_eval_against_soul / run_eval_file entry points.
     Updated: 2026-04-27 — Documented user-driven memory update primitives: Soul.forget_one
       (audited single-id delete), Soul.supersede (write new memory + link old.superseded_by),
       Soul.supersede_audit property. Rewrote stale soul.forget() entry to match the real
       signature (forget(query) → dict, not forget(memory_id) → bool). Added forget_entity /
       forget_before / forget_by_id signatures alongside.
     Updated: 2026-04-06 — Added soul.dream() method and DreamReport type. -->

# API Reference

> soul-protocol v0.2.9+

This is the complete public API reference for the `soul_protocol` package. Every class, method, field, and enum listed here is exported from `soul_protocol` and covered by semver guarantees.

All public symbols are importable directly:

```python
from soul_protocol import Soul, Interaction, MemoryType, CognitiveEngine
```

---

## Table of Contents

- [Soul Class](#soul-class)
  - [Constructor](#constructor)
  - [Lifecycle](#lifecycle)
  - [Properties](#properties)
  - [Memory Operations](#memory-operations)
  - [State](#state)
  - [Evolution](#evolution)
  - [Persistence](#persistence)
  - [Serialization](#serialization)
- [Types](#types)
  - [Identity](#identity)
  - [DNA / Personality](#dna--personality)
  - [Psychology](#psychology)
  - [Memory](#memory)
  - [State / Feelings](#state--feelings)
  - [Evolution](#evolution-types)
  - [Lifecycle](#lifecycle-types)
  - [Interaction](#interaction)
  - [Reflection](#reflection)
  - [Configuration](#configuration)
  - [Manifest](#manifest)
- [Protocols](#protocols)
  - [CognitiveEngine](#cognitiveengine)
  - [SearchStrategy](#searchstrategy)
- [Implementations](#implementations)
  - [HeuristicEngine](#heuristicengine)
  - [TokenOverlapStrategy](#tokenoverlapstrategy)
- [Enums](#enums)
  - [MemoryType](#memorytype)
  - [Mood](#mood)
  - [LifecycleState](#lifecyclestate)
  - [EvolutionMode](#evolutionmode)

---

## Soul Class

```python
from soul_protocol import Soul
```

`Soul` is the top-level object. It owns identity, DNA, memory, state, and evolution. All async methods must be awaited.

### Constructor

```python
Soul(config: SoulConfig, engine: CognitiveEngine | None = None, search_strategy: SearchStrategy | None = None) -> None
```

Direct construction from a `SoulConfig`. Most callers should use `Soul.birth()` or `Soul.awaken()` instead.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `SoulConfig` | required | Full soul configuration |
| `engine` | `CognitiveEngine \| None` | `None` | LLM backend for cognition |
| `search_strategy` | `SearchStrategy \| None` | `None` | Custom retrieval scoring |

### Lifecycle

#### `Soul.birth()`

```python
@classmethod
async def birth(
    cls,
    name: str,
    archetype: str = "",
    personality: str = "",
    values: list[str] | None = None,
    communication_style: str | None = None,
    bonded_to: str | None = None,
    engine: CognitiveEngine | None = None,
    search_strategy: SearchStrategy | None = None,
    **kwargs,
) -> Soul
```

Create a new soul with a unique DID. Sets lifecycle to `ACTIVE` and initializes core memory with the personality text (or a default `"I am {name}."`).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Display name |
| `archetype` | `str` | `""` | Character archetype description |
| `personality` | `str` | `""` | Origin story / persona text |
| `values` | `list[str] \| None` | `None` | Core values for significance scoring |
| `communication_style` | `str \| None` | `None` | Reserved for future use |
| `bonded_to` | `str \| None` | `None` | Entity this soul is bonded to |
| `engine` | `CognitiveEngine \| None` | `None` | LLM backend |
| `search_strategy` | `SearchStrategy \| None` | `None` | Custom retrieval scoring |
| `**kwargs` | | | Reserved for future use |

**Returns:** `Soul`

```python
soul = await Soul.birth("Kavi", archetype="wise companion", values=["curiosity", "honesty"])
```

#### `Soul.awaken()`

```python
@classmethod
async def awaken(
    cls,
    source: str | Path | bytes,
    engine: CognitiveEngine | None = None,
    search_strategy: SearchStrategy | None = None,
    password: str | None = None,
) -> Soul
```

Load an existing soul from disk or bytes. Supports `.soul` (zip archive), `.json`, `.yaml`/`.yml`, and `.md` (SOUL.md format). Sets lifecycle to `ACTIVE` on load.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | `str \| Path \| bytes` | required | File path or raw `.soul` bytes |
| `engine` | `CognitiveEngine \| None` | `None` | LLM backend |
| `search_strategy` | `SearchStrategy \| None` | `None` | Custom retrieval scoring |

**Returns:** `Soul`

**Raises:** `ValueError` if the file extension is unrecognized. `SoulEncryptedError` if encrypted but no password given. `SoulDecryptionError` if wrong password.

```python
soul = await Soul.awaken("./kavi.soul")
soul = await Soul.awaken(Path("config.yaml"), engine=my_engine)
```

#### `Soul.from_markdown()`

```python
@classmethod
async def from_markdown(cls, content: str) -> Soul
```

Parse a SOUL.md-formatted string into a Soul. Does not accept an engine or search strategy -- use the constructor after parsing if you need those.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | required | Raw SOUL.md text |

**Returns:** `Soul`

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `did` | `str` | Decentralized identifier (DID). Unique, generated at birth. |
| `name` | `str` | Display name. |
| `born` | `datetime` | Birth timestamp. |
| `archetype` | `str` | Character archetype description. |
| `dna` | `DNA` | Full personality blueprint (personality, communication, biorhythms). |
| `state` | `SoulState` | Current emotional and energy state. |
| `lifecycle` | `LifecycleState` | Current lifecycle phase (`BORN`, `ACTIVE`, `DORMANT`, `RETIRED`). |
| `identity` | `Identity` | Full identity object including DID, name, values, origin story. |
| `self_model` | `SelfModelManager` | Klein's self-concept manager. Tracks self-images and relationship notes. |
| `general_events` | `list[GeneralEvent]` | Conway hierarchy general events accumulated from experience. |
| `pending_mutations` | `list[Mutation]` | Unapproved evolution proposals. |
| `evolution_history` | `list[Mutation]` | All resolved mutations (approved and rejected). |

### Memory Operations

#### `soul.remember()`

```python
async def remember(
    self,
    content: str,
    *,
    type: MemoryType = MemoryType.SEMANTIC,
    importance: int = 5,
    emotion: str | None = None,
    entities: list[str] | None = None,
) -> str
```

Store a new memory. Returns the generated memory ID.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | required | The memory content |
| `type` | `MemoryType` | `SEMANTIC` | Memory tier |
| `importance` | `int` | `5` | 1-10 scale |
| `emotion` | `str \| None` | `None` | Emotional tag |
| `entities` | `list[str] \| None` | `None` | Referenced entities |
| `domain` | `str` | `"default"` | Sub-namespace inside the layer (#41), e.g. `"finance"` or `"legal"` |
| `user_id` | `str \| None` | `None` | Multi-user attribution (#46) |

**Returns:** `str` -- memory ID

```python
mid = await soul.remember("User prefers dark mode", importance=7)

# Domain-scoped memory (#41)
mid = await soul.remember(
    "Q3 revenue up 12 percent", domain="finance", importance=8
)
```

#### `soul.recall()`

```python
async def recall(
    self,
    query: str,
    *,
    limit: int = 10,
    types: list[MemoryType] | None = None,
    min_importance: int = 0,
    user_id: str | None = None,
    layer: str | None = None,
    domain: str | None = None,
) -> list[MemoryEntry]
```

Search memories ranked by ACT-R activation (recency, frequency, relevance). Relevance scoring uses the configured `SearchStrategy`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Natural language search query |
| `limit` | `int` | `10` | Max results |
| `types` | `list[MemoryType] \| None` | `None` | Filter by memory type(s). `None` = all types. |
| `min_importance` | `int` | `0` | Minimum importance threshold |
| `user_id` | `str \| None` | `None` | Multi-user filter (#46). When set, results restrict to memories whose `user_id` matches OR is `None` (legacy/orphan entries are visible to every user). When unset, returns all memories regardless of attribution. |
| `layer` | `str \| None` | `None` | Restrict recall to one layer (#41). Accepts built-in names (`"episodic"`, `"semantic"`, `"procedural"`, `"social"`) or any custom layer name. |
| `domain` | `str \| None` | `None` | Restrict recall to one domain sub-namespace (#41), e.g. `"finance"`. |

**Returns:** `list[MemoryEntry]`

```python
# Legacy (single-user) recall
memories = await soul.recall("dark mode preference", limit=5)

# Multi-user soul: scope to alice
alice_memories = await soul.recall("preferences", user_id="alice", limit=5)

# Domain-scoped recall (#41)
finance_only = await soul.recall("revenue", domain="finance")
all_semantic = await soul.recall("python", layer="semantic")
combo = await soul.recall("revenue", layer="semantic", domain="finance")
```

#### `soul.observe()`

```python
async def observe(
    self,
    interaction: Interaction,
    *,
    user_id: str | None = None,
    domain: str = "default",
) -> None
```

The primary learning hook. Call after every user-agent exchange. Runs the full psychology pipeline:

1. Detect sentiment (somatic marker)
2. Compute significance (LIDA gate)
3. If significant: store episodic memory with somatic marker
4. Extract semantic facts
5. Extract entities
6. Update self-model (Klein)
7. Update knowledge graph
8. Drain energy/social_battery
9. Check evolution triggers

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `interaction` | `Interaction` | required | The user-agent exchange |
| `user_id` | `str \| None` | `None` | Multi-user attribution (#46). When set, every memory written during this call is stamped with the user_id, and the per-user bond is strengthened instead of the default bond. When unset, behaviour is unchanged: orphan entries with `user_id=None`. |
| `domain` | `str` | `"default"` | Domain stamp for memories written by this call (#41). Pass e.g. `"finance"` to scope all derived memories to that domain. |

```python
# Legacy (single-user) observe
await soul.observe(Interaction(user_input="Hi!", agent_output="Hello there!"))

# Multi-user soul: attribute to alice
await soul.observe(
    Interaction(user_input="My favorite color is blue", agent_output="Got it!"),
    user_id="alice",
)

# Domain-scoped observe (#41)
await soul.observe(
    Interaction(user_input="Q3 revenue up 12 percent", agent_output="Noted."),
    domain="finance",
)
```

#### `soul._memory.layer(name)` — LayerView accessor (#41)

```python
view = soul._memory.layer("social")
sid = await view.store(MemoryEntry(
    type=MemoryType.SEMANTIC,
    content="Alice prefers async messages",
    importance=7,
))
results = await view.query("alice", domain="finance")
recent = view.entries(domain="legal")
n = view.count()
```

`MemoryManager.layer(name)` returns a `LayerView` with a uniform API (`store`, `query`, `get`, `delete`, `entries`, `count`) that works for built-in layers (`episodic`, `semantic`, `procedural`, `social`) and any user-defined layer name. Custom layers are created lazily on first `store()`.

#### `DomainIsolationMiddleware` (#41)

```python
from soul_protocol.runtime.middleware import DomainIsolationMiddleware

finance_only = DomainIsolationMiddleware(
    soul, allowed_domains=["finance", "default"]
)
await finance_only.remember("New OPEX line", importance=7)  # stamped "finance"
results = await finance_only.recall("revenue", limit=5)
await finance_only.remember("NDA fact", domain="legal")  # raises DomainAccessError
```

Wraps a `Soul` and enforces a domain allow-list. Reads silently filter to the allowed list. Writes to a disallowed domain raise `DomainAccessError`. When no domain is given on `remember`/`observe`, the middleware defaults to `allowed_domains[0]`.

#### `soul.bond_for()`

```python
def bond_for(self, user_id: str) -> Bond
```

Return the per-user `Bond` for a given `user_id` (multi-user souls, #46). Lazily creates the bond on first access (strength=50, count=0). Bonds survive export/awaken. Use this to inspect or mutate a single user's relationship without touching the default bond.

```python
alice_bond = soul.bond_for("alice")
alice_bond.strengthen(2.0)  # only alice's bond moves

# bond.strengthen() also accepts a user_id keyword for routing
soul.bond.strengthen(2.0, user_id="alice")  # same as above
soul.bond.strengthen(2.0)  # default bond (legacy)
```

`soul.bonded_users` returns the list of `user_id`s with their own per-user bonds (excludes the default bond's `bonded_to`).

#### `soul.forget()`

```python
async def forget(self, query: str) -> dict
```

Bulk-delete memories matching `query` across episodic, semantic, and procedural tiers. Records a deletion audit entry. Token-overlap match.

**Returns:** dict with keys:

| Key | Type | Description |
|-----|------|-------------|
| `episodic` | `list[str]` | IDs of deleted episodic memories. |
| `semantic` | `list[str]` | IDs of deleted semantic facts. |
| `procedural` | `list[str]` | IDs of deleted procedural memories. |
| `total` | `int` | Total deleted across tiers. |

#### `soul.forget_entity()`

```python
async def forget_entity(self, entity: str) -> dict
```

Bulk-delete by entity. Removes the entity from the knowledge graph and any memories mentioning it. Returns the same dict shape as `forget()` plus `edges_removed: int`.

#### `soul.forget_before()`

```python
async def forget_before(self, timestamp: datetime) -> dict
```

Bulk-delete memories created before `timestamp`. Returns the same dict shape as `forget()`.

#### `soul.forget_by_id()`

```python
async def forget_by_id(self, memory_id: str) -> bool
```

Legacy single-id deletion. Returns `True` on hit. Kept for backward compatibility — for an audited single-id deletion that returns the full result dict (used by `soul forget --id`), prefer `forget_one()`.

#### `soul.forget_one()`

```python
async def forget_one(self, memory_id: str) -> dict
```

Audited single-id deletion. Records a deletion audit entry when the entry exists. Returns:

| Key | Type | Description |
|-----|------|-------------|
| `episodic` / `semantic` / `procedural` | `list[str]` | The deleted ID (length 0 or 1) by tier. |
| `total` | `int` | 0 if not found, 1 if deleted. |
| `found` | `bool` | Whether `memory_id` resolved. |
| `tier` | `str \| None` | Tier the entry lived in, or `None`. |

#### `soul.supersede()`

```python
async def supersede(
    self,
    old_id: str,
    new_content: str,
    *,
    reason: str | None = None,
    importance: int = 5,
    memory_type: MemoryType | None = None,
    emotion: str | None = None,
    entities: list[str] | None = None,
) -> dict
```

Mark `old_id` as superseded by a newly-written memory. The old entry is preserved with `superseded_by = new_id`; search filters out superseded entries by default, so recall surfaces the new one. `memory_type` defaults to the old entry's tier. Records a supersede audit entry.

**Returns:** dict with `found` / `old_id` / `new_id` / `tier` / `reason`. If `old_id` does not resolve, `found` is False and no new memory is written.

```python
result = await soul.supersede(
    old_fact_id,
    "User now prefers light mode",
    reason="changed during onboarding redesign",
    importance=7,
)
print(result["new_id"])
```

#### `soul.deletion_audit`

```python
@property
def deletion_audit(self) -> list[dict]
```

Read-only copy of the deletion audit trail. Each entry: `deleted_at` (ISO timestamp), `count`, `reason`, `tiers` (per-tier breakdown). The audit does not contain deleted content (GDPR).

#### `soul.supersede_audit`

```python
@property
def supersede_audit(self) -> list[dict]
```

Read-only copy of the user-driven supersede audit trail. Each entry: `superseded_at` (ISO timestamp), `old_id`, `new_id`, `tier`, `reason`. Internal supersession (dream-cycle dedup, contradiction resolution during `learn`) does not append here — only explicit `supersede()` calls.

#### `soul.get_core_memory()`

```python
def get_core_memory(self) -> CoreMemory
```

Return the always-loaded core memory (persona + human profile). Not async.

**Returns:** `CoreMemory`

#### `soul.edit_core_memory()`

```python
async def edit_core_memory(self, *, persona: str | None = None, human: str | None = None) -> None
```

Append to core memory fields. Pass only the fields you want to update.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `persona` | `str \| None` | `None` | Text to append to persona block |
| `human` | `str \| None` | `None` | Text to append to human profile block |

#### `soul.reflect()`

```python
async def reflect(self, *, apply: bool = True) -> ReflectionResult | None
```

Trigger a reflection pass. The soul reviews recent interactions, consolidates memories, and updates self-understanding. Call periodically (every 10-20 interactions or at session end).

Requires a `CognitiveEngine` (LLM). Returns `None` in heuristic-only mode.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `apply` | `bool` | `True` | Auto-consolidate results into memory. Summaries become semantic memories, themes create GeneralEvents, self-insight updates the self-model. |

**Returns:** `ReflectionResult | None`

```python
result = await soul.reflect()
if result:
    print(result.themes)
```

#### `soul.dream()`

```python
async def dream(
    self,
    *,
    since: datetime | None = None,
    archive: bool = True,
    detect_patterns: bool = True,
    consolidate_graph: bool = True,
    synthesize: bool = True,
) -> DreamReport
```

Run an offline dream cycle — batch consolidation of accumulated memories. Dreaming is the offline counterpart to `observe()` (online). While `observe()` processes interactions one-at-a-time, `dream()` reviews accumulated episodes in batch to detect patterns, consolidate memory tiers, and synthesize cross-tier insights. No LLM required.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `since` | `datetime \| None` | `None` | Only review episodes after this time. None = review all. |
| `archive` | `bool` | `True` | Whether to archive old episodic memories. |
| `detect_patterns` | `bool` | `True` | Whether to detect topic clusters and recurring procedures. |
| `consolidate_graph` | `bool` | `True` | Whether to merge/prune knowledge graph. |
| `synthesize` | `bool` | `True` | Whether to create procedural memories and evolution insights. |

**Returns:** `DreamReport` with `topic_clusters`, `detected_procedures`, `behavioral_trends`, `graph_consolidation`, `evolution_insights`, and consolidation stats.

```python
report = await soul.dream()
print(report.summary())  # Human-readable summary
print(f"Found {len(report.topic_clusters)} topic clusters")
print(f"Created {report.procedures_created} procedures")
```

### State

#### `soul.feel()`

```python
def feel(self, **kwargs) -> None
```

Update the soul's emotional state. Not async.

For `energy` and `social_battery`, values are **deltas** (added to current value, clamped 0-100). `mood` and `last_interaction` are set directly. `focus` accepts a level (`"low"`, `"medium"`, `"high"`, `"max"`) which sets `focus_override` and locks focus to that value, or `"auto"` / `None` to clear the lock and re-enable density-driven focus.

```python
soul.feel(energy=-10, mood=Mood.TIRED)
soul.feel(social_battery=15, focus="high")  # locked
soul.feel(focus="auto")                     # density-driven again
```

#### `soul.recompute_focus()`

```python
def recompute_focus(self, now: datetime | None = None) -> str
```

Recompute density-driven focus at the given time and return the resulting level. Call before reading `soul.state.focus` if you need a value that reflects current interaction density rather than the last interaction tick. No-op when `focus_override` is set or `Biorhythms.focus_window_seconds` is 0.

#### `soul.to_system_prompt()`

```python
def to_system_prompt(self) -> str
```

Generate a complete LLM system prompt from DNA, core memory, state, and self-model insights. Not async.

**Returns:** `str`

### Evolution

#### `soul.propose_evolution()`

```python
async def propose_evolution(self, trait: str, new_value: str, reason: str) -> Mutation
```

Propose a trait mutation. The `trait` is a dot-separated path into DNA (e.g., `"communication.warmth"`).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `trait` | `str` | required | Dot-separated trait path |
| `new_value` | `str` | required | Proposed new value (as string) |
| `reason` | `str` | required | Human-readable justification |

**Returns:** `Mutation`

**Raises:** `ValueError` if evolution is disabled or the trait is immutable.

In **supervised** mode, the mutation is created as pending. In **autonomous** mode, it is auto-approved.

```python
m = await soul.propose_evolution("communication.warmth", "high", "User responds well to warmth")
```

#### `soul.approve_evolution()`

```python
async def approve_evolution(self, mutation_id: str) -> bool
```

Approve a pending mutation and apply it to DNA.

**Returns:** `True` if the mutation was found and approved, `False` otherwise.

#### `soul.reject_evolution()`

```python
async def reject_evolution(self, mutation_id: str) -> bool
```

Reject a pending mutation.

**Returns:** `True` if the mutation was found and rejected, `False` otherwise.

### Persistence

#### `soul.save()`

```python
async def save(self, path: str | Path | None = None) -> None
```

Save the soul to file storage (config + full memory data). If `path` is omitted, uses the internal storage backend.

#### `soul.export()`

```python
async def export(self, path: str | Path) -> None
```

Export the soul as a portable `.soul` zip archive with full memory data.

```python
await soul.export("./kavi.soul")
```

#### `soul.retire()`

```python
async def retire(self, *, farewell: bool = False, preserve_memories: bool = True) -> None
```

Graceful retirement. Saves to disk (if `preserve_memories` is True), sets lifecycle to `RETIRED`, clears memory, and resets state.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `farewell` | `bool` | `False` | Reserved for farewell rituals |
| `preserve_memories` | `bool` | `True` | Save to disk before clearing |

### Serialization

#### `soul.serialize()`

```python
def serialize(self) -> SoulConfig
```

Serialize the soul's current state to a `SoulConfig` for storage or export. Not async.

**Returns:** `SoulConfig`

---

## Types

All types are Pydantic `BaseModel` subclasses unless noted as enums. Import from `soul_protocol`.

### Identity

```python
class Identity(BaseModel)
```

A soul's unique identity with cryptographic DID.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `did` | `str` | `""` | Decentralized identifier |
| `name` | `str` | required | Display name |
| `archetype` | `str` | `""` | Character archetype |
| `born` | `datetime` | `datetime.now()` | Birth timestamp |
| `bonded_to` | `str \| None` | `None` | Entity this soul is bonded to |
| `origin_story` | `str` | `""` | Persona / origin text |
| `prime_directive` | `str` | `""` | Top-level directive |
| `core_values` | `list[str]` | `[]` | Values for significance scoring |

### DNA / Personality

#### `Personality`

```python
class Personality(BaseModel)
```

Big Five OCEAN model. Each trait is a float from 0.0 to 1.0.

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `openness` | `float` | `0.5` | `ge=0.0, le=1.0` |
| `conscientiousness` | `float` | `0.5` | `ge=0.0, le=1.0` |
| `extraversion` | `float` | `0.5` | `ge=0.0, le=1.0` |
| `agreeableness` | `float` | `0.5` | `ge=0.0, le=1.0` |
| `neuroticism` | `float` | `0.5` | `ge=0.0, le=1.0` |

#### `CommunicationStyle`

```python
class CommunicationStyle(BaseModel)
```

How the soul communicates.

| Field | Type | Default |
|-------|------|---------|
| `warmth` | `str` | `"moderate"` |
| `verbosity` | `str` | `"moderate"` |
| `humor_style` | `str` | `"none"` |
| `emoji_usage` | `str` | `"none"` |

#### `Biorhythms`

```python
class Biorhythms(BaseModel)
```

Simulated vitality and energy patterns.

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `chronotype` | `str` | `"neutral"` | |
| `social_battery` | `float` | `100.0` | `ge=0.0, le=100.0` |
| `energy_regen_rate` | `float` | `5.0` | |
| `focus_window_seconds` | `float` | `3600.0` | `ge=0.0` (set to 0 to disable density-driven focus) |
| `focus_high_threshold` | `int` | `3` | `ge=1` (interactions in window at or above which focus rises to `high`) |
| `focus_max_threshold` | `int` | `10` | `ge=1` (interactions in window at or above which focus rises to `max`) |
| `trust_chain_max_entries` | `int` | `0` | `ge=0` (cap for touch-time chain pruning; 0 = unbounded; positive = compress old history into a `chain.pruned` marker once the cap is reached). See [docs/trust-chain.md](trust-chain.md#chain-pruning). |

#### `DNA`

```python
class DNA(BaseModel)
```

The soul's complete personality blueprint.

| Field | Type | Default |
|-------|------|---------|
| `personality` | `Personality` | `Personality()` |
| `communication` | `CommunicationStyle` | `CommunicationStyle()` |
| `biorhythms` | `Biorhythms` | `Biorhythms()` |

### Psychology

#### `SomaticMarker`

```python
class SomaticMarker(BaseModel)
```

Emotional context tagged onto a memory (Damasio's Somatic Marker Hypothesis). Emotions guide recall and decision-making.

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `valence` | `float` | `0.0` | `ge=-1.0, le=1.0` (negative to positive) |
| `arousal` | `float` | `0.0` | `ge=0.0, le=1.0` (calm to intense) |
| `label` | `str` | `"neutral"` | e.g. `"joy"`, `"frustration"`, `"curiosity"` |

#### `SignificanceScore`

```python
class SignificanceScore(BaseModel)
```

Significance gate for episodic storage (LIDA architecture). Only experiences passing the threshold become episodic memories.

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `novelty` | `float` | `0.0` | `ge=0.0, le=1.0` |
| `emotional_intensity` | `float` | `0.0` | `ge=0.0, le=1.0` |
| `goal_relevance` | `float` | `0.0` | `ge=0.0, le=1.0` |

#### `GeneralEvent`

```python
class GeneralEvent(BaseModel)
```

Conway's Self-Memory System hierarchical autobiography grouping. Episodes cluster into general events (themes).

| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | `""` |
| `theme` | `str` | `""` |
| `episode_ids` | `list[str]` | `[]` |
| `started_at` | `datetime` | `datetime.now()` |
| `last_updated` | `datetime` | `datetime.now()` |

#### `SelfImage`

```python
class SelfImage(BaseModel)
```

A facet of the soul's self-concept (Klein's self-model). Built from accumulated experience.

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `domain` | `str` | `""` | e.g. `"technical_helper"`, `"creative_writer"` |
| `confidence` | `float` | `0.1` | `ge=0.0, le=1.0` |
| `evidence_count` | `int` | `0` | Interactions supporting this self-image |

### Memory

#### `MemoryEntry`

```python
class MemoryEntry(BaseModel)
```

A single memory with metadata, emotional context, and psychology-informed fields.

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `id` | `str` | `""` | | Auto-generated |
| `type` | `MemoryType` | required | | Memory tier |
| `content` | `str` | required | | The memory text |
| `importance` | `int` | `5` | `ge=1, le=10` | Importance score |
| `emotion` | `str \| None` | `None` | | Emotional tag |
| `confidence` | `float` | `1.0` | `ge=0.0, le=1.0` | Fact confidence |
| `entities` | `list[str]` | `[]` | | Referenced entities |
| `created_at` | `datetime` | `datetime.now()` | | Creation time |
| `last_accessed` | `datetime \| None` | `None` | | Last recall time |
| `access_count` | `int` | `0` | | Total recall count |
| `somatic` | `SomaticMarker \| None` | `None` | | Emotional context (v0.2.0) |
| `access_timestamps` | `list[datetime]` | `[]` | | Full access history for ACT-R decay |
| `significance` | `float` | `0.0` | | LIDA significance score |
| `general_event_id` | `str \| None` | `None` | | Conway hierarchy link |
| `superseded_by` | `str \| None` | `None` | | ID of newer conflicting fact (v0.2.2) |
| `user_id` | `str \| None` | `None` | | Multi-user attribution (#46) |
| `layer` | `str` | `""` | | Free-form layer namespace (#41). Empty string is coerced to `type.value`. |
| `domain` | `str` | `"default"` | | Sub-namespace inside the layer (#41), e.g. `"finance"` |

#### `CoreMemory`

```python
class CoreMemory(BaseModel)
```

Always-loaded memory: persona description and human profile.

| Field | Type | Default |
|-------|------|---------|
| `persona` | `str` | `""` |
| `human` | `str` | `""` |

#### `MemorySettings`

```python
class MemorySettings(BaseModel)
```

Configuration for the memory subsystem.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `episodic_max_entries` | `int` | `10000` | Max episodic memories |
| `semantic_max_facts` | `int` | `1000` | Max semantic facts |
| `importance_threshold` | `int` | `3` | Minimum importance to store |
| `confidence_threshold` | `float` | `0.7` | Minimum confidence to surface |
| `persona_tokens` | `int` | `500` | Max token budget for persona block |
| `human_tokens` | `int` | `500` | Max token budget for human block |

### State / Feelings

#### `SoulState`

```python
class SoulState(BaseModel)
```

The soul's current emotional and energy state.

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `mood` | `Mood` | `Mood.NEUTRAL` | |
| `energy` | `float` | `100.0` | `ge=0.0, le=100.0` |
| `focus` | `str` | `"medium"` | Effective level (one of `low`, `medium`, `high`, `max`). Computed from interaction density unless `focus_override` is set. |
| `focus_override` | `str \| None` | `None` | When set, freezes `focus` to that level. Cleared via `feel(focus="auto")`. |
| `social_battery` | `float` | `100.0` | `ge=0.0, le=100.0` |
| `last_interaction` | `datetime \| None` | `None` | |
| `recent_interactions` | `list[datetime]` | `[]` | Sliding-window timestamps for density-driven focus calc. |

### Evolution Types

#### `Mutation`

```python
class Mutation(BaseModel)
```

A proposed or applied trait change.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | `""` | Auto-generated hex ID |
| `trait` | `str` | required | Dot-separated trait path |
| `old_value` | `str` | required | Previous value |
| `new_value` | `str` | required | Proposed value |
| `reason` | `str` | required | Justification |
| `proposed_at` | `datetime` | `datetime.now()` | When proposed |
| `approved` | `bool \| None` | `None` | `None` = pending, `True` = approved, `False` = rejected |
| `approved_at` | `datetime \| None` | `None` | When resolved |

#### `EvolutionConfig`

```python
class EvolutionConfig(BaseModel)
```

Evolution system configuration.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `EvolutionMode` | `EvolutionMode.SUPERVISED` | Evolution mode |
| `mutation_rate` | `float` | `0.01` | Base mutation probability |
| `require_approval` | `bool` | `True` | Require human approval |
| `mutable_traits` | `list[str]` | `["communication", "biorhythms"]` | Traits that can evolve |
| `immutable_traits` | `list[str]` | `["personality", "core_values"]` | Traits that cannot evolve |
| `history` | `list[Mutation]` | `[]` | All resolved mutations |

### Lifecycle Types

See [LifecycleState enum](#lifecyclestate).

### Interaction

```python
class Interaction(BaseModel)
```

A single user-agent interaction. This is the input to `soul.observe()`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `user_input` | `str` | required | What the user said |
| `agent_output` | `str` | required | What the agent replied |
| `channel` | `str` | `"unknown"` | Source channel identifier |
| `timestamp` | `datetime` | `datetime.now()` | When the exchange occurred |
| `metadata` | `dict` | `{}` | Arbitrary metadata |

### Reflection

#### `ReflectionResult`

```python
class ReflectionResult(BaseModel)
```

Output of a soul's reflection pass. Only produced when a `CognitiveEngine` (LLM) is available.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `themes` | `list[str]` | `[]` | Recurring themes across episodes |
| `summaries` | `list[dict]` | `[]` | Consolidated episode summaries |
| `emotional_patterns` | `str` | `""` | Observed emotional patterns |
| `self_insight` | `str` | `""` | Updated self-understanding |

### Configuration

#### `SoulConfig`

```python
class SoulConfig(BaseModel)
```

Complete serializable soul configuration. This is what gets saved to disk.

| Field | Type | Default |
|-------|------|---------|
| `version` | `str` | `"1.0.0"` |
| `identity` | `Identity` | required |
| `dna` | `DNA` | `DNA()` |
| `memory` | `MemorySettings` | `MemorySettings()` |
| `core_memory` | `CoreMemory` | `CoreMemory()` |
| `state` | `SoulState` | `SoulState()` |
| `evolution` | `EvolutionConfig` | `EvolutionConfig()` |
| `lifecycle` | `LifecycleState` | `LifecycleState.BORN` |

### Manifest

#### `SoulManifest`

```python
class SoulManifest(BaseModel)
```

Metadata for a `.soul` archive file.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format_version` | `str` | `"1.0.0"` | Archive format version |
| `created` | `datetime` | `datetime.now()` | When the soul was first created |
| `exported` | `datetime` | `datetime.now()` | When this archive was exported |
| `soul_id` | `str` | `""` | Soul's DID |
| `soul_name` | `str` | `""` | Soul's display name |
| `checksum` | `str` | `""` | Integrity checksum |
| `stats` | `dict` | `{}` | Archive statistics |

---

## Protocols

Both protocols are `@runtime_checkable`, so you can use `isinstance()` checks.

### CognitiveEngine

```python
from soul_protocol import CognitiveEngine

class CognitiveEngine(Protocol):
    async def think(self, prompt: str) -> str: ...
```

The interface for LLM-powered cognition. Implement this to connect any LLM to a soul.

**Method: `think(prompt: str) -> str`**

Receives a structured prompt with `[TASK:xxx]` markers and returns a response (typically JSON). The soul uses this for sentiment analysis, significance assessment, fact extraction, entity extraction, self-reflection, and memory consolidation.

**Minimal implementation:**

```python
class MyCognitive:
    async def think(self, prompt: str) -> str:
        return await my_llm_client.complete(prompt)
```

### SearchStrategy

```python
from soul_protocol import SearchStrategy

class SearchStrategy(Protocol):
    def score(self, query: str, content: str) -> float: ...
```

The interface for memory retrieval scoring. Replace the default token-overlap strategy with embeddings, vector search, or any custom approach.

**Method: `score(query: str, content: str) -> float`**

Returns a relevance score from 0.0 (no match) to 1.0 (perfect match).

**Minimal implementation:**

```python
class EmbeddingSearch:
    def score(self, query: str, content: str) -> float:
        return cosine_similarity(embed(query), embed(content))
```

---

## Implementations

### HeuristicEngine

```python
from soul_protocol import HeuristicEngine
```

Zero-dependency fallback implementing `CognitiveEngine`. Used when no LLM is available (offline, testing, cost-constrained).

Routes prompts to the appropriate heuristic function based on `[TASK:xxx]` markers in the prompt:

| Task Marker | Behavior |
|-------------|----------|
| `[TASK:sentiment]` | Keyword-based sentiment detection |
| `[TASK:significance]` | Heuristic significance scoring |
| `[TASK:extract_facts]` | Regex-based fact extraction (e.g., "my name is X") |
| `[TASK:extract_entities]` | Returns empty list (minimal heuristic) |
| `[TASK:self_reflection]` | Returns minimal self-reflection |
| `[TASK:reflect]` | Returns empty reflection result |

All responses are JSON strings matching the expected LLM output format.

```python
soul = await Soul.birth("Kavi", engine=HeuristicEngine())
```

### TokenOverlapStrategy

```python
from soul_protocol import TokenOverlapStrategy
```

Zero-dependency default implementing `SearchStrategy`. Uses Jaccard token overlap: the fraction of query tokens found in the content. Identical behavior to pre-v0.2.2 built-in scoring.

```python
strategy = TokenOverlapStrategy()
score = strategy.score("dark mode", "User prefers dark mode for coding")
# Returns float between 0.0 and 1.0
```

---

## Enums

All enums inherit from both `str` and `Enum`, so they serialize cleanly to JSON.

### MemoryType

```python
from soul_protocol import MemoryType
```

| Value | String | Description |
|-------|--------|-------------|
| `MemoryType.CORE` | `"core"` | Always-loaded persona and human profile |
| `MemoryType.EPISODIC` | `"episodic"` | Autobiographical events with emotional context |
| `MemoryType.SEMANTIC` | `"semantic"` | Extracted facts and knowledge |
| `MemoryType.PROCEDURAL` | `"procedural"` | Learned skills and procedures |

### Mood

```python
from soul_protocol import Mood
```

| Value | String |
|-------|--------|
| `Mood.NEUTRAL` | `"neutral"` |
| `Mood.CURIOUS` | `"curious"` |
| `Mood.FOCUSED` | `"focused"` |
| `Mood.TIRED` | `"tired"` |
| `Mood.EXCITED` | `"excited"` |
| `Mood.CONTEMPLATIVE` | `"contemplative"` |
| `Mood.SATISFIED` | `"satisfied"` |
| `Mood.CONCERNED` | `"concerned"` |

### LifecycleState

```python
from soul_protocol import LifecycleState
```

| Value | String | Description |
|-------|--------|-------------|
| `LifecycleState.BORN` | `"born"` | Initial state at creation |
| `LifecycleState.ACTIVE` | `"active"` | Running and interacting |
| `LifecycleState.DORMANT` | `"dormant"` | Suspended, not interacting |
| `LifecycleState.RETIRED` | `"retired"` | Gracefully shut down |

### EvolutionMode

```python
from soul_protocol import EvolutionMode
```

| Value | String | Description |
|-------|--------|-------------|
| `EvolutionMode.DISABLED` | `"disabled"` | No mutations allowed |
| `EvolutionMode.SUPERVISED` | `"supervised"` | Mutations require explicit approval |
| `EvolutionMode.AUTONOMOUS` | `"autonomous"` | Mutations auto-approved on proposal |

---

## Trust Chain (#42)

Verifiable signed history of every audit-worthy soul action. See [trust-chain.md](trust-chain.md) for the threat model and detailed treatment.

### `soul.trust_chain`

```python
@property
def trust_chain(self) -> TrustChain
```

Read-only `TrustChain` view. The chain is mutated by Soul's lifecycle hooks; for direct mutation use `soul.trust_chain_manager`.

### `soul.trust_chain_manager`

<a id="trustchainmanager-summary"></a>

```python
@property
def trust_chain_manager(self) -> TrustChainManager
```

The `TrustChainManager` instance. Public methods of interest:

```python
def append(
    self,
    action: str,
    payload: dict,
    actor_did: str | None = None,
    timestamp: datetime | None = None,
    summary: str | None = None,        # #201 — non-cryptographic per-action description
) -> TrustEntry
```

Use `manager.append(action, payload)` to record a custom action that the built-in hooks don't cover. Pass `summary=` to attach a human-readable description; when omitted, an action-keyed default formatter from `_SUMMARY_FORMATTERS` runs against the payload. The summary is stored on the resulting `TrustEntry.summary` field and surfaces in `audit_log()` rows. It is excluded from the canonical bytes used for hashing and signing — chain integrity does not depend on it.

Default formatters ship for the actions Soul emits (`memory.write`, `memory.forget`, `memory.supersede`, `bond.strengthen`, `bond.weaken`, `evolution.proposed`, `evolution.applied`, `learning.event`); custom actions without a registered formatter get `summary=""` unless one is passed explicitly.

The manager also exposes `prune(keep)` and `dry_run_prune(keep)` for touch-time chain pruning (#203) — see [trust-chain.md](trust-chain.md#chain-pruning).

`TrustChainManager.prune(keep=None, *, reason="touch-time") -> dict` compresses every non-genesis entry into a single signed `chain.pruned` marker when the chain has more than `keep` entries. `keep=None` falls back to the manager's `max_entries` (mirrored from `Biorhythms.trust_chain_max_entries`). Returns `{count, low_seq, high_seq, reason, marker_seq}` describing the prune; `count == 0` indicates a no-op.

`TrustChainManager.dry_run_prune(keep=None) -> dict` returns the same shape without mutating the chain — used by the CLI and MCP preview paths.

The cap is enforced automatically at `append()` time: when `max_entries > 0` and the chain has reached the cap, `append()` runs `prune(keep=1)` before adding the new entry, so the chain is bounded as a hard ceiling.

### `soul.verify_chain()`

```python
def verify_chain(self) -> tuple[bool, str | None]
```

Returns `(True, None)` on a fully valid chain, or `(False, "reason at seq N")` on the first failure.

### `soul.audit_log()`

```python
def audit_log(
    self,
    *,
    action_prefix: str | None = None,
    limit: int | None = None,
) -> list[dict]
```

Returns a list of `{seq, timestamp, action, actor_did, payload_hash, summary}` dicts. Filter by dot-namespaced action prefix (e.g. `"memory."`) and/or take only the most recent N rows. The `summary` field (added in #201) is a short human-readable description set at append time — see [`TrustChainManager.append`](#trustchainmanager-summary). Pre-#201 entries return `summary=""`.

### `Soul.export(include_keys=...)`

```python
async def export(
    self,
    path: str | Path,
    *,
    password: str | None = None,
    archive: bool = False,
    archive_tiers: list[str] | None = None,
    include_keys: bool = False,
) -> None
```

When `include_keys=False` (default for `export`), the soul's private signing key is dropped from the archive. The recipient can verify the chain but cannot append. Set `include_keys=True` only when migrating to a trusted destination.

`Soul.save()` and `Soul.save_local()` default `include_keys=True` because they're meant for the owner's own machine.

### `TrustEntry`

```python
class TrustEntry(BaseModel):
    seq: int                                # 0-indexed monotonic
    timestamp: datetime                     # UTC, validator-normalized
    actor_did: str                          # signer DID
    action: str                             # dot-namespaced (memory.write, …)
    payload_hash: str                       # SHA-256 hex of canonical payload JSON
    prev_hash: str                          # hash of previous entry (or GENESIS_PREV_HASH)
    signature: str                          # base64 Ed25519 signature (excluded from canonical bytes)
    algorithm: str = "ed25519"
    public_key: str                         # base64 raw 32-byte public key
    summary: str = ""                       # non-cryptographic per-action prose (excluded from canonical bytes, #201)
```

`summary` is a short human-readable description set at append time. It is excluded from `compute_entry_hash` and `_signing_message` so callers can edit, localise, or rewrite the summary without breaking `verify_chain()`. Pre-#201 entries that have no `summary` field on disk load with the empty default.

### `TrustChain`

```python
class TrustChain(BaseModel):
    did: str
    entries: list[TrustEntry]

    @property
    def length(self) -> int
    def head(self) -> TrustEntry | None
    def genesis_entry(self) -> TrustEntry | None
```

### `SignatureProvider` Protocol

```python
@runtime_checkable
class SignatureProvider(Protocol):
    @property
    def algorithm(self) -> str: ...
    @property
    def public_key(self) -> str: ...
    def sign(self, message: bytes) -> str: ...
    def verify(self, message: bytes, signature: str, public_key: str) -> bool: ...
```

The default implementation is `Ed25519SignatureProvider` from `soul_protocol.runtime.crypto`.

### Verification functions

```python
from soul_protocol.spec.trust import (
    verify_entry,
    verify_chain,
    chain_integrity_check,
    compute_payload_hash,
    compute_entry_hash,
    GENESIS_PREV_HASH,
)
```

- `verify_entry(entry, prev_entry, provider=None) -> bool` — single-entry verification (signature + chain link)
- `verify_chain(chain) -> tuple[bool, str | None]` — full chain, returns first failure reason
- `chain_integrity_check(chain) -> dict` — `{valid, length, first_failure, signers}` summary
- `compute_payload_hash(payload) -> str` — canonical-JSON SHA-256 hex of an arbitrary payload
- `compute_entry_hash(entry) -> str` — canonical-JSON SHA-256 hex of the entry minus its signature
- `GENESIS_PREV_HASH` — the constant `"0" * 64` used as the prev_hash of seq=0

---

## Soul Diff (#191)

Structured comparison between two souls. Lives in `soul_protocol.runtime.diff` with re-exports at the package level.

```python
from soul_protocol.runtime import Soul, SoulDiff, diff_souls, SchemaMismatchError

left = await Soul.awaken("aria.soul")
right = await Soul.awaken("aria-after-week.soul")
diff: SoulDiff = diff_souls(left, right, include_superseded=False)
```

### `diff_souls(left, right, *, include_superseded=False) -> SoulDiff`

Top-level entry point. Compares two `Soul` instances and returns a fully-populated `SoulDiff`. Sections are populated even when empty — consumers read `section.empty` to decide rendering.

Raises `SchemaMismatchError` when the two souls have different `_config.version` strings; run `soul migrate <path>` on the older soul first.

When `include_superseded=False` (default), memories whose `superseded_by` flipped between the two souls are filtered from the modified list; the supersession chain stays in the file but isn't surfaced. Pass `True` to populate `memory.superseded` and add the `superseded_by` field change explicitly.

### `SoulDiff`

Top-level Pydantic model. Fields:

| Field | Type | Description |
|-------|------|-------------|
| `left_name` / `right_name` | `str` | Soul names from each side. |
| `left_did` / `right_did` | `str` | DIDs from each side. |
| `identity` | `IdentityDiff` | Field changes (DID, name, archetype, born, bonded_to, role, core_values). |
| `ocean` | `OceanDiff` | OCEAN trait deltas + communication / biorhythm changes. |
| `state` | `StateDiff` | Mood, energy, social_battery, focus changes. |
| `core_memory` | `CoreMemoryDiff` | Persona / human content changes. |
| `memory` | `MemoryDiff` | Per-layer + per-domain counts; added / removed / modified entries. |
| `bond` | `BondDiff` | Default + per-user bond strength changes; added/removed users. |
| `skills` | `SkillDiff` | Skill registry — added / removed / level + XP changes. |
| `trust_chain` | `TrustChainDiff` | Length delta + new actions + new-entries sample. |
| `self_model` | `SelfModelDiff` | Domain confidence shifts. |
| `evolution` | `EvolutionDiff` | New mutations applied since the left's snapshot. |

Methods:

- `summary() -> dict[str, int]` — per-section change counts.
- `empty` (property) — `True` when no section detected any change.
- `model_dump(mode="json")` — full JSON-serializable dict (standard Pydantic).

### Section models

`IdentityDiff`, `StateDiff` carry `changes: list[FieldChange]`. Each `FieldChange` is `{field, before, after}`.

`OceanDiff` exposes `trait_deltas: dict[str, float]` (only non-zero deltas), plus `communication_changes` and `biorhythm_changes` lists of `FieldChange`.

`MemoryDiff` carries `layer_counts: list[LayerCounts]` (per-domain breakdown), plus `added`, `removed` (lists of `MemoryEntryAbstract` with truncated content), `modified` (list of `MemoryEntryChange` with content_before/content_after + field_changes), and `superseded` (only populated with `include_superseded=True`).

`BondDiff` carries `changes: list[BondChange]` (per-user strength + interaction count deltas), plus `added_users` / `removed_users` lists.

`SkillDiff` carries `added` / `removed` / `changed` lists of `SkillChange`.

`TrustChainDiff` carries `length_before` / `length_after`, `new_actions` (distinct action names past the left's head), and `new_entries_sample` (up to 5 newest entries as `{seq, timestamp, action, actor_did}`).

`SelfModelDiff` carries `added_domains` / `removed_domains` plus `changed: list[SelfModelChange]` with confidence + evidence deltas.

`EvolutionDiff` carries `new_mutations: list[dict]` with the right-side mutation history past the left's mutation ids.

### `SchemaMismatchError`

Subclass of `ValueError`. Raised by `diff_souls` when versions differ.

---

## Evaluation

The `soul_protocol.eval` module ships YAML-driven soul-aware evals (#160). Evals seed a soul with explicit state (memories, OCEAN, bonds, mood, energy) and then run cases against that state, so behaviour can be measured against a known starting point. See [eval-format.md](eval-format.md) for the full schema and [cli-reference.md](cli-reference.md#soul-eval) for the `soul eval` command.

```python
from soul_protocol.eval import (
    EvalSpec,
    EvalCase,
    EvalResult,
    CaseResult,
    Scoring,
    KeywordScoring,
    RegexScoring,
    SemanticScoring,
    JudgeScoring,
    StructuralScoring,
    SoulSeed,
    StateSeed,
    MemorySeed,
    BondSeed,
    SchemaValidationError,
    load_eval_spec,
    parse_eval_spec,
    run_eval,
    run_eval_file,
    run_eval_against_soul,
)
```

### Loading

- `load_eval_spec(path: str | Path) -> EvalSpec` — read and validate a YAML file. Raises `FileNotFoundError` or `SchemaValidationError`.
- `parse_eval_spec(data: dict, *, source: str | None = None) -> EvalSpec` — validate a parsed dict. Raises `SchemaValidationError`.

### Running

- `run_eval(spec, *, engine=None, case_filter=None) -> EvalResult` — births a soul from `spec.seed`, applies state / memories / bonds, runs cases. When `engine` is None, judge-scoring cases skip cleanly.
- `run_eval_file(path, *, engine=None, case_filter=None) -> EvalResult` — convenience wrapper that loads then runs.
- `run_eval_against_soul(spec, soul, *, engine=None, case_filter=None) -> EvalResult` — run cases against an existing `Soul` without re-birthing. Used by the `soul_eval` MCP tool. The `seed` block is ignored — the soul's live state is the seed.

### Result models

`EvalResult`:

| Property | Type | Description |
|----------|------|-------------|
| `spec_name` | `str` | Echo of `EvalSpec.name`. |
| `cases` | `list[CaseResult]` | One per case that ran. |
| `duration_ms` | `int` | Total time. |
| `error` | `str \| None` | Set when seed application failed. |
| `pass_count` | `int` | Cases that passed (excludes skips). |
| `fail_count` | `int` | Cases that failed (excludes skips and errors). |
| `skip_count` | `int` | Cases that were skipped (e.g. judge with no engine). |
| `error_count` | `int` | Cases that raised. |
| `total` | `int` | Length of `cases`. |
| `all_passed` | `bool` | True when no failures and no errors. Skips do not count as failures. |

`CaseResult`:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Echoes `EvalCase.name`. |
| `passed` | `bool` | Pass/fail per the scoring threshold. |
| `score` | `float` | Normalized `[0, 1]`. |
| `skipped` | `bool` | True for judge cases with no engine. |
| `duration_ms` | `int` | Case wall-clock. |
| `output` | `str` | First 1000 chars of soul output. |
| `details` | `dict` | Kind-specific diagnostic info. |
| `error` | `str \| None` | Set when the case raised. |

### Scoring kinds

`Scoring` is a discriminated union by `kind`:

- `KeywordScoring(kind="keyword", expected: list[str], mode: "all"|"any" = "all", threshold: float = 1.0)`
- `RegexScoring(kind="regex", pattern: str, threshold: float = 1.0)`
- `SemanticScoring(kind="semantic", expected: str, threshold: float = 0.5)`
- `JudgeScoring(kind="judge", criteria: str, threshold: float = 0.7)`
- `StructuralScoring(kind="structural", expected: dict, threshold: float = 1.0)`

For the structural keys (`output_contains_bonded_user`, `output_contains_user_id`, `mood_after`, `min_energy_after`, `max_energy_after`, `recall_min_results`, `recall_expected_substring`) see [eval-format.md](eval-format.md#structural).
