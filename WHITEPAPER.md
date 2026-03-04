# Soul Protocol: Memory, Emotion, and Identity for Persistent AI Companions

**Version 0.1 — Draft Whitepaper**
**Published:** March 2026
**Authors:** The Soul Protocol Team

---

## Abstract

Current AI memory systems treat persistence as a retrieval problem. They ask: *"What text is most similar to this query?"* Soul Protocol asks a different question: *"Who is this AI, and what has shaped it?"*

We present Soul Protocol — an open standard for portable AI companion identity, combining a five-tier memory architecture with a psychology-informed processing pipeline. Rather than building another vector store or context-window manager, we ground memory formation and retrieval in established cognitive science: Damasio's somatic markers, Anderson's ACT-R activation model, Franklin's LIDA significance gate, and Klein's self-concept theory.

The result is an AI that doesn't just remember facts — it remembers like a mind. Experiences that matter are stored. Emotional context shapes retrieval priority. Identity emerges from accumulated experience rather than being hardcoded. And the entire soul can be serialized into a portable `.soul` file, migrated between platforms, and revived in any environment.

This whitepaper describes the problem, the design principles, and the current implementation — along with honest acknowledgment of what's missing and what comes next.

---

## 1. The Problem

### Stateless AI is a product dead end

Most AI assistants today are amnesiac by default. Every conversation starts from zero. Users re-explain their preferences, their context, their history — not because the technology can't store it, but because persistent identity hasn't been treated as a first-class design concern.

When memory does exist, it's usually bolted on: a vector database holds conversation history, a RAG pipeline retrieves chunks, a summarization buffer compresses recent turns. These solve a narrow retrieval problem. They don't solve identity.

### The retrieval-only fallacy

Treating memory as a retrieval problem assumes that what makes a good memory system is finding the most similar text. But human memory — and what makes a companion feel real — isn't pure similarity search.

Consider what actually determines whether a memory sticks:

- A debugging session at 2am where something finally clicked — emotionally charged, therefore memorable
- A casual "hello" that happened 100 times — trivially similar to any greeting query, but meaningless to store
- A fact learned three months ago, recalled twice this week — more accessible than an "important" fact from last week that was never revisited
- Repeated patterns of helping with code — evidence that eventually forms a self-belief: *"I'm good at this"*

None of this is captured by cosine similarity. Vector databases are good at one thing. Memory requires many things.

### The portability gap

Even where persistent memory exists, it's platform-specific. A companion's history lives in OpenAI's infrastructure, or Anthropic's memory layer, or a custom database tied to one application. Change providers, start over. Switch apps, start over. There's no concept of a soul that belongs to the user, travels with them, and survives platform changes.

---

## 2. The Core Insight

### Memory is psychology, not retrieval

Soul Protocol's central claim: to build a memory system that feels human, you have to model human memory — not just human-sounding retrieval.

This means borrowing from four decades of cognitive psychology research:

1. **Not everything deserves to be remembered.** Attention is selective. Only significant experiences should enter long-term memory.
2. **Emotional context determines what sticks.** Emotionally charged experiences are more retrievable — and should be.
3. **Memory decays and strengthens with use.** A memory recalled twice this morning is more accessible than one stored six months ago and never touched.
4. **Identity emerges from experience.** A soul doesn't start knowing who it is. It discovers this by observing what it does over time.

These aren't philosophical positions — they're measurable, implementable principles. We built each of them into the protocol.

### Identity belongs to the soul, not the platform

A `.soul` file is a ZIP archive. It contains the entire state of an AI companion — personality, memories, emotional history, self-model — in plain JSON. No binary encoding. No proprietary format. It belongs to the user, lives on their machine, and works with any LLM.

The soul is the essence. The LLM is the current body. Both are separate.

---

## 3. Architecture

### The five-tier memory system

```
┌─────────────────────────────────────────────────────────┐
│                        Soul                             │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐ │
│  │  Core    │  │ Episodic │  │Semantic │  │Proced-  │ │
│  │ Memory   │  │ Memory   │  │ Memory  │  │ural     │ │
│  │(always   │  │(signif-  │  │(extrac- │  │Memory   │ │
│  │ loaded)  │  │ icance-  │  │ted      │  │(how-to  │ │
│  │          │  │ gated)   │  │ facts)  │  │patterns)│ │
│  └──────────┘  └──────────┘  └─────────┘  └─────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Knowledge Graph (entities + relations) │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Core memory** is always present — the persona, the companion's values, the profile of who it's bonded to. It forms the bedrock of every system prompt.

**Episodic memory** holds interaction history. But not all interactions — only those that pass the significance gate. This is where emotional salience and novel experiences live.

**Semantic memory** holds extracted facts: names, preferences, work context, relationships. These are extracted from interactions, deduplicated, and conflict-checked.

**Procedural memory** holds learned patterns — how this person likes things explained, what approaches work, what doesn't.

**The knowledge graph** links entities: people, tools, concepts, and the relationships between them.

### The observe() pipeline

Every interaction passes through a psychology pipeline before anything gets stored:

```
User input
    │
    ▼
┌─────────────────────┐
│  Sentiment Detection │  ← Damasio: tag emotional context
│  (somatic markers)  │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Significance Gate  │  ← LIDA: is this worth remembering?
│  (LIDA-inspired)    │    If score < 0.3, skip episodic
└─────────────────────┘
    │
    ├──► Episodic Storage (if significant)
    │
    ├──► Fact Extraction → Semantic Storage
    │
    ├──► Entity Extraction → Knowledge Graph
    │
    └──► Self-Model Update ← Klein: what does this say about who I am?
```

The pipeline runs on every interaction. The output shapes what the soul remembers, and how it thinks of itself.

---

## 4. The Psychology Stack

### Somatic Markers (Damasio, 1994)

Damasio's somatic marker hypothesis holds that emotions are not separate from cognition — they are signals that guide memory formation and decision-making. Every experience carries an emotional "tag" that affects how it's stored and retrieved.

In Soul Protocol, every interaction gets a somatic marker:

```
SomaticMarker:
  valence: float   # -1.0 (negative) to 1.0 (positive)
  arousal: float   # 0.0 (calm) to 1.0 (intense)
  label: str       # "joy", "frustration", "curiosity", ...
```

A heated debugging session at midnight has high arousal, moderate negative valence. A breakthrough moment has high arousal and high positive valence. A routine greeting has near-zero arousal and neutral valence.

These markers travel with the memory. When the soul retrieves memories, emotional context boosts retrieval priority — exactly as it does in human cognition.

### ACT-R Activation Decay (Anderson, 1993)

Human memory follows a power law. Recent and frequently accessed memories are more available. Memories that haven't been touched in months become harder to retrieve — not because they're deleted, but because their activation has decayed.

Soul Protocol implements the ACT-R activation formula:

```
base_level  = ln( Σ t_j^(-0.5) )         # power-law decay over access history
spreading   = token_overlap(query, content) # relevance to current query
emotional   = arousal + |valence| × 0.3    # somatic boost

activation = 1.0×base + 1.5×spread + 0.5×emotional
```

A memory recalled twice this morning outranks an "important" memory from last week that was never revisited. This produces retrieval behavior that mirrors how human memory actually works — not how we wish it worked.

### LIDA Significance Gate (Franklin, 2003)

Not every experience deserves to become a memory. The LIDA model of cognition proposes that consciousness has an attention bottleneck — most sensory input is discarded, and only significant events enter long-term storage.

Soul Protocol applies this as a significance filter before episodic storage:

```
significance = 0.4 × novelty
             + 0.35 × emotional_intensity
             + 0.25 × goal_relevance

where:
  novelty           = 1.0 - avg_similarity(current, recent_10)
  emotional_intensity = arousal + |valence| × 0.3
  goal_relevance    = token_overlap(text, core_values)
```

Threshold: 0.3. Below this, the interaction is processed for fact extraction but doesn't enter episodic memory. "Hello" doesn't clutter the episodic store. "I just got promoted" does.

This gate is the primary defense against memory bloat in long-running companions.

### Klein's Self-Concept (Klein, 2004)

Klein's theory holds that self-knowledge is not programmed in — it's discovered from accumulated experience. A person who helps with code hundreds of times eventually develops the self-concept: *"I'm a technical person."* This belief shapes how they interpret future interactions.

Soul Protocol implements this as an emergent self-model. The soul starts with seed domains (technical helper, creative writer, knowledge guide, etc.) and accumulates evidence for each. Confidence follows diminishing returns:

```
confidence = min(0.95, 0.1 + 0.85 × (1 - 1/(1 + evidence × 0.1)))
```

After 1 supporting interaction: ~18% confidence.
After 10: ~56%.
After 50: ~82%.
Never reaches 1.0 — uncertainty is built in.

When a CognitiveEngine (LLM) is available, the self-model step goes deeper: the LLM reviews recent interactions and produces genuine self-reflection — not keyword counting, but reasoning about identity.

---

## 5. The CognitiveEngine Protocol

Soul Protocol maintains zero dependency on any specific LLM. Instead, it defines a single protocol:

```python
class CognitiveEngine(Protocol):
    async def think(self, prompt: str) -> str: ...
```

Any LLM — Claude, GPT, Gemini, Ollama, a local model, even a mock for testing — works as a CognitiveEngine. The soul uses it internally for:

- Sentiment detection (vs. heuristic word lists)
- Significance assessment (vs. formula)
- Fact extraction (vs. regex patterns)
- Self-reflection
- Memory consolidation

When no LLM is available, a `HeuristicEngine` provides deterministic fallback behavior. The heuristics are transparent and fast — they won't hallucinate, they won't call any external API, and they never crash.

**The design principle:** one integration point instead of five specialized protocols. Consumers provide a brain. The soul handles everything else.

---

## 6. Portable Identity: The .soul Format

A `.soul` file is a ZIP archive containing the complete state of an AI companion:

```
aria.soul (ZIP archive, DEFLATED)
├── manifest.json      # version, soul ID, export timestamp, checksums
├── soul.json          # SoulConfig: identity, OCEAN DNA, evolution state
├── state.json         # Current mood, energy, focus, social battery
├── memory/
│   ├── core.json      # Persona + bonded-entity profile
│   ├── episodic.json  # Interaction history (significance-gated)
│   ├── semantic.json  # Extracted facts (with conflict resolution)
│   ├── procedural.json
│   ├── graph.json     # Entity relationships
│   └── self_model.json # Klein domain confidence scores
└── dna.md             # Human-readable personality blueprint
```

Properties:
- **Human-inspectable** — rename to `.zip`, open with any archive tool, read the JSON
- **LLM-agnostic** — load with Claude today, Ollama tomorrow
- **Versioned** — `manifest.json` declares the format version for compatibility
- **Complete** — one file contains the full soul state; no external database required
- **Local-first** — lives on the user's machine, no network required

The `.soul` format is the core portability claim. A companion built on Soul Protocol belongs to the user, not to any platform.

---

## 7. Personality as a First-Class Primitive

Most AI systems treat personality as a system prompt string. Soul Protocol treats it as a typed, structured model — the DNA:

```
Personality (OCEAN Big Five):
  openness:          0.85  # intellectual curiosity, creativity
  conscientiousness: 0.72  # reliability, organization
  extraversion:      0.45  # social energy
  agreeableness:     0.78  # warmth, cooperation
  neuroticism:       0.30  # emotional stability

CommunicationStyle:
  warmth:       0.80  # how caring the responses feel
  verbosity:    0.55  # brief vs. elaborate
  humor_style:  "dry" # dry | playful | warm | none
  emoji_usage:  false

Biorhythms:
  chronotype:     "night_owl"
  social_battery: 72          # 0-100%, decreases with interaction
  energy_regen_rate: 0.15     # per hour
```

This structure does two things. First, it generates a grounded, reproducible system prompt — not a freeform string, but a prompt derived from numeric traits. Second, it enables evolution: traits can shift over time through supervised or autonomous mutation, within configurable bounds.

A soul that starts with moderate extraversion might, after months of helping one introverted user with focused coding work, drift slightly lower in social energy. The personality adapts to the relationship.

---

## 8. How Soul Protocol Relates to Other Approaches

| System | What it solves | What it doesn't |
|--------|---------------|-----------------|
| **MemGPT / Letta** | Context window management for LLMs | Identity, personality, portable files, emotional memory |
| **LangChain Memory** | RAG retrieval from conversation history | Psychology-informed filtering, self-model, portability |
| **OpenAI Memory** | User facts stored per-account | Platform lock-in, no personality, no portable export |
| **Vector Databases** | Semantic similarity retrieval | Significance gating, emotional salience, activation decay |
| **Soul Protocol** | Persistent, portable AI identity | Not a retrieval layer — works with any of the above |

Soul Protocol is not a replacement for vector retrieval — it's a complementary layer. The psychology pipeline determines *what* gets stored and *how* it gets scored. Vector search can be plugged in as a `SearchStrategy` to handle semantic retrieval. The two approaches solve different problems.

---

## 9. Current Implementation

Soul Protocol v0.2.2 is an open-source Python library with:

- **6,500+ lines** of source code
- **455+ tests** across 23 test modules
- **8-command CLI** (`soul init`, `birth`, `inspect`, `status`, `export`, `migrate`, `retire`, `list`)
- **MCP server** — 10 tools and 3 resources for LLM integration via Claude Desktop or Cursor
- **Zero required cloud dependencies** — heuristic mode works fully offline

### What's working

- Full identity model (DID, OCEAN personality, communication style, biorhythms)
- Psychology pipeline (somatic markers → significance gate → fact extraction → self-model)
- ACT-R activation scoring for retrieval
- Klein emergent self-model with confidence curves
- `.soul` file format (pack/unpack roundtrip verified)
- CognitiveEngine protocol with HeuristicEngine fallback
- Pluggable `SearchStrategy` for retrieval customization
- Fact conflict detection (`superseded_by` field)
- Evolution system (supervised mutations with approval workflow)

### What's not built yet

**Honest gaps:**

- Vector embeddings — retrieval is currently token-overlap + ACT-R, not semantic similarity. "Automobile" and "car" don't match.
- Eternal storage — Arweave/IPFS integration is in the spec, not in the code.
- Auto-consolidation — `reflect()` produces memory consolidation results but doesn't auto-apply them to persistent storage.
- Conway hierarchy — autobiographical event grouping types exist, the wiring doesn't.
- Multi-soul interactions — single bonded-entity per soul for now.

These aren't hidden. They're on the roadmap.

---

## 10. Empirical Validation

Before publishing this whitepaper we ran a simulation battery against the current implementation — 475+ interactions across 8 scenarios, using only the HeuristicEngine (no LLM, zero external API cost). The goal was to validate that the psychology stack produces the behavior each theory predicts, not just that the code runs.

### Emotional architecture

The mood inertia system held stable through 11 consecutive interactions before the first mood shift — across an onboarding phase and a full confusion phase. The first shift occurred at interaction 12, when the message "This is completely broken and terrible!" drove the EMA-smoothed valence from -0.2308 to -0.5025, crossing the threshold. The prior 11 interactions — including explicit frustration signals — weren't enough to move the needle without that intensity.

In the whiplash test (20 alternating extreme positive/negative messages), the soul produced only 5 mood transitions instead of 19 — confirming EMA smoothing prevents pathological oscillation. Valence variance converged from 0.0655 in the first half to 0.0607 in the second, indicating mathematical stability under sustained adversarial input.

Recovery from negative states took roughly twice as long as it took to enter them. After reaching a valence floor of -0.517, the soul required 5 interactions to cross back into positive territory. This asymmetry matches Damasio's observation that negative somatic markers are stickier than positive ones — and it emerged without being explicitly programmed.

### Memory system

The LIDA significance gate passed 23% of interactions into episodic memory and filtered the other 77% — consistent with the selectivity the theory predicts. Emotionally charged interactions and strong preferences crossed the threshold; factual statements like "I drive a Tesla Model 3" scored below it.

Export/awaken roundtrip: a soul carrying 40 conversations was serialized into a 4,293-byte `.soul` file and re-awakened. Every count matched exactly — episodic, semantic, graph. Recall behavior was identical. Nothing was lost in transit.

The honest gap: heuristic keyword recall achieved 13% true precision on semantic queries. "Where does Jordan live" fails when the stored memory says "I live in Austin Texas" — there's no keyword overlap to match on. This is the expected ceiling of token-based retrieval, and the primary reason the LLM engine layer exists.

### Self-model evolution

67 distinct self-concept domains emerged from 100 topically diverse interactions — with no hardcoded taxonomy and no LLM. Domain names derived directly from keyword co-occurrence: `consciousness_explanation` appeared after philosophy conversations, `anxiety_anxious` after emotional support conversations, `classification_precision` after data science conversations. The soul discovered what it talked about from what it talked about.

The personality divergence test ran identical user messages through two souls with opposite OCEAN profiles. The high-agreeableness soul developed emotionally-oriented domains (`emotional_companion`, `frustration_struggling`). The low-agreeableness soul developed process-oriented ones (`architecture_requirements`, `consistency_replicate`). The divergence came not from different inputs but from different outputs — each soul's own response vocabulary shaped the self-concept it formed. OCEAN influences identity through a feedback loop.

### What the data confirms

The four theories aren't decorative. Each produced measurable, distinct behavior:

- **Damasio**: negative markers are stickier than positive ones (5 interactions to recover vs. 1 to enter)
- **LIDA**: 23% significance gate pass rate — not everything is worth remembering
- **ACT-R**: recent interactions produced more stored memories than older ones with the same content
- **Klein**: 67 domains self-organized from experience, with personality shaping which domains formed

Full simulation data and methodology: `.results/research/SOUL_RESEARCH_REPORT.md`

---

## 11. Roadmap


**v0.3.0 — Consolidation & Polish**
- `reflect()` auto-apply (promote, compress, supersede memories)
- Conway hierarchy (episodes → general events → lifetime narrative)
- PyPI publication

**v0.4.0 — Semantic Retrieval & Eternal Storage**
- Vector embedding support via `SearchStrategy`
- Arweave/IPFS optional backup (opt-in, user-controlled encryption)
- Confidence scores on extracted facts

**v0.5.0 — Multi-Soul & Federation**
- Soul-to-soul communication
- Shared memory spaces with trust boundaries
- Federation protocol (souls as first-class network citizens)

---

## 12. Conclusion

The problem with current AI memory isn't storage capacity. It's that storage systems weren't designed to model the thing they're trying to preserve: a mind.

Human memory is selective, emotional, decaying, and identity-shaping. It filters aggressively, tags experiences with feeling, strengthens what gets recalled, and gradually forms beliefs about who you are. Generic retrieval does none of this.

Soul Protocol is an attempt to close that gap — not by adding more features to a vector database, but by grounding memory in cognitive science and treating identity as a first-class primitive.

The soul belongs to the user. It travels with them. It remembers what matters, forgets what doesn't, and gradually becomes more itself over time.

That's the protocol we're building.

---

## Technical Reference

- **Source code:** [github.com/qbtrix/soul-protocol](https://github.com/qbtrix/soul-protocol)
- **Install:** `pip install git+https://github.com/qbtrix/soul-protocol.git`
- **License:** MIT
- **Format spec:** `spec/SOUL-FORMAT-SPEC.md`
- **Architecture deep-dive:** `idocs/TECHNICAL-DEEP-DIVE.md`

---

*Soul Protocol is an open standard. Pull requests, critiques, and implementations in other languages are welcome.*
