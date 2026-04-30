<!-- Covers: The 5-tier memory system, psychology-informed observe() pipeline,
     ACT-R activation scoring, cross-store recall, pluggable retrieval,
     reflection/consolidation, fact conflict resolution, memory settings,
     v2 features: MemoryCategory, salience, L0/L1 content layers,
     extraction taxonomy, dedup pipeline, abstract generation.
     v0.2.5 additions: memory visibility tiers (PUBLIC/BONDED/PRIVATE),
     contradiction pipeline with ContradictionDetector in observe(),
     Long Context Memory (LCM) with ContextStore and 3-level compaction,
     real embedding providers (SentenceTransformer, OpenAI, Ollama).
     v0.2.9 additions: archival memory wiring (auto-compress old episodics),
     auto-consolidation triggers, progressive recall (abstract overflow),
     skill progression with significance-weighted XP and daily decay.
     Updated: 2026-04-27 — Documented user-driven supersede primitive
       (Soul.supersede + soul supersede CLI) on top of the existing
       superseded_by infrastructure, plus the parallel supersede_audit
       trail. Internal supersession (dream-cycle dedup, contradiction
       detector) is unchanged.
     Updated: 2026-04-29 (#41) — Added "Memory Layers and Domains" section
       covering open-string layers, the new social layer, domain isolation,
       the LayerView accessor, DomainIsolationMiddleware, and the on-disk
       layout switch (flat legacy vs nested layered).
     Updated: 2026-03-29 — added v0.2.9 features. -->

# Memory Architecture

Soul Protocol implements a psychology-informed, 5-tier memory system inspired by human cognitive science. This document explains how memories are created, stored, scored, retrieved, and consolidated.

## Overview

```
Interaction
    |
    v
+--------------------------------------+
|         Psychology Pipeline           |
|                                       |
|  1. Sentiment   -> SomaticMarker      |
|  2. Significance -> LIDA Gate         |
|  3. Fact Extraction -> Semantic       |
|  4. Entity Extraction -> Graph        |
|  4d. Contradiction Scan -> Supersede  |
|  5. Self-Model Update -> Klein        |
+--------------------------------------+
    |
    v
+---------------+
|   5-Tier      |
|   Memory      |
|   Store       |
+---------------+
```

Every call to `soul.observe(interaction)` runs the full pipeline. Significant interactions become episodic memories. All interactions still produce semantic facts and entity updates, so no data is silently lost.


## The 5 Tiers

### Tier 1: Core Memory (always in context)

Core memory is the soul's permanent, always-loaded identity. It has two slots:

- **Persona**: Who the soul is. Injected into every system prompt so the soul never forgets itself.
- **Human**: What the soul knows about the human it serves. Also always in context.

Core memory is mutable via `edit_core_memory()`, which appends to existing content rather than replacing it. This is deliberate -- the soul accumulates understanding over time.

Token limits are enforced by `MemorySettings`: `persona_tokens=500`, `human_tokens=500`.

```python
await soul.edit_core_memory(
    human="Prakash prefers concise responses and dark mode."
)
```

### Tier 2: Episodic Memory

Episodic memory is the soul's autobiographical record. Each entry captures a specific interaction with timestamps, emotional markers, and significance scores.

Key properties:

- Max entries: **10,000** (configurable via `MemorySettings.episodic_max_entries`)
- Only stored if the significance gate passes (threshold: **0.3**)
- Each entry carries: content, somatic marker, significance score, access timestamps
- Eviction policy: least-significant entries removed first (scored by significance * 2.0 + importance * 0.1 + access_count * 0.5)
- Entries are sorted by `created_at` descending for recent-first access

### Tier 3: Semantic Memory

Semantic memory holds extracted facts about the user and world. These are declarative knowledge statements like "User prefers dark mode" or "User works at Acme Corp."

Key properties:

- Max facts: **1,000** (configurable via `MemorySettings.semantic_max_facts`)
- Eviction policy: least-important entries removed first
- Includes confidence scores (0.0-1.0) per fact
- Deduplication: token overlap > 0.7 with an existing fact causes the new fact to be skipped
- Superseded facts (v0.2.2): when a new fact contradicts an old one, the old fact gets marked with `superseded_by` and is excluded from search results

### Tier 4: Procedural Memory

Procedural memory stores learned patterns, preferences, and how-to knowledge. This tier is less heavily used in the current version (v0.2.x) and is planned for expansion. It follows the same `MemoryEntry` model and search interface as other stores.

### Tier 5: Knowledge Graph

The knowledge graph tracks typed entity relationships using directed edges.

Structure:

- Entities: dict mapping name to type plus an optional list of memory-id provenance
- Edges: list of `(source, target, relation)` tuples with optional `weight` and metadata
- No external dependencies — implemented with plain Python dicts
- Duplicate edges are silently ignored
- Entities are auto-created when a relationship references them

#### Typed entity ontology (v0.5.0, #190)

Eight built-in entity kinds plus open-string extension. Use `EntityType.PERSON`, `EntityType.TOOL`, etc. when the well-known kinds fit; pass any string when they don't:

| Built-in | Use for |
|----------|---------|
| `person` | Humans (Alice, the user) |
| `place` | Geographic or virtual locations |
| `org` | Companies, teams, projects with org-like ownership |
| `concept` | Abstract ideas, topics, methodologies |
| `tool` | Technologies, libraries, software |
| `document` | Files, articles, written artefacts |
| `event` | Time-bound activities |
| `relation` | Reified relationships (when an edge needs to carry data) |

Custom strings (`"pr"`, `"channel"`, `"library"`, `"issue"`) pass through untouched — `EntityType` just names the well-known ones so they don't drift across modules.

Eight built-in relation predicates: `mentions`, `related`, `depends_on`, `contributes_to`, `causes`, `follows`, `supersedes`, `owned_by`. Same open-string contract — any predicate is accepted on an edge.

#### Extraction contract

The cognitive engine's `extract_entities` returns one dict per entity:

```python
{
    "name": "Alice",
    "type": "person",
    "relation": "knows",          # optional first-person relation to user
    "relationships": [             # entity-to-entity edges
        {"target": "Acme", "relation": "owned_by", "weight": 0.9},
    ],
    "edge_metadata": {"source_memory_id": "ep-1", "extracted_at": "..."},
    "source_memory_id": "ep-1",
}
```

When an LLM `CognitiveEngine` is wired, the prompt asks for the typed ontology + relations + weight directly. When no engine is configured, the heuristic extractor produces typed entities via a translation table (`technology` -> `tool`, `organization` -> `org`, etc.) — the heuristic stays in place for offline / cost-constrained souls.

Re-extraction on the same interaction is **idempotent**: identical entities and edges are deduped, but the `(source, target, relation)` triple's metadata picks up the second memory's id in its `provenance` list.

#### Traversal API

`Soul.graph` returns a `GraphView` with read methods:

```python
soul.graph.nodes(type="person", name_match="ali", limit=20)
soul.graph.edges(source="Alice", relation="mentions")
soul.graph.neighbors("Alice", depth=2, types=["person", "tool"])
soul.graph.path("Alice", "Acme", max_depth=4)        # shortest path BFS
soul.graph.subgraph(["Alice", "Bob", "Acme"])
soul.graph.to_mermaid()                               # human inspection
```

`Soul.recall` accepts a `graph_walk` parameter that filters memories to those linked to entities reachable within `depth` hops:

```python
results = await soul.recall(
    "production rollout",
    graph_walk={"start": "Acme", "depth": 2, "edge_types": ["mentions", "owned_by"]},
    limit=10,
    token_budget=4000,   # overflow falls back to L0 abstracts (F1 mechanism)
)
if results.next_page_token:
    next_page = await soul.recall(..., page_token=results.next_page_token)
```

Memories rank by combined relevance + graph distance — closer entities surface first.

Trust chain entries (`graph.entity_added`, `graph.relation_added`) record net-new graph state on each `observe()` call. Payloads are compact (id/type/source) so the chain doesn't redundantly store memory content.

Example graph state after a few interactions:

```
Python  (tool)  --[uses]--> User       (person)
Acme    (org)   --[builds]--> User
FastAPI (tool)  --[uses]--> User
```


## Memory Layers and Domains (v0.4.0, #41)

Up to 0.3.x the four built-in tiers (`core`, `episodic`, `semantic`, `procedural`) were the only memory namespaces. v0.4.0 generalises this in two directions:

- **Layers** are free-form strings. The four built-ins keep their names and dedicated stores. A new `social` layer ships for relationship memories. Anything else is allowed — `MemoryEntry(layer="preferences")` is fine.
- **Domains** are sub-namespaces inside a layer. An entry can sit in `layer="semantic"` with `domain="finance"` while another sits in `layer="semantic"` with `domain="legal"`. Domain defaults to `"default"` so 0.3.x souls round-trip without migration.

### Layer constants

The well-known names live in `soul_protocol.spec.memory`:

```python
from soul_protocol.spec.memory import (
    LAYER_CORE,        # "core"
    LAYER_EPISODIC,    # "episodic"
    LAYER_SEMANTIC,    # "semantic"
    LAYER_PROCEDURAL,  # "procedural"
    LAYER_SOCIAL,      # "social"
    DEFAULT_DOMAIN,    # "default"
)
```

The runtime `MemoryType` StrEnum keeps the same value strings so existing code that compares `entry.type == MemoryType.SEMANTIC` keeps working.

### LayerView — uniform accessor

`MemoryManager.layer(name)` returns a `LayerView` that exposes the same small API for every layer regardless of which store actually backs it:

```python
view = soul._memory.layer("social")
sid = await view.store(MemoryEntry(
    type=MemoryType.SEMANTIC,
    content="Alice prefers async messages",
    importance=8,
))
results = await view.query("alice")          # search the layer
recent = view.entries(domain="finance")      # cross-domain or filtered
n = view.count(domain="finance")
```

Custom layer names are created lazily on first `store()` call. The legacy attribute access (`manager._semantic`, `manager._episodic`, ...) keeps working; `LayerView` is additive.

### Domain stamping

`Soul.remember()` and `Soul.observe()` accept a `domain` keyword:

```python
await soul.remember("Q3 revenue up 12%", domain="finance", importance=8)
await soul.observe(interaction, domain="finance")
```

The stamp lands on every memory written by that call (episodic + extracted facts).

### Domain-aware recall

`Soul.recall()` and `MemoryManager.recall()` accept `layer` and `domain` filters:

```python
fin = await soul.recall("revenue", layer="semantic", domain="finance")
all_finance = await soul.recall("budget", domain="finance")  # any layer
all_semantic = await soul.recall("python", layer="semantic")  # any domain
```

When neither filter is set, behaviour matches pre-#41 (cross-tier search across every domain).

### DomainIsolationMiddleware

When you want to hand one user / agent a sandboxed view of the soul, wrap it:

```python
from soul_protocol.runtime.middleware import DomainIsolationMiddleware

finance_only = DomainIsolationMiddleware(
    soul, allowed_domains=["finance", "default"]
)
await finance_only.remember("New OPEX line", importance=7)  # → "finance"
results = await finance_only.recall("revenue")              # filtered
await finance_only.remember("NDA fact", domain="legal")      # raises
```

Reads silently filter to the allow-list. Writes to a disallowed domain raise `DomainAccessError`. When no domain is given, the middleware defaults to `allowed_domains[0]`.

### On-disk layout

The persistence layer picks between two shapes:

- **Flat (legacy)**: every entry has `domain="default"` and uses a built-in layer. The on-disk shape is the pre-#41 `memory/episodic.json` + `memory/semantic.json` + `memory/procedural.json` + `memory/social.json` form, plus the unchanged companion files (`core.json`, `graph.json`, `self_model.json`, `general_events.json`).
- **Nested (layered)**: as soon as one entry uses a non-default domain or a custom layer name appears, the layout switches to `memory/<layer>/<domain>/entries.json`. A small `memory/_layout.json` marker records the choice. Custom layers (`memory/preferences/finance/entries.json`, ...) live alongside built-ins. Loaders auto-detect the layout — flat souls keep working, nested souls round-trip cleanly.

Both shapes are read transparently on awaken; you never have to call `soul migrate` for #41.

### Auto-migration

Loading a 0.3.x soul (no `domain` field, no `layer` field on `MemoryEntry`) populates `domain="default"` and derives `layer` from `type` automatically via a Pydantic `model_validator`. There is no separate migration step.

---

## Memory Visibility Tiers (v0.2.5)

Every `MemoryEntry` now carries a `visibility` field that controls who can access the memory. This adds a privacy layer on top of the existing memory system.

### Three Visibility Levels

| Level | Value | Who can see it |
|-------|-------|---------------|
| **PUBLIC** | `"public"` | Any requester -- visible to all connected agents, users, and bonded souls |
| **BONDED** | `"bonded"` | Only bonded souls/users -- the requester must have an active bond with the soul |
| **PRIVATE** | `"private"` | Only the soul itself -- invisible to all external requesters |

### How Visibility Filtering Works

Recall is automatically filtered by requester identity and bond strength. When `soul.recall()` is called:

1. The requester's identity (DID or session context) is checked
2. If the requester is the soul itself, all memories are visible (PUBLIC + BONDED + PRIVATE)
3. If the requester has an active bond with the soul, PUBLIC and BONDED memories are visible
4. Otherwise, only PUBLIC memories are returned

This filtering happens transparently inside the recall engine -- callers do not need to manually filter results.

### Setting Visibility

Visibility can be set at creation time or updated later:

```python
# Set visibility when observing
await soul.observe(
    "User shared their home address",
    visibility="private"
)

# Set visibility when remembering a fact
await soul.remember(
    "User's favorite color is blue",
    visibility="public"
)

# Default visibility is PUBLIC for backward compatibility
```

Visibility is persisted in the `.soul` file and survives export/import round-trips. Existing memories without a visibility field default to `PUBLIC` during migration.


## Psychology Pipeline (observe())

The `observe()` method runs five psychology-informed steps on every interaction. The pipeline is routed through `CognitiveProcessor`, which delegates to either an LLM (`CognitiveEngine`) or built-in heuristics (`HeuristicEngine`).

### Step 1: Sentiment Detection (Damasio's Somatic Marker Hypothesis)

The heuristic approach scans text against ~150 emotion words with pre-assigned valence scores.

**Modifiers:**

| Type | Examples | Effect |
|------|----------|--------|
| Intensifiers | very (1.3x), extremely (1.5x), super (1.3x) | Scale up valence and arousal |
| Diminishers | slightly (0.5x), somewhat (0.6x), barely (0.4x) | Scale down |
| Negation | not, don't, never, can't, isn't | Flip valence (3-word lookback window) |

Negated positives become mild negatives (score * 0.7). Negated negatives become mild positives (score * 0.5). This asymmetry reflects how "not bad" is weaker than "good."

**Output:** `SomaticMarker(valence: -1.0 to 1.0, arousal: 0.0 to 1.0, label: str)`

Valence-arousal quadrants:

| Arousal | Positive Valence | Negative Valence |
|---------|-----------------|-----------------|
| High | excitement, enthusiasm | frustration, anger |
| Low | joy, gratitude, contentment | sadness, melancholy |

With a `CognitiveEngine` attached, the LLM returns structured JSON for richer, context-aware sentiment. On parse failure, the system falls back to the heuristic.

### Step 2: Significance Gate (LIDA Architecture -- Franklin)

Not every interaction deserves to become a memory. The LIDA-inspired significance gate scores each interaction on three dimensions:

**Formula:**

```
novelty = 1.0 - avg_similarity(text, recent_10_contents)
emotional_intensity = min(1.0, arousal + |valence| * 0.3)
goal_relevance = token_overlap(text, core_values)

overall = 0.4 * novelty + 0.35 * emotional + 0.25 * goal
threshold: 0.3
```

A length bonus is applied: `min(0.2, token_count * 0.01)` added to novelty. This naturally penalizes terse greetings and boosts substantive messages.

If significant: the interaction is stored in episodic memory with its somatic marker.

If not significant: the interaction still passes through fact extraction and entity extraction. Mundane "hello" exchanges skip episodic memory but the soul still learns from them.

### Step 3: Fact Extraction

**Heuristic mode** uses 10 regex patterns:

| Pattern | Example Match | Importance |
|---------|--------------|------------|
| `my name is (\w+)` | "my name is Prakash" | 9 |
| `i(?:'m\| am) (?:a\|an )?(\w[\w\s]{2,30})` | "I'm a developer" | 7 |
| `i (?:prefer\|like\|love) ...` | "I love Python" | 7 |
| `i (?:hate\|dislike) ...` | "I hate YAML" | 7 |
| `i (?:use\|work with\|am using) ...` | "I use Docker" | 6 |
| `i(?:'m\| am) (?:building\|creating) ...` | "I'm building Acme" | 7 |
| `i (?:work at\|work for) ...` | "I work at Qbtrix" | 8 |
| `i(?:'m\| am) from ...` | "I'm from India" | 7 |
| `i live in ...` | "I live in NYC" | 7 |
| `my favorite (\w+) is ...` | "my favorite language is Rust" | 6 |

**Deduplication:** Jaccard token overlap > 0.7 with any existing fact skips the new fact.

**With CognitiveEngine:** The LLM returns a JSON array of facts with content and importance. On parse failure, the heuristic extractor runs as fallback.

**Fact Conflict Resolution (v0.2.2):** When a new fact contradicts an existing one -- detected by matching template prefixes (e.g., "User lives in") -- the old fact gets `superseded_by = new_fact_id`. Both facts persist in storage, but superseded facts are excluded from `search()` and `facts()` by default. You can access the full history with `facts(include_superseded=True)`.

**User-driven Supersede (2026-04-27):** The same `superseded_by` mechanism is exposed to callers via `Soul.supersede(old_id, new_content, *, reason, importance, memory_type, ...)` and the `soul supersede` CLI command. Use it when you have learned that an existing memory is wrong or out of date and want to record the correction without losing provenance. The runtime writes a new memory entry, sets the old entry's `superseded_by` to the new ID, and appends a record to a parallel `supersede_audit` trail (read it via `Soul.supersede_audit`). Internal supersession from the dream cycle and contradiction detector does not write to that trail — it is for explicit user intent only. Recall surfaces the new memory because superseded entries are filtered out of search; the old entry is still on disk under `facts(include_superseded=True)` for "what I once thought" queries.

### Step 4: Entity Extraction

Three detection strategies run in sequence:

1. **Known tech terms:** A set of 70+ technology names matched case-insensitively (Python, React, Docker, Kubernetes, FastAPI, etc.). These are typed as `"technology"`.

2. **Capitalized words:** Words that are (a) not at the start of a sentence, (b) not in the stop-word list (~70 common words), and (c) at least 2 characters long. These are guessed as `"person"` by default.

3. **Relationship inference:** Regex patterns map surrounding context to relation verbs:
   - `i use/work with ...` -> `uses`
   - `i'm building/creating ...` -> `builds` (also upgrades entity type to `"project"`)
   - `i prefer/like/love ...` -> `prefers`
   - `i work at/for ...` -> `works_at`
   - `i'm learning/studying ...` -> `learns`

Extracted entities are fed into the knowledge graph via `update_graph()`.

### Step 4d: Contradiction Pipeline (v0.2.5)

After entity extraction, `observe()` now runs a raw-text contradiction scan against the semantic store on every memory write. This is handled by the `ContradictionDetector`, which catches life-change statements that the older template-prefix approach would miss.

**How it works:**

1. The `ContradictionDetector` scans the incoming text for verb-fact patterns that signal a state change.
2. Detected patterns include:
   - **Location changes:** "moved to X", "relocated to X", "living in X now"
   - **Employer changes:** "joined Y", "works at Z", "started at Y", "left Z"
   - **Role changes:** "promoted to X", "switched to X role", "now a X"
   - **Relationship changes:** "married", "divorced", "broke up with"
3. For each detected verb-fact pattern, the detector queries the semantic store for existing facts with overlapping subjects (e.g., all facts about where the user lives or works).
4. Contradicting facts are automatically marked as superseded (`superseded_by = new_fact_id`) rather than accumulating as duplicates.

**Example:**

```python
# Session 1: user says "I work at Acme Corp"
# -> Semantic memory stores: "User works at Acme Corp"

# Session 2: user says "I joined Globex last month"
# -> ContradictionDetector matches "joined Y" pattern
# -> Finds existing fact "User works at Acme Corp"
# -> Supersedes old fact, stores "User works at Globex"
```

This runs as part of the standard `observe()` pipeline -- no additional API calls needed. The detector integrates between entity extraction (Step 4) and self-model update (Step 5), ensuring the knowledge graph and semantic store stay consistent.

### Step 5: Self-Model Update (Klein's Self-Concept)

The soul learns who it is from accumulated interactions. Six fixed domains are tracked:

- `technical_helper`
- `creative_writer`
- `knowledge_guide`
- `problem_solver`
- `creative_collaborator`
- `emotional_companion`

Each domain has a list of associated keywords (15-20 per domain). When keywords from an interaction match a domain, the evidence count is incremented.

**Confidence formula (diminishing returns):**

```
confidence = min(0.95, 0.1 + 0.85 * (1 - 1 / (1 + evidence * 0.1)))
```

Growth curve:
- After 1 evidence: ~0.18
- After 10 evidence: ~0.56
- After 50 evidence: ~0.82
- Asymptote: 0.95 (never reaches 1.0 -- the soul never claims absolute certainty)

The soul also extracts relationship notes from facts. If a fact contains "user's name is" or "user works at," it updates the relationship notes accordingly.

With a `CognitiveEngine`, the LLM provides richer self-reflection and can create new domains beyond the six fixed ones.


## Memory Retrieval (ACT-R Activation)

### Scoring Formula (Anderson's ACT-R)

Every memory entry gets an activation score that determines retrieval priority. The model is based on Anderson's ACT-R theory: memories that are used more recently and more frequently are more active.

```
base_level = ln(sum(t_j^(-0.5) for t_j in access_timestamps))
spreading  = token_overlap(query, content)  # or SearchStrategy.score()
emotional  = arousal + |valence| * 0.3
total      = 1.0 * base + 1.5 * spread + 0.5 * emo + noise(0, 0.1)
```

**Parameters:**

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `DECAY_RATE` | 0.5 | ACT-R power-law decay exponent |
| `W_BASE` | 1.0 | Weight for base-level activation |
| `W_SPREAD` | 1.5 | Weight for spreading activation (query relevance) |
| `W_EMOTION` | 0.5 | Weight for emotional boost |
| `NOISE_SCALE` | 0.1 | Gaussian noise standard deviation |
| `MAX_ACCESS_TIMESTAMPS` | 100 | Cap per entry to bound memory growth |

**Graceful degradation:** Entries with no `access_timestamps` (pre-v0.2.0 data) fall back to importance-weighted scoring: `base = (importance - 5) * 0.2`, mapping importance 1-10 to roughly -0.8 to 1.0.

**Noise:** During recall ranking, noise is disabled (`noise=False`) for deterministic results. Noise is available for creative/exploration use cases.

### Cross-Store Recall

`soul.recall(query)` searches across episodic, semantic, and procedural stores simultaneously:

1. Each store runs its own `search()` to find candidates with relevance > 0.0
2. All candidates are merged into a single list
3. Candidates are scored by ACT-R activation (without noise)
4. **Visibility filtering** is applied based on requester identity and bond strength (v0.2.5)
5. Results are sorted by activation descending and returned up to `limit`
6. Access timestamps on retrieved entries are updated (strengthens future recall)

The timestamp update creates a reinforcement loop: memories that get recalled become easier to recall again. This mirrors the psychological "use it or lose it" principle.

```python
memories = await soul.recall("Python deployment", limit=5)
for mem in memories:
    print(f"[{mem.type.value}] {mem.content[:80]}")
```

You can filter by memory type:

```python
from soul_protocol.types import MemoryType

facts = await soul.recall(
    "programming languages",
    types=[MemoryType.SEMANTIC],
    min_importance=5,
)
```


## Pluggable Retrieval (SearchStrategy)

The default retrieval uses `TokenOverlapStrategy` -- Jaccard token overlap with zero external dependencies. You can replace it with any scoring function that implements the `SearchStrategy` protocol.

**Protocol:**

```python
class SearchStrategy(Protocol):
    def score(self, query: str, content: str) -> float: ...
```

One method. Returns a float from 0.0 to 1.0. The score feeds into ACT-R spreading activation, replacing the default token overlap in the `spreading` component.

**Example: Embedding-based search:**

```python
from soul_protocol import SearchStrategy
import numpy as np

class EmbeddingSearch:
    def __init__(self, embed_fn):
        self.embed_fn = embed_fn

    def score(self, query: str, content: str) -> float:
        q = self.embed_fn(query)
        c = self.embed_fn(content)
        return float(np.dot(q, c) / (np.linalg.norm(q) * np.linalg.norm(c)))

soul = await Soul.birth("Aria", search_strategy=EmbeddingSearch(my_embed))
```

The strategy is injected at `Soul.birth()` and propagates to `RecallEngine` and `compute_activation()`. You do not need to change any other code.


## Real Embedding Providers (v0.2.5)

While the `SearchStrategy` protocol lets you bring any scoring function, v0.2.5 ships three production-ready embedding providers that plug directly into the memory pipeline for vector-based semantic recall. These replace the hash-based default with real embeddings.

### Available Providers

| Provider | Class | Backend | Dependencies |
|----------|-------|---------|-------------|
| **SentenceTransformer** | `SentenceTransformerEmbedder` | Local model (e.g., `all-MiniLM-L6-v2`) | `sentence-transformers` |
| **OpenAI** | `OpenAIEmbedder` | OpenAI Embeddings API (`text-embedding-3-small`) | `openai` |
| **Ollama** | `OllamaEmbedder` | Local via Ollama server | `httpx` (already a dep) |

### Usage

```python
from soul_protocol.runtime.embeddings import SentenceTransformerEmbedder

embedder = SentenceTransformerEmbedder(model="all-MiniLM-L6-v2")
soul = await Soul.birth("Aria", search_strategy=embedder)
```

```python
from soul_protocol.runtime.embeddings import OpenAIEmbedder

embedder = OpenAIEmbedder(api_key="sk-...", model="text-embedding-3-small")
soul = await Soul.birth("Aria", search_strategy=embedder)
```

```python
from soul_protocol.runtime.embeddings import OllamaEmbedder

embedder = OllamaEmbedder(model="nomic-embed-text", base_url="http://localhost:11434")
soul = await Soul.birth("Aria", search_strategy=embedder)
```

All three implement `SearchStrategy`, so they drop in wherever the default `TokenOverlapStrategy` was used. Each provider computes cosine similarity between query and content embeddings, returning a 0.0-1.0 score that feeds into the ACT-R spreading activation component.

The hash-based default remains the zero-dependency fallback. No new required dependencies were added to the core package -- each embedding provider is an optional extra (`pip install soul-protocol[embeddings]` for SentenceTransformer, or bring your own OpenAI/Ollama client).


## Reflection and Consolidation

### reflect()

`soul.reflect()` triggers an LLM-driven consolidation pass over the 20 most recent episodic memories. The LLM identifies:

- **Themes** across recent interactions
- **Summaries** that compress multiple episodes into semantic memories
- **Emotional patterns** worth noting
- **Self-insight** -- what the soul learned about itself

Returns a `ReflectionResult` with `themes`, `summaries`, `emotional_patterns`, and `self_insight`.

**Requires a CognitiveEngine.** With `HeuristicEngine`, `reflect()` returns `None` because genuine cross-episode reasoning needs an LLM.

### consolidate()

When `soul.reflect(apply=True)` (the default), the `ReflectionResult` is applied to memory:

1. **Summaries** become new semantic memories with importance scores from the LLM
2. **Themes** create or update `GeneralEvent` objects (Conway's Self-Memory System hierarchy). Episodes matching a theme (token overlap > 0.3) are linked via `general_event_id`
3. **Self-insight** is stored in the self-model's relationship notes
4. **Emotional patterns** are stored as semantic memories with importance 6

The consolidation returns a dict summarizing what was applied:

```python
result = await soul.reflect()
# result: {"summaries": 3, "general_events": 2, "self_insight": True, "emotional_pattern": True}
```


## Long Context Memory (v0.2.5)

The `soul_protocol.runtime.context` package provides Long Context Memory (LCM) -- a SQLite-backed conversation store that keeps conversations coherent at 100k+ tokens without losing earlier context.

### Problem

Long conversations exceed LLM context windows. Naive truncation loses early context. Simply stuffing everything into the prompt wastes tokens on low-relevance turns.

### Architecture

LCM introduces `ContextStore`, which sits alongside the 5-tier memory system and handles raw conversation history with intelligent compaction.

```
Conversation Turns
    |
    v
+---------------------------+
|      ContextStore         |
|  (SQLite-backed)          |
|                           |
|  Recent turns  -> Full    |
|  Older turns   -> Bullets |
|  Ancient turns -> Summary |
+---------------------------+
    |
    v
  Compacted context window
  (fits within token budget)
```

### Three-Level Compaction

| Level | Age | Representation | Token cost |
|-------|-----|----------------|------------|
| **Full** | Recent (last N turns) | Original text, verbatim | High |
| **Bullets** | Older | Key points as bullet list | ~20% of original |
| **Summary** | Ancient | Single paragraph summary | ~5% of original |

Compaction runs automatically when the context window exceeds the configured token budget. Turns are progressively compressed from oldest to newest:

1. **Summary**: The oldest turns are collapsed into a running summary paragraph
2. **Bullets**: Mid-age turns are reduced to bullet-point key points
3. **Truncate**: If still over budget after compaction, the least-relevant bullets are dropped

### Relevance-Weighted Retrieval

Not all past conversation is equally relevant to the current turn. LCM builds a hierarchical DAG (directed acyclic graph) of conversation topics and retrieves context weighted by relevance to the active topic.

When assembling context for a new turn:

1. The current message is analyzed for topic signals
2. The DAG is traversed to find related earlier conversation segments
3. Relevant segments are promoted (kept at higher fidelity) even if they are old
4. Irrelevant segments are compacted more aggressively

This means a user can reference something from 200 turns ago and the soul will still have that context available -- as long as it is topically connected.

### Usage

```python
from soul_protocol.runtime.context import ContextStore

store = ContextStore(db_path="conversations.db")

# Record turns
await store.add_turn(role="user", content="Tell me about Python decorators")
await store.add_turn(role="assistant", content="Decorators are functions that...")

# Get compacted context for the next LLM call
context = await store.get_context(token_budget=4000)
# Returns a list of messages, with older turns compacted
```

### Zero New Dependencies

`ContextStore` uses `sqlite3` from the Python standard library. No additional packages are required. The SQLite database is stored alongside the `.soul` file or at a configurable path.


## Memory Settings

```python
MemorySettings(
    episodic_max_entries=10000,   # Max episodic memories before eviction
    semantic_max_facts=1000,      # Max semantic facts before eviction
    importance_threshold=3,       # Minimum importance to store
    confidence_threshold=0.7,     # Minimum confidence for facts
    persona_tokens=500,           # Core memory persona token limit
    human_tokens=500,             # Core memory human token limit
)
```

Settings are passed at soul creation and persisted in the `.soul` file. They can be adjusted for different deployment scenarios:

- **Low-memory devices:** Reduce `episodic_max_entries` to 1,000 and `semantic_max_facts` to 200
- **Long-running companions:** Increase limits and rely on eviction policies to keep quality high
- **Testing:** Use small limits (100/50) for fast iteration


## Memory Categories (v2)

Every `MemoryEntry` can be assigned a `MemoryCategory` that classifies its semantic role. The `MemoryCategory` enum defines 7 values:

| Category | Description | Example |
|----------|-------------|---------|
| `profile` | Identity facts about the user or soul | "User's name is Prakash" |
| `preference` | Likes, dislikes, style choices | "User prefers dark mode" |
| `entity` | Named things: people, places, organizations | "User works at Qbtrix" |
| `event` | Time-bound happenings | "Deployed v0.2.2 on Tuesday" |
| `case` | Problem/solution pairs, debugging sessions | "Fixed the OOM by reducing batch size" |
| `pattern` | Recurring behaviors, workflows | "User always reviews PRs before merging" |
| `skill` | Learned capabilities, domain knowledge | "User is proficient in async Python" |

Categories are assigned automatically during fact extraction via the `classify_memory_category()` heuristic. The heuristic checks content against keyword patterns for each category and picks the best match. When no pattern matches, the default is `preference` for semantic memories and `event` for episodic memories.

Categories power filtered recall: `soul.recall("Python", categories=[MemoryCategory.SKILL, MemoryCategory.PREFERENCE])`.


## Salience (v2)

Each `MemoryEntry` carries an optional `salience` field -- an additive boost applied during ACT-R activation scoring. The range is **-0.25 to +0.25**.

```
total = W_BASE * base + W_SPREAD * spread + W_EMOTION * emo + salience + noise
```

Salience lets the system (or an LLM judge) mark certain memories as more or less retrievable without changing their importance score. Use cases:

- **Positive salience (+0.1 to +0.25):** Key architectural decisions, user corrections, safety-critical facts. These should surface even when activation would otherwise decay them.
- **Negative salience (-0.1 to -0.25):** Stale preferences the user has moved past, superseded patterns. Soft-demoting without deletion.
- **Zero (default):** No boost. Standard ACT-R decay applies.

Salience is persisted in the `.soul` file and survives export/import round-trips.


## Content Layers: L0 and L1 (v2)

Long memories are expensive to inject into LLM context. Content layers provide progressive loading:

- **L0 (abstract):** A compressed summary of the memory, roughly 100 tokens. Generated automatically when a memory is created. Used for listing and scanning large memory sets without blowing up context.
- **L1 (overview):** A more detailed summary, roughly 1,000 tokens. Generated on demand or during reflection. Provides enough detail for most recall scenarios.
- **Full content:** The original, uncompressed memory text. Loaded only when a client explicitly requests the full entry.

Fields on `MemoryEntry`:

| Field | Type | Size | When generated |
|-------|------|------|----------------|
| `content` | `str` | Full | Always (original text) |
| `abstract` | `str` or `None` | ~100 tokens | On creation (first sentence, ~400 chars) |
| `overview` | `str` or `None` | ~1K tokens | On demand or during reflection |

Recall results include `abstract` by default. Clients can request `full=True` to get the complete content. This keeps context budgets manageable for souls with thousands of memories.

### Abstract Generation

Abstracts are generated using a simple heuristic: take the first sentence of the content, capped at approximately 400 characters. If the content is shorter than 400 characters, the abstract equals the full content. The heuristic splits on sentence boundaries (`.`, `!`, `?`) and picks the first complete sentence.

With a `CognitiveEngine` attached, the LLM generates a more meaningful abstract that captures the key point rather than just the first sentence.


## Extraction Taxonomy (v2)

The `classify_memory_category()` function assigns a `MemoryCategory` to extracted facts. It runs as part of the fact extraction step in the psychology pipeline.

**Heuristic classification rules (checked in order):**

1. **profile** -- matches patterns like "name is", "I am a", "I'm from", "born in"
2. **entity** -- matches patterns like "works at", "works for", capitalized proper nouns with relational context
3. **skill** -- matches patterns like "proficient in", "experienced with", "knows how to", technology keywords
4. **preference** -- matches patterns like "prefer", "like", "love", "hate", "dislike", "favorite"
5. **event** -- matches temporal markers: "yesterday", "last week", "on Monday", date patterns
6. **case** -- matches problem/solution language: "fixed", "solved", "debugged", "the issue was"
7. **pattern** -- matches frequency language: "always", "usually", "every time", "tends to"

If no rule matches, the fallback is `preference` for semantic entries and `event` for episodic entries.

With a `CognitiveEngine`, the LLM classifies categories with richer context understanding, handling ambiguous cases that keyword matching misses.


## Deduplication Pipeline (v2)

The `reconcile_fact()` function runs before storing any new semantic fact. It prevents duplicates and handles updates to existing knowledge.

**Algorithm:**

1. Compute Jaccard token overlap between the new fact and every existing fact in semantic memory.
2. Find the highest-overlap match.
3. Apply thresholds:

| Overlap | Action | Rationale |
|---------|--------|-----------|
| > 0.85 | **SKIP** | Near-duplicate. The existing fact already captures this knowledge. |
| 0.6 -- 0.85 | **MERGE** | Partial overlap. Update the existing fact's content and bump its importance. The old content is preserved in `superseded_by` linkage. |
| < 0.6 | **CREATE** | Sufficiently novel. Store as a new fact. |

The merge operation combines the new information with the existing fact. If a `CognitiveEngine` is available, the LLM produces a merged statement. Otherwise, the newer fact replaces the older one (with `superseded_by` tracking).

This three-tier approach (skip / merge / create) replaces the earlier binary dedup (overlap > 0.7 = skip, otherwise create) and reduces semantic memory bloat while preserving knowledge evolution history.


## Serialization

The entire memory state serializes to a plain dict via `MemoryManager.to_dict()`:

```python
data = soul._memory.to_dict()
# {
#     "core": {"persona": "...", "human": "..."},
#     "episodic": [...],
#     "semantic": [...],
#     "procedural": [...],
#     "graph": {"entities": {...}, "edges": [...]},
#     "self_model": {"self_images": {...}, "relationship_notes": {...}},
#     "general_events": [...],
#     "archives": [...]
# }
```

Reconstitution via `MemoryManager.from_dict(data, settings)` restores the full state, including superseded facts, access timestamps, general events, and archives. This powers `.soul` file persistence and migration.

---

## Archival Memory (v0.2.9)

Old episodic memories are compressed into `ConversationArchive` objects to prevent unbounded growth:

```python
archive = await soul._memory.archive_old_memories(max_age_hours=48.0)
```

**How it works:**
1. Gathers episodic entries older than `max_age_hours` (default 48h)
2. Skips if fewer than 3 entries (not enough to archive)
3. Generates a heuristic summary (first sentence of each entry, capped at 10)
4. Extracts key moments (entries with importance >= 7)
5. Creates a `ConversationArchive` with provenance (memory_refs to original IDs)
6. Marks original entries `archived=True` — these are filtered from recall

Archives persist through `to_dict()`/`from_dict()` and survive export/awaken. Search archives via `soul._memory.archival.search_archives(query)`.

---

## Auto-Consolidation (v0.2.9)

Memory hygiene runs automatically during `observe()`:

```python
# In MemorySettings:
consolidation_interval: int = 20  # Every 20 interactions
```

Every `consolidation_interval` interactions, `observe()` auto-triggers:
1. **Archive old memories** — compresses episodics older than 48h
2. **Reflect + consolidate** — if a CognitiveEngine is available, runs reflection to extract themes, summaries, and self-insights into semantic memory

The interaction count is persisted in `SoulConfig` so it survives across sessions.

Set `consolidation_interval=0` to disable auto-consolidation.

---

## Progressive Recall (v0.2.9)

When building context windows, you can request overflow entries with compressed content:

```python
results = await soul.recall("topic", limit=5, progressive=True)
# results[0:5] — full content (primary)
# results[5:10] — abstract-only content (overflow, marked is_summarized=True)
```

**How it works:**
- Fetches `limit * 2` candidates from each store (more candidates = better ranking)
- After ACT-R scoring, splits into primary (full content) and overflow (abstract)
- Overflow entries use `model_copy()` to avoid mutating in-store objects
- Entries without an abstract keep their full content in the overflow

This lets callers build token-budgeted context: full content for the most relevant memories, L0 abstracts for "see more" context.

---

## Skill Progression and Decay (v0.2.9)

Skills track domain expertise with XP and leveling:

- **XP grants are significance-weighted**: `max(5, int(significance * 30))` — range 5-30 per interaction
- **Daily decay**: dormant skills lose 1 XP per day inactive, floor at 0, never reduces level
- **Decay runs at start of observe()**: stale skills shed XP before new XP is granted
- **Leveling**: XP thresholds scale exponentially (100 → 150 → 225 → ...), level cap at 10

```python
soul.skills  # SkillRegistry with all learned skills
soul.skills.get("python")  # Skill(id="python", level=3, xp=45, ...)
```

Skills persist through export/awaken via `SoulConfig.skills`.
