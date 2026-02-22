<!-- API Reference for soul-protocol v0.2.2. Covers: Soul class (lifecycle, properties,
     memory, state, evolution, persistence), all Pydantic types, protocols (CognitiveEngine,
     SearchStrategy), implementations (HeuristicEngine, TokenOverlapStrategy), and enums. -->

# API Reference

> soul-protocol v0.2.2

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
) -> Soul
```

Load an existing soul from disk or bytes. Supports `.soul` (zip archive), `.json`, `.yaml`/`.yml`, and `.md` (SOUL.md format). Sets lifecycle to `ACTIVE` on load.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | `str \| Path \| bytes` | required | File path or raw `.soul` bytes |
| `engine` | `CognitiveEngine \| None` | `None` | LLM backend |
| `search_strategy` | `SearchStrategy \| None` | `None` | Custom retrieval scoring |

**Returns:** `Soul`

**Raises:** `ValueError` if the file extension is unrecognized.

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

**Returns:** `str` -- memory ID

```python
mid = await soul.remember("User prefers dark mode", importance=7)
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
) -> list[MemoryEntry]
```

Search memories ranked by ACT-R activation (recency, frequency, relevance). Relevance scoring uses the configured `SearchStrategy`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Natural language search query |
| `limit` | `int` | `10` | Max results |
| `types` | `list[MemoryType] \| None` | `None` | Filter by memory type(s). `None` = all types. |
| `min_importance` | `int` | `0` | Minimum importance threshold |

**Returns:** `list[MemoryEntry]`

```python
memories = await soul.recall("dark mode preference", limit=5)
```

#### `soul.observe()`

```python
async def observe(self, interaction: Interaction) -> None
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

```python
await soul.observe(Interaction(user_input="Hi!", agent_output="Hello there!"))
```

#### `soul.forget()`

```python
async def forget(self, memory_id: str) -> bool
```

Remove a specific memory by ID.

**Returns:** `True` if the memory was found and removed, `False` otherwise.

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

### State

#### `soul.feel()`

```python
def feel(self, **kwargs) -> None
```

Update the soul's emotional state. Not async.

For `energy` and `social_battery`, values are **deltas** (added to current value, clamped 0-100). All other fields (`mood`, `focus`, `last_interaction`) are **set directly**.

```python
soul.feel(energy=-10, mood=Mood.TIRED)
soul.feel(social_battery=15, focus="high")
```

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
| `focus` | `str` | `"medium"` | |
| `social_battery` | `float` | `100.0` | `ge=0.0, le=100.0` |
| `last_interaction` | `datetime \| None` | `None` | |

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
