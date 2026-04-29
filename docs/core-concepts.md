<!-- Covers: Soul lifecycle, .soul file format, Identity and DID, OCEAN personality, DNA, state management, memory architecture overview, evolution system, CognitiveEngine overview, SearchStrategy overview.
     Updated: 2026-04-14 — v0.3.1: Added "Org-Level Concepts" section covering the org journal,
     root agent, scope tags, decision traces, and Zero-Copy federation. Per-soul concepts unchanged.
     Updated: 2026-03-27 — v0.2.8: Fixed biorhythms table (removed social_battery state field,
     added all config fields with correct always-on defaults). Updated observe() drain text. -->

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
| `energy_regen_rate` | `float` | `0.0` | Energy recovered per hour of elapsed time |
| `energy_drain_rate` | `float` | `0.0` | Energy lost per interaction (0 = no drain) |
| `social_drain_rate` | `float` | `0.0` | Social battery lost per interaction (0 = no drain) |
| `tired_threshold` | `float` | `0.0` | Energy below this forces TIRED mood (0 = disabled) |
| `mood_inertia` | `float` | `0.4` | How quickly mood shifts (0 = max inertia, 1 = instant) |
| `mood_sensitivity` | `float` | `0.25` | Sentiment threshold to trigger a mood change |
| `auto_regen` | `bool` | `false` | Recover energy based on elapsed time between interactions |


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

**On interaction**: With default biorhythms (always-on), `observe()` does not drain energy. Drain is opt-in for companion souls via `energy_drain_rate` and `social_drain_rate`. If energy drops below `tired_threshold`, mood auto-shifts to `TIRED`.

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


## Identity Bundle Concepts (v0.4.0)

The 0.4.0 release adds three new top-level concepts to a single soul. None of these require the org layer; they all work on a standalone soul.

### Multi-User Soul

A soul can serve multiple users — a support agent answering 100 customers, a family assistant, a coding buddy that pairs with several teammates. Pass `user_id` to `observe()` and `recall()` to scope memory and bond strength per user.

```python
await soul.observe(interaction, user_id="alice")
await soul.observe(interaction, user_id="bob")

# Alice-scoped recall — sees alice's memories + legacy (None-attributed) entries
mems = await soul.recall("project", user_id="alice")

# Each user has their own bond
soul.bond_for("alice").bond_strength  # alice's bond
soul.bond_for("bob").bond_strength    # independent
```

Per-user bonds live in a `BondRegistry`; the default bond stays available for legacy single-user code.

### Memory Layers (open strings) + Domains

`MemoryType` is no longer a fixed enum at the spec layer. The runtime ships seven built-in layers — `core`, `episodic`, `semantic`, `procedural`, `graph`, `social`, plus any user-defined string. `manager.layer("custom_namespace").store(entry)` is valid.

Within a layer, `MemoryEntry.domain` is a sub-namespace defaulting to `"default"`. Use it to isolate context: `"finance"`, `"legal"`, `"personal"`. A `DomainIsolationMiddleware` wraps a soul and enforces a domain allow-list — reads silently filter, writes raise `DomainAccessError`. Use it to give a sub-agent a sandboxed view of the soul without handing them full access.

```python
finance_view = DomainIsolationMiddleware(soul, allowed_domains=["finance"])
await finance_view.remember("Q3 revenue $4.2M", domain="finance")  # ok
await finance_view.remember("Friend's birthday March 5", domain="personal")  # DomainAccessError
```

The new `social` layer is for relationship memory — bonds, trust signals, communication preferences per user.

### Trust Chain

Every memory write, supersede, forget, evolution proposal, evolution apply, learning event, and bond change appends a signed entry to the soul's trust chain. The chain is an Ed25519-signed Merkle-style hash chain — alter any past entry and every entry after it is invalid.

```python
ok, reason = soul.verify_chain()  # True or (False, "<reason> at seq N")
log = soul.audit_log()             # human-readable timeline
```

`Soul.export(include_keys=False)` (the new default) drops the private signing key from the archive. The recipient can verify the chain but cannot append new entries — the soul is shareable without giving away signing power. See [docs/trust-chain.md](trust-chain.md) for the full threat model.

### How they fit together

- **Multi-user** attributes memories to a `user_id`.
- **Layers + domains** organize memories into namespaces.
- **Trust chain** signs every consequential change so the soul's history is verifiable.

A soul can use any subset. Single-user souls in the default domain with no chain still work — every new field has a backward-compatible default.

---

## Org-Level Concepts (v0.3.1)

Everything above describes a single soul. A soul can live on its own forever — a personal assistant doesn't need an org. But when multiple agents and humans share context, audit history, and access boundaries, the **org layer** provides the container.

The per-soul concepts stay unchanged inside an org. What the org adds is a journal, a governance agent, a scope grammar, decision traces, and a way to reach external data without copying it into the boundary. The protocol-level contract lives in [Org Journal Spec](org-journal-spec.md); what follows is the conceptual overview.

### Org Journal

An append-only event log. One `EventEntry` per action, one monotonically-increasing `seq` across the whole org, an opportunistic sha256 hash-chain for tamper evidence. Backend: SQLite WAL, single file, atomic `seq` allocation inside `BEGIN IMMEDIATE`.

Everything that happens inside an org — a scope created, a soul invited, a proposal raised, a correction applied, a retrieval resolved — becomes one or more events in this journal. The journal is the source of truth. A wiped-and-restored org is reconstructable from its events alone.

Events carry:

- `action` — namespaced string, e.g. `org.created`, `scope.created`, `agent.proposed`, `retrieval.resolved`.
- `actor` — who did it: root, a user, or an agent.
- `payload` — structured, typed, validated against the spec.
- `causation_id` — optional pointer to the event that triggered this one. How decision traces are chained.

### Root Agent

The governance identity that sits above the org. One per org, born at `soul org init`, signs things but can't execute. Three-layer undeletability makes it structurally hard to remove by accident:

1. **Storage level** — file-system guard on `root.soul`.
2. **Protocol level** — the journal refuses events that would remove the root.
3. **CLI level** — `soul org destroy` requires two flags plus a typed confirmation.

The root's OCEAN is weighted toward conscientiousness and away from extraversion. It's designed to audit, not to chat.

### Scope Tags

Memories, events, and retrievals carry a **scope** — a colon-separated tag that locates them in the org hierarchy. The grammar is simple:

```
org:*
org:sales:*
org:sales:leads
agent:arrow-42
session:2026-04-14-a1b2
```

Scope matching is **bidirectional containment**: `org:sales:*` matches `org:sales:leads` and vice versa. The v0.3.0 strict helper (`match_scope_strict`) is preserved for callers who want one-way matching, but the default `match_scope` now does the obvious thing — a bundled archetype whose `default_scope` is `org:*` is visible to any agent installed from it without an extra config step.

Scope tags land on `MemoryEntry.scope`. Recalls filter on them automatically.

### Decision Traces

Three chained event types that capture the full cycle of an agent suggesting something and a human reacting:

1. `agent.proposed` — the agent emits a structured proposal with its alternatives, confidence, and the events it consulted.
2. `human.corrected` — the human edits, accepts, rejects, or defers. Linked back via `causation_id`.
3. `decision.graduated` — when a correction pattern recurs, it graduates into standing guidance the agent loads as memory.

This is the protocol-level answer to "where does the human-in-the-loop leave a receipt?" See [Decision Traces](decision-traces.md) for the full model.

### Zero-Copy Federation

External data (Drive docs, Salesforce records, Slack threads) doesn't belong inside the org boundary. Copying it creates staleness, duplication, and permission drift. Zero-copy federation handles this differently:

- A **`DataRef`** names a remote payload — source adapter id + opaque locator — without copying the data itself.
- The **`RetrievalRouter`** resolves a `DataRef` against registered `SourceAdapter`s at query time. Routes can be `first`, `parallel`, or `sequential`.
- The **`CredentialBroker`** scopes credentials per source and fails closed on denial, writing an audit event so every denied retrieval is traceable.
- The router emits a **`RetrievalTrace`** (also attached to `Soul.last_retrieval` on every `recall()`) that records the query, the candidate set, the rerank decisions, and the final selection. Only the trace crosses the org boundary; the source data stays where it lives.

The adapter contracts are in [Org Journal Spec](org-journal-spec.md). Concrete adapters for real systems live in each runtime's connector package, not in this repo — the protocol stays SDK-free.
