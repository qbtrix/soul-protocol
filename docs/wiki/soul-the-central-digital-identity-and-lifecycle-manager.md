---
{
  "title": "Soul: The Central Digital Identity and Lifecycle Manager",
  "summary": "The Soul class is the top-level API object in Soul Protocol — it unifies identity, memory, personality, skills, evolution, dreaming, bonding, and eternal storage into a single coherent interface. It is the primary object that consuming applications instantiate and interact with.",
  "concepts": [
    "Soul",
    "digital soul",
    "soul lifecycle",
    "observe",
    "recall",
    "smart recall",
    "dream",
    "evolution",
    "eternal storage",
    "GDPR",
    "birth",
    "awaken",
    "DID",
    "memory management",
    "skill XP"
  ],
  "categories": [
    "soul-lifecycle",
    "identity",
    "memory",
    "architecture"
  ],
  "source_docs": [
    "d627a071ff7f5076"
  ],
  "backlinks": null,
  "word_count": 478,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## What Is a Soul?

A `Soul` instance represents a persistent AI companion identity. It holds everything that makes a companion coherent across sessions and platforms: a DID-based identity, OCEAN personality traits, five tiers of memory, a self-model, skill progression, and an evolution history. The class is the integration point where all subsystems meet.

## Birth vs. Awaken

Two construction paths exist:

**`Soul.birth()`** — creates a new soul from scratch:
```python
soul = await Soul.birth(
    name="Luna",
    archetype="creative_companion",
    personality=Personality(openness=0.8, ...),
    engine=cognitive_engine
)
```

**`Soul.awaken(source)`** — restores a soul from a `.soul` archive:
```python
soul = await Soul.awaken("path/to/companion.soul", engine=engine)
```

The separation enforces the semantic distinction between creating a new identity and restoring an existing one. `awaken()` handles decryption, format migration, and subsystem rewiring.

## Observe → Remember → Recall Loop

The core interaction loop:

1. **`observe(interaction)`** — processes a user interaction, extracts facts into semantic memory, records the episode, updates the self-model, grants skill XP, and triggers consolidation every `N` interactions.
2. **`remember(content, type=...)`** — explicit memory addition, used when the application wants to stamp specific knowledge (e.g., onboarding facts).
3. **`recall(query)`** / **`smart_recall(query)`** — retrieve relevant memories. `smart_recall()` adds an LLM reranking pass via `rerank.py`, off by default to protect high-frequency callers from unbounded token cost.

## Smart Recall and Traceability

```python
async def smart_recall(self, query, *, limit, candidate_pool, enabled) -> list[MemoryEntry]:
    ...
    self._last_retrieval = RetrievalTrace(source="soul.smart", ...)
```

`_last_retrieval` is overwritten by `smart_recall()` to reflect the final reranked set rather than the pre-rerank pool. Callers can inspect `soul.last_retrieval` to understand why specific memories were returned.

## Dream: Offline Consolidation

```python
async def dream(self, *, since, archive, detect_patterns, consolidate_graph,
                synthesize, dry_run) -> DreamReport:
```

`dream()` runs the `Dreamer` engine for offline batch consolidation: detecting topic clusters, promoting recurring procedures, identifying behavioral trends, consolidating the knowledge graph, and synthesizing cross-tier insights (e.g., episodic patterns → procedural memories). The `dry_run` flag lets operators preview what would be consolidated without committing changes.

## Eternal Storage

`archive()` and the `eternal=` parameter on `birth()`/`awaken()` connect to the `EternalManager` for Arweave/IPFS-backed persistent storage. Eternal storage is opt-in because it requires external infrastructure.

## GDPR and Deletion

`forget_by_id()`, `forget()`, `forget_entity()`, and `forget_before()` provide a comprehensive forgetting API. All deletions are recorded in `deletion_audit()` to satisfy GDPR's right-to-erasure record-keeping requirements.

## Evolution

```python
async def propose_evolution(self, trait, new_value, reason) -> Mutation:
async def approve_evolution(self, mutation_id) -> bool:
async def reject_evolution(self, mutation_id) -> bool:
```

Personality changes go through a proposal-approval cycle. No trait can change silently — the captain (or the soul's bonded user) must explicitly approve mutations. This prevents runaway drift from a single unusual interaction.

## Known Gaps

- `_resolve_actor()` is a best-effort helper that may return a generic fallback ID when no engine is available, weakening audit trail attribution.
- `reincarnate()` (creating a new soul that carries memories from a retiring soul) is present but has minimal documentation on what is preserved vs. reset.
