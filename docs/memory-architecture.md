<!-- Covers: The 5-tier memory system, psychology-informed observe() pipeline,
     ACT-R activation scoring, cross-store recall, pluggable retrieval,
     reflection/consolidation, fact conflict resolution, and memory settings. -->

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

The knowledge graph tracks entity relationships using directed edges.

Structure:

- Entities: dict mapping name to type (technology, person, project, place)
- Edges: list of `(source, target, relation)` tuples
- Relations: `uses`, `builds`, `prefers`, `works_at`, `learns`, `related_to`
- No external dependencies -- implemented with plain Python dicts
- Duplicate edges are silently ignored
- Entities are auto-created when a relationship references them

Example graph state after a few interactions:

```
Python --[uses]--> User
PocketPaw --[builds]--> User
FastAPI --[uses]--> User
```


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
| `i(?:'m\| am) (?:building\|creating) ...` | "I'm building PocketPaw" | 7 |
| `i (?:work at\|work for) ...` | "I work at Qbtrix" | 8 |
| `i(?:'m\| am) from ...` | "I'm from India" | 7 |
| `i live in ...` | "I live in NYC" | 7 |
| `my favorite (\w+) is ...` | "my favorite language is Rust" | 6 |

**Deduplication:** Jaccard token overlap > 0.7 with any existing fact skips the new fact.

**With CognitiveEngine:** The LLM returns a JSON array of facts with content and importance. On parse failure, the heuristic extractor runs as fallback.

**Fact Conflict Resolution (v0.2.2):** When a new fact contradicts an existing one -- detected by matching template prefixes (e.g., "User lives in") -- the old fact gets `superseded_by = new_fact_id`. Both facts persist in storage, but superseded facts are excluded from `search()` and `facts()` by default. You can access the full history with `facts(include_superseded=True)`.

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
4. Results are sorted by activation descending and returned up to `limit`
5. Access timestamps on retrieved entries are updated (strengthens future recall)

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
#     "general_events": [...]
# }
```

Reconstitution via `MemoryManager.from_dict(data, settings)` restores the full state, including superseded facts, access timestamps, and general events. This powers `.soul` file persistence and migration.
