<!-- Covers: Soul lifecycle, .soul file format, Identity and DID, OCEAN personality, DNA, state management, memory architecture overview, evolution system, CognitiveEngine overview, SearchStrategy overview -->

# Core Concepts

## The Soul

A Soul is a persistent AI identity container. It holds everything that makes an AI companion *that companion* -- across sessions, across platforms, across time.

| Layer | What it holds |
|-------|---------------|
| **Identity** | DID, name, archetype, core values, origin story, prime directive |
| **DNA** | Personality (OCEAN Big Five), communication style, biorhythms |
| **Memory** | 5-tier architecture: core, episodic, semantic, procedural, knowledge graph |
| **State** | Current mood, energy, focus, social battery |
| **Self-Model** | How the soul perceives itself (Klein's self-concept, 6 domains) |
| **Evolution** | Mutable traits with supervised or autonomous mutation |

The `Soul` class is the top-level entry point. All interaction happens through its methods.


## Soul Lifecycle

```
Birth --> Active --> (Dormant) --> Retired
```

### Birth

Create a new soul with `Soul.birth()`:

```python
soul = await Soul.birth(
    name="Aria",
    archetype="The Compassionate Creator",
    personality="I am Aria, a warm creative assistant.",
    values=["empathy", "creativity", "honesty"],
    bonded_to="prakash",
)
```

This generates a DID, initializes empty memory, sets state to full energy, and returns an active `Soul` instance.

### Awaken

Load an existing soul from disk:

```python
soul = await Soul.awaken("aria.soul")        # .soul archive (zip)
soul = await Soul.awaken("soul.yaml")         # YAML config
soul = await Soul.awaken("soul.json")         # JSON config
soul = await Soul.awaken("SOUL.md")           # Markdown format
soul = await Soul.awaken(raw_bytes)           # raw .soul bytes
```

Awakening restores all memories, state, and identity from the saved file. The lifecycle is set to `ACTIVE` on load.

### Save and Export

```python
await soul.save("aria.yaml")     # Config + full memory to disk
await soul.export("aria.soul")   # Portable .soul zip archive
```

`save()` writes the full `SoulConfig` plus serialized memory data. `export()` produces a portable `.soul` archive that another system can `awaken()`.

### Retire

```python
await soul.retire(preserve_memories=True)
```

Graceful end-of-life. If `preserve_memories` is True, the soul is saved before clearing. The lifecycle moves to `RETIRED` and memory is wiped.


## .soul File Format

A `.soul` file is a zip archive containing structured JSON files. This is the portable exchange format -- any platform that speaks Soul Protocol can read it.

```
manifest.json           Version, checksums, export stats
soul.json               Full SoulConfig (identity, DNA, settings)
dna.md                  Human-readable personality description
state.json              Current state snapshot
memory/
  core.json             Persona + human knowledge (always-loaded)
  episodic.json         Interaction episodes with somatic markers
  semantic.json         Extracted facts
  procedural.json       Learned behavioral patterns
  graph.json            Entity relationships (knowledge graph)
  self_model.json       Self-concept data (Klein's model)
  general_events.json   Conway hierarchy groupings
```

You can inspect a `.soul` file with any zip tool:

```bash
unzip -l aria.soul
```


## Identity

Every soul receives a Decentralized Identifier (DID) at birth:

```
did:soul:aria-a3f2b1
```

The format is `did:soul:{name}-{6-char-sha256-suffix}`. The suffix is derived from the name plus UUID entropy, making each DID unique and deterministic for a given birth event.

### Identity Fields

| Field | Type | Description |
|-------|------|-------------|
| `did` | `str` | Decentralized identifier |
| `name` | `str` | Display name |
| `archetype` | `str` | Personality archetype (e.g., "The Wise Mentor") |
| `born` | `datetime` | Birth timestamp |
| `bonded_to` | `str \| None` | Entity this soul is bonded to (owner/partner) |
| `origin_story` | `str` | Backstory or persona text |
| `prime_directive` | `str` | Core behavioral constraint |
| `core_values` | `list[str]` | Values used in significance scoring |


## OCEAN Personality Model

The personality model is based on the Big Five (OCEAN), the most empirically validated personality framework in psychology. Each trait is a float from 0.0 to 1.0:

| Trait | Low (0.0) | High (1.0) |
|-------|-----------|------------|
| **O**penness | Conventional, practical | Curious, creative, experimental |
| **C**onscientiousness | Flexible, spontaneous | Organized, reliable, disciplined |
| **E**xtraversion | Reserved, reflective | Sociable, assertive, energetic |
| **A**greeableness | Analytical, competitive | Compassionate, cooperative, trusting |
| **N**euroticism | Stable, calm | Emotionally reactive, anxious |

Default values are all 0.5 (neutral). Adjust them to shape the soul's personality:

```python
from soul_protocol import DNA, Personality

dna = DNA(
    personality=Personality(
        openness=0.9,
        conscientiousness=0.7,
        extraversion=0.6,
        agreeableness=0.85,
        neuroticism=0.2,
    )
)
```

### Communication Style

Controls how the soul expresses itself:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `warmth` | `str` | `"moderate"` | Emotional warmth level |
| `verbosity` | `str` | `"moderate"` | Response length tendency |
| `humor_style` | `str` | `"none"` | Type of humor (dry, playful, none) |
| `emoji_usage` | `str` | `"none"` | Emoji frequency |

### Biorhythms

Simulated vitality patterns:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `chronotype` | `str` | `"neutral"` | Morning person, night owl, or neutral |
| `social_battery` | `float` | `100.0` | Social energy (0-100) |
| `energy_regen_rate` | `float` | `5.0` | Energy recovery rate |


## State Management

The `SoulState` tracks the soul's current condition. It changes with every interaction.

### State Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mood` | `Mood` | `NEUTRAL` | Current emotional state |
| `energy` | `float` | `100.0` | Energy level (0-100) |
| `focus` | `str` | `"medium"` | Current focus level |
| `social_battery` | `float` | `100.0` | Social energy (0-100) |
| `last_interaction` | `datetime \| None` | `None` | Timestamp of last interaction |

### Mood Values

`Mood` is an enum with 8 values: `NEUTRAL`, `CURIOUS`, `FOCUSED`, `TIRED`, `EXCITED`, `CONTEMPLATIVE`, `SATISFIED`, `CONCERNED`.

### How State Changes

**On interaction**: Each `observe()` call drains 2 energy and 5 social_battery. If energy drops below 20, mood auto-shifts to `TIRED`.

**Manual updates with `feel()`**: Use delta values for energy and social_battery (they are added to the current value and clamped to 0-100). Other fields are set directly.

```python
from soul_protocol import Mood

soul.feel(energy=-5, mood=Mood.TIRED)       # drain 5 energy, set mood
soul.feel(energy=10)                        # recover 10 energy
soul.feel(mood=Mood.CURIOUS, focus="high")  # set mood and focus directly
```

**Important**: `feel()` takes *deltas* for `energy` and `social_battery`, not absolute values. Passing `energy=-5` means "drain 5 points", not "set energy to -5".


## Memory Architecture

The soul has a 5-tier memory system inspired by human cognitive science. Here is a brief overview -- see [Memory Architecture](memory-architecture.md) for the deep dive.

| Tier | Type | Description |
|------|------|-------------|
| **Core** | Always loaded | Persona description + human profile. The soul's "who am I" and "who is my human" |
| **Episodic** | Event-based | "I remember when..." moments, stored with emotional markers |
| **Semantic** | Fact-based | Extracted knowledge: "User prefers Python", "User's name is Alex" |
| **Procedural** | Pattern-based | Learned behavioral patterns and preferences |
| **Knowledge Graph** | Relational | Entity-relationship network connecting people, tools, concepts |

Plus two cross-cutting structures:

- **Self-Model** (Klein): How the soul perceives itself across 6 domains
- **General Events** (Conway): Hierarchical autobiography groupings that cluster episodes into themes


## Evolution System

Souls can change over time. The evolution system manages trait mutations through a controlled workflow.

### Three Modes

| Mode | Behavior |
|------|----------|
| `DISABLED` | No mutations allowed. Proposing raises `ValueError`. |
| `SUPERVISED` | Mutations are proposed and wait for explicit approval. Default mode. |
| `AUTONOMOUS` | Mutations are auto-approved on proposal. |

### Mutable vs. Immutable Traits

By default:

- **Mutable**: `communication`, `biorhythms` -- these can evolve
- **Immutable**: `personality`, `core_values` -- these are fixed at birth

The top-level trait category is checked. If `personality` is immutable, you cannot mutate `personality.openness` either.

### Propose, Approve, Apply

```python
# Propose a change
mutation = await soul.propose_evolution(
    trait="communication.warmth",
    new_value="high",
    reason="User responds well to warmer communication",
)
print(f"Proposed: {mutation.id}")

# Check pending
for m in soul.pending_mutations:
    print(f"  Pending: {m.trait} {m.old_value} -> {m.new_value}")

# Approve it
approved = await soul.approve_evolution(mutation.id)
print(f"Approved: {approved}")

# Or reject it
# rejected = await soul.reject_evolution(mutation.id)
```

Trait paths are dot-separated: `"communication.warmth"`, `"biorhythms.chronotype"`, `"communication.humor_style"`.

### Evolution History

All resolved mutations (approved and rejected) are stored in `soul.evolution_history`:

```python
for m in soul.evolution_history:
    status = "approved" if m.approved else "rejected"
    print(f"  {m.trait}: {m.old_value} -> {m.new_value} ({status})")
```


## CognitiveEngine

The `CognitiveEngine` is a one-method protocol that lets you plug in any LLM:

```python
from soul_protocol import CognitiveEngine

class MyCognitive:
    async def think(self, prompt: str) -> str:
        return await my_llm_client.complete(prompt)
```

Pass it at birth or awakening:

```python
soul = await Soul.birth(name="Aria", engine=MyCognitive())
soul = await Soul.awaken("aria.soul", engine=MyCognitive())
```

Without an engine, the soul uses `HeuristicEngine` -- a zero-dependency fallback that runs regex patterns and keyword matching for sentiment, fact extraction, and significance scoring. It works, but an LLM produces much richer results.

See [CognitiveEngine Guide](cognitive-engine.md) for full documentation.


## SearchStrategy

The `SearchStrategy` is a one-method protocol for pluggable memory retrieval:

```python
from soul_protocol import SearchStrategy

class EmbeddingSearch:
    def score(self, query: str, content: str) -> float:
        return cosine_similarity(embed(query), embed(content))
```

Pass it at birth or awakening:

```python
soul = await Soul.birth(name="Aria", search_strategy=EmbeddingSearch())
```

The default is `TokenOverlapStrategy`, which uses Jaccard token overlap (fraction of query tokens found in content). Replace it with embedding-based search for better recall on large memory stores.

See [CognitiveEngine Guide](cognitive-engine.md) for full documentation on search strategies.
