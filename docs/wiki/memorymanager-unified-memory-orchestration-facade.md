---
{
  "title": "MemoryManager — Unified Memory Orchestration Facade",
  "summary": "The `MemoryManager` is the top-level coordinator for all memory subsystems. It orchestrates the full observe pipeline — sentiment, attention gate, episodic storage, fact extraction, entity extraction, knowledge graph updates, contradiction detection, self-model updates — and exposes a unified recall interface.",
  "concepts": [
    "MemoryManager",
    "observe pipeline",
    "fact extraction",
    "entity extraction",
    "contradiction detection",
    "GDPR forget",
    "significance gate",
    "CognitiveEngine",
    "self-model",
    "knowledge graph update"
  ],
  "categories": [
    "memory",
    "orchestration",
    "soul-protocol-core"
  ],
  "source_docs": [
    "4b525cbaf45d5655"
  ],
  "backlinks": null,
  "word_count": 402,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Role in the Architecture

`MemoryManager` is the single class that higher-level soul code interacts with for memory operations. It owns instances of every memory store and processing module and sequences them through the observe and recall pipelines. It deliberately hides subsystem complexity behind a clean facade.

## observe() Pipeline

The pipeline runs on every interaction the soul receives:

```
1. detect_sentiment()          → SomaticMarker
2. compute_significance()      → SignificanceScore
3. Attention gate              → should store episodic?
   3a. If significant: add_with_psychology()
   3b. If low significance but contains facts: promote
4. reconcile_fact()            → extract + dedup semantic facts
   4c. ContradictionDetector   → mark superseded facts
   4d. Raw verb-fact scan      → catch location/employer changes
5. extract_entities()          → update KnowledgeGraph (if significant)
6. SelfModelManager.update()   → update self-model (if significant)
```

Steps 5 and 6 are skipped when significance is low (v0.4.0 optimization), saving two LLM calls per trivial interaction. The return dict always includes all keys with empty defaults for skipped steps.

## Fact Extraction

Heuristic `FACT_PATTERNS` — a list of `(regex, importance, template)` tuples — extract structured facts from raw user input. The v0.2.3 expansion added Q&A patterns (user questions, recommendations, advice, goals) beyond the original personal-attribute patterns.

## Entity Extraction

Two passes:
1. **First-person patterns** — `"I work at X"`, `"My name is Y"` → user-centric edges
2. **Third-person patterns** (`_THIRD_PERSON_RELATION_PATTERNS`) — `"Alice reports to Bob"` → entity-to-entity edges

A `_TOPIC_PATTERNS` pass (added 2026-03-26) catches natural-speech entity mentions that lack capitalized proper nouns or known tech terms — fixing the dead knowledge graph issue for conversational interactions.

## Contradiction Pipeline

Step 4c runs `ContradictionDetector.detect_heuristic()` against newly stored facts. Step 4d runs a raw-text scan against the full semantic store for verb-fact conflicts missed by `FACT_PATTERNS`. Both steps mark superseded entries rather than deleting them.

## GDPR forget() Methods

- `forget(query)` — cascade delete: episodic entries matching query + associated knowledge graph entities
- `forget_entity(name)` — remove entity from graph + related semantic memories
- `forget_before(cutoff)` — time-based bulk deletion with UTC audit trail

## set_engine() / DSPy Integration

`set_engine()` allows hot-swapping the `CognitiveEngine` at runtime without re-initializing `MemoryManager`. Used by `MCPSamplingEngine` to inject the engine lazily on the first MCP tool call.

## Known Gaps

- TODO #51: Deletion audit entries are written to an in-memory list — they are not persisted to the soul file between sessions.
- PII scrubbing in logs is manual (logging word counts, not content) — no automated PII detection layer.