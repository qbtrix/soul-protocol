<!-- Covers: Design philosophy, full module structure, psychology stack (Damasio, ACT-R, LIDA, Klein),
     data flow for observe() and recall(), CognitiveEngine interface, integration patterns,
     known limitations, and version history. -->

# Architecture

## Design Philosophy

Soul Protocol is built on three principles:

1. **Identity is portable.** Souls are not locked to any platform, LLM provider, or hosting environment. The `.soul` file is a self-contained zip archive that can be moved between machines, backed up, or shared.

2. **Memory is psychology-informed.** This is not a vector database with similarity search bolted on. Every memory carries emotional metadata, activation history, and significance scores. Retrieval models cognitive science -- memories that are accessed often, emotionally intense, or recently formed surface first.

3. **Simplicity of integration.** One method to plug in an LLM (`CognitiveEngine.think()`). One method to plug in embeddings (`SearchStrategy.score()`). Everything else works out of the box with zero-dependency heuristic fallbacks.

## Module Structure

```
soul_protocol/
  soul.py              -- Main Soul class (orchestrator)
  types.py             -- All Pydantic models and enums
  __init__.py           -- Public API exports
  |
  cognitive/
    engine.py           -- CognitiveEngine protocol, CognitiveProcessor, HeuristicEngine
    prompts.py          -- 6 prompt templates for LLM cognitive tasks
  |
  memory/
    manager.py          -- MemoryManager (orchestrates all memory operations)
    activation.py       -- ACT-R activation scoring (recency + frequency + emotion)
    attention.py        -- LIDA significance gate (novelty + emotion + goal relevance)
    sentiment.py        -- Damasio somatic markers (heuristic sentiment detection)
    self_model.py       -- Klein self-concept (6 domains, logistic confidence curve)
    recall.py           -- RecallEngine (cross-store search with activation ranking)
    search.py           -- Token overlap utilities (Jaccard similarity)
    strategy.py         -- SearchStrategy protocol + TokenOverlapStrategy
    episodic.py         -- Episodic memory store (interaction history)
    semantic.py         -- Semantic memory store (extracted facts)
    procedural.py       -- Procedural memory store (how-to knowledge)
    graph.py            -- Knowledge graph (entity relationships)
    core.py             -- CoreMemoryManager (persona + human, always loaded)
  |
  identity/
    did.py              -- DID generation (did:soul:{name}-{hash})
  |
  dna/
    prompt.py           -- System prompt generation from DNA + identity + state
  |
  state/
    manager.py          -- StateManager (mood, energy, focus, social battery)
  |
  evolution/
    manager.py          -- EvolutionManager (mutation proposal, approval, application)
  |
  export/
    pack.py             -- .soul zip archive creation
    unpack.py           -- .soul zip archive extraction
  |
  storage/
    file.py             -- FileStorage (YAML/JSON persistence, atomic writes)
    memory_store.py     -- InMemoryStorage (ephemeral, for testing)
    protocol.py         -- Storage protocol definition
  |
  parsers/
    markdown.py         -- SOUL.md parser
    yaml_parser.py      -- YAML parser
    json_parser.py      -- JSON parser
  |
  crypto/
    encrypt.py          -- Encryption utilities (reserved)
  |
  cli/
    main.py             -- Click CLI (7 commands: birth, inspect, status, export, migrate, retire, list)
  |
  mcp/
    __init__.py         -- create_server(), run_server()
    server.py           -- FastMCP server (10 tools, 3 resources, 2 prompts)
```

## Psychology Stack

The memory system implements four cognitive science theories. Each one handles a different aspect of how memories form, persist, and surface.

### 1. Damasio's Somatic Marker Hypothesis

Every memory receives emotional metadata via a `SomaticMarker`:

- **Valence** (-1.0 to 1.0): negative to positive emotional tone
- **Arousal** (0.0 to 1.0): calm to intense
- **Label**: human-readable emotion name (joy, frustration, curiosity, etc.)

The key insight from Damasio: emotions are not separate from cognition. They guide recall and decision-making. Emotionally marked memories activate more strongly during retrieval.

**Implementation:** `memory/sentiment.py` provides heuristic detection. When a `CognitiveEngine` (LLM) is available, sentiment is detected via prompt instead, with heuristic as fallback.

### 2. Anderson's ACT-R (Adaptive Control of Thought -- Rational)

Memory activation determines which memories surface during recall. The formula combines four components:

```
activation = W_BASE * base_level + W_SPREAD * spreading + W_EMOTION * emotional + noise
```

| Component | Weight | Source |
|-----------|--------|--------|
| Base-level activation | 1.0 | Power-law decay over access timestamps: `B_i = ln(sum(t_j^(-d)))` |
| Spreading activation | 1.5 | Query-memory relevance (token overlap or custom SearchStrategy) |
| Emotional boost | 0.5 | Somatic marker intensity (arousal + abs(valence) * 0.3) |
| Stochastic noise | 0.1 | Gaussian noise for natural variability |

Memories that are accessed more frequently and recently have higher base-level activation. This naturally implements both recency and frequency effects through a single mechanism -- the same power-law decay curve that ACT-R uses for human memory.

**Graceful degradation:** Entries with no `access_timestamps` (e.g., imported from older formats) fall back to importance-weighted scoring.

**Implementation:** `memory/activation.py`

### 3. Franklin's LIDA (Learning Intelligent Distribution Agent)

The significance gate determines what enters episodic memory. Not every interaction deserves to be remembered. A "hello / hi there" exchange is mundane; "my name is Prakash and I'm building a startup" is significant.

Three dimensions are scored:

| Dimension | Weight | How it is measured |
|-----------|--------|--------------------|
| Novelty | 0.40 | Inverse similarity to recent episodic memories |
| Emotional intensity | 0.35 | From somatic marker detection |
| Goal relevance | 0.25 | Token overlap with the soul's core values |

The overall significance score is the weighted sum. The default threshold is **0.3** -- interactions below this are still processed for fact extraction (semantic memory) but do not create episodic entries.

A length bonus is applied to novelty: longer messages are slightly more likely to be significant. This penalizes short greetings while remaining fair to substantive single-sentence messages.

**Implementation:** `memory/attention.py`

### 4. Klein's Self-Concept

The soul builds a model of itself across 6 domains:

| Domain | Example keywords |
|--------|-----------------|
| `technical_helper` | python, code, debug, api, deploy |
| `creative_writer` | write, story, poem, narrative, blog |
| `knowledge_guide` | explain, teach, learn, research, tutorial |
| `problem_solver` | solve, fix, issue, troubleshoot, diagnose |
| `creative_collaborator` | brainstorm, idea, design, prototype, iterate |
| `emotional_companion` | feel, support, listen, care, empathy |

Evidence accumulates via a logistic curve: `confidence = 0.1 + 0.85 * (1 - 1/(1 + count * 0.1))`. This means confidence starts at 0.1, grows with evidence, and asymptotically approaches 0.95 -- the soul becomes more certain about its identity over time but never reaches absolute certainty.

The top 3 self-images (by confidence) are included in the system prompt under a "Self-Understanding" section, so the LLM can reference the soul's self-concept during generation.

**Implementation:** `memory/self_model.py`

## CognitiveEngine Interface

The `CognitiveEngine` protocol is the single integration point for LLM access:

```python
class CognitiveEngine(Protocol):
    async def think(self, prompt: str) -> str: ...
```

Implement this with any LLM client:

```python
class OpenAIEngine:
    def __init__(self, client, model="gpt-4o"):
        self.client = client
        self.model = model

    async def think(self, prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
```

When no engine is provided, the `HeuristicEngine` kicks in automatically. It routes prompts to the appropriate v0.2.0 heuristic module based on `[TASK:xxx]` markers embedded in the prompt templates. This means soul-protocol works fully offline with zero LLM dependencies -- the heuristics handle sentiment detection, significance scoring, fact extraction, entity detection, and self-model updates.

The `CognitiveProcessor` orchestrates this: it wraps the engine, constructs prompts, parses JSON responses, and falls back to heuristics on parse failure.

## Data Flow

### `observe()` Flow

Called after every user-agent interaction. This is the main learning pathway.

```
Interaction (user_input + agent_output)
  |
  v
1. detect_sentiment(user_input)
   -> SomaticMarker {valence, arousal, label}
  |
  v
2. assess_significance(interaction, core_values, recent_episodes)
   -> SignificanceScore {novelty, emotional_intensity, goal_relevance}
   -> overall = 0.4*novelty + 0.35*emotion + 0.25*goal
  |
  v
3. [if overall >= 0.3] add_episodic(interaction, somatic, significance)
   -> episodic memory entry with emotional metadata
  |
  v
4. extract_facts(interaction)
   -> resolve_fact_conflicts(new_facts vs existing_facts)
   -> add each fact to semantic store
  |
  v
5. extract_entities(interaction)
   -> update knowledge graph (entities + relationships)
  |
  v
6. update_self_model(interaction, facts)
   -> increment domain evidence, update relationship notes
  |
  v
7. state.on_interaction()
   -> drain energy, adjust social battery
  |
  v
8. evolution.check_triggers()
   -> propose mutations if thresholds met
```

Steps 1-6 are delegated to the `CognitiveProcessor` (which uses LLM or heuristics). Steps 7-8 are handled directly by the Soul class.

Non-significant interactions (step 3) still get fact extraction (step 4), entity extraction (step 5), and self-model updates (step 6). They just skip episodic storage. This means a mundane "hello" exchange can still teach the soul something if the user mentions a fact.

### `recall()` Flow

Called when the soul needs to retrieve relevant memories for a query.

```
Query string
  |
  v
1. Search across episodic + semantic + procedural stores
   -> collect candidate MemoryEntry objects
  |
  v
2. Score each candidate by ACT-R activation:
   -> base_level(access_timestamps)    [recency + frequency]
   -> spreading_activation(query)       [relevance]
   -> emotional_boost(somatic_marker)   [emotional intensity]
   -> gaussian_noise()                  [natural variability]
  |
  v
3. Sort by activation score (descending)
  |
  v
4. Update access_timestamps on returned entries
   (accessing a memory reinforces it)
  |
  v
5. Return top N entries
```

### `reflect()` Flow

Called periodically (every 10-20 interactions, or at session end) for memory consolidation.

```
Recent episodic entries (up to 20)
  |
  v
1. CognitiveProcessor.reflect(episodes, self_model)
   -> LLM identifies themes, summarizes, finds patterns
   -> Returns ReflectionResult {themes, summaries, emotional_patterns, self_insight}
  |
  v
2. [if apply=True] consolidate(result):
   -> summaries -> new semantic memories
   -> themes -> GeneralEvents (Conway hierarchy)
   -> self_insight -> self-model relationship notes
   -> emotional_patterns -> semantic memory
```

Returns `None` in heuristic mode. Genuine reflection requires an LLM to reason across episodes.

## Integration Patterns

### Direct SDK Integration

The most common pattern. Import `Soul`, call methods directly in your application loop.

```python
from soul_protocol import Soul, CognitiveEngine, Interaction

# Birth a soul (or awaken from file)
soul = await Soul.birth("Aria", archetype="The Companion", engine=my_engine)

# On each user-agent exchange:
await soul.observe(Interaction(
    user_input=user_message,
    agent_output=agent_response,
    channel="web",
))

# Generate system prompt for the next LLM call
prompt = soul.to_system_prompt()

# Recall relevant memories for context injection
memories = await soul.recall(user_message, limit=5)

# Persist periodically
await soul.save()
```

### MCP Server Integration

For MCP-compatible clients (Claude Desktop, Cursor, custom agents):

```bash
SOUL_PATH=aria.soul soul-mcp
```

The MCP server wraps the Soul API as 10 tools, 3 resources, and 2 prompts. See `docs/mcp-server.md` for full details.

### PocketPaw Integration

The `examples/pocketpaw_integration.py` file provides a `SoulProvider` class that bridges soul-protocol into PocketPaw's agent loop:

```python
from examples.pocketpaw_integration import SoulProvider

# From existing soul file
provider = await SoulProvider.from_file("~/.pocketpaw/souls/aria.soul")

# Generate soul-aware system prompt
prompt = await provider.get_system_prompt(user_query="Tell me about Python")

# Track interactions (auto-saves every 10 exchanges)
await provider.on_interaction(user_input, agent_output, channel="discord")

# Dashboard status
status = await provider.get_soul_status()
```

The `SoulProvider` has zero PocketPaw dependencies. It enriches the system prompt with recalled memories and state-aware annotations (e.g., a low-energy notice when the soul is tired).

## `.soul` File Format

The `.soul` file is a zip archive with this structure:

```
archive.soul (zip)
  manifest.json         -- Archive metadata (format version, soul ID, export time)
  soul.json             -- Full SoulConfig serialization
  dna.md                -- Human-readable personality blueprint
  state.json            -- Current SoulState snapshot
  memory/
    core.json           -- Core memory (persona + human)
    episodic.json       -- Episodic memories with somatic markers
    semantic.json       -- Extracted facts
    procedural.json     -- How-to knowledge
    graph.json          -- Knowledge graph (entities + relationships)
    self_model.json     -- Klein self-concept (domains + relationship notes)
    general_events.json -- Conway hierarchy (theme groupings)
```

All files are JSON. The `dna.md` is a bonus human-readable export for quick inspection without tooling.

## Known Limitations

1. **Token overlap is not semantic similarity.** The default `TokenOverlapStrategy` uses Jaccard similarity on whitespace-split tokens. "automobile" and "car" score zero overlap. Plug in a custom `SearchStrategy` with embeddings for semantic retrieval.

2. **Fact extraction is regex-based in heuristic mode.** The 10 built-in patterns cover names, preferences, locations, workplaces, and favorites. Anything outside these patterns requires an LLM (`CognitiveEngine`).

3. **Entity detection is limited.** Known tech terms are matched case-insensitively. Proper nouns are detected by capitalization heuristics. No NER model is used.

4. **Self-model has 6 fixed domains.** Custom domain discovery is not yet implemented. The 6 domains (technical_helper, creative_writer, knowledge_guide, problem_solver, creative_collaborator, emotional_companion) cover common AI assistant roles but are not extensible without code changes.

5. **Naive datetimes.** All timestamps use `datetime.now()` with no timezone awareness. If the soul migrates across timezones, activation decay calculations will be slightly off.

6. **Not thread-safe.** Concurrent `observe()` calls on the same Soul instance will cause data races. Use a single-writer pattern or external synchronization.

7. **GeneralEvent is a stub.** The Conway autobiography hierarchy stores themes and links episodes, but lifetime period grouping (the next level up) is deferred to a future version.

8. **No checksum verification on `.soul` archives.** The `manifest.json` has a `checksum` field but it is currently set to an empty string. Archive integrity is not validated on import.

## Version History

| Version | Key Features |
|---------|-------------|
| v0.1.0 | Core: birth, observe, save, export, DID, OCEAN personality, evolution system, 4-tier memory (core, episodic, semantic, procedural) |
| v0.2.0 | Psychology stack: somatic markers (Damasio), ACT-R activation scoring, LIDA significance gate, Klein self-model, knowledge graph, entity/fact extraction |
| v0.2.1 | CognitiveEngine protocol (single-method LLM interface), HeuristicEngine fallback, CognitiveProcessor orchestrator, LLM-driven reflect() |
| v0.2.2 | SearchStrategy protocol (pluggable retrieval), memory consolidation (reflect + apply), fact conflict resolution (supersede), GeneralEvent storage (Conway hierarchy) |
