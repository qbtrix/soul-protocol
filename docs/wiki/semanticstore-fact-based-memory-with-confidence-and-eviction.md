---
{
  "title": "SemanticStore: Fact-Based Memory with Confidence and Eviction",
  "summary": "Stores semantic memories — extracted facts and general knowledge about the world and the user — with importance scoring, confidence tracking, supersession logic for updated facts, and a bounded capacity that evicts least-important entries when full. GDPR deletion APIs are provided for targeted and time-based removal.",
  "concepts": [
    "semantic memory",
    "fact storage",
    "memory eviction",
    "supersession",
    "confidence scoring",
    "importance ranking",
    "GDPR deletion",
    "bounded capacity",
    "memory store",
    "knowledge extraction"
  ],
  "categories": [
    "memory",
    "storage",
    "facts",
    "GDPR"
  ],
  "source_docs": [
    "777715d6655ef703"
  ],
  "backlinks": null,
  "word_count": 422,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Role in the Memory Architecture

Semantic memories are "what is known" as opposed to "what happened" (episodic) or "how to do it" (procedural). Examples: "User works at Acme Corp", "User prefers Python over Ruby", "The project deadline is March 30". These facts are extracted from conversations by the observation pipeline and stored here for future recall.

## Bounded Capacity and Eviction

Unlike episodic memories (which are intentionally unlimited as a permanent record), semantic facts have a `max_facts` cap (default 1000). When the limit is hit, `_evict_least_important()` removes the single lowest-importance fact:

```python
def _evict_least_important(self) -> None:
    if len(self._facts) >= self._max_facts:
        min_id = min(self._facts, key=lambda k: self._facts[k].importance)
        del self._facts[min_id]
```

Evicting by minimum importance rather than LRU (least recently used) is a deliberate choice: "User has a dog" (importance 3) should be dropped before "User is allergic to nuts" (importance 9) even if the allergy fact hasn't been recalled recently. This reflects a domain insight that semantic memory importance is semantically meaningful, not just access-pattern meaningful.

## Supersession Logic

When a fact is updated (e.g., the user changes jobs), the old entry is not deleted — it is marked `superseded=True`. This preserves historical truth while hiding stale data from normal search:

```python
async def search(self, query, limit, min_importance):
    # Only return non-superseded facts by default
    candidates = [f for f in self._facts.values() if not f.superseded]
```

The `facts(include_superseded=True)` method lets authorized callers (such as the audit trail) still access the history. This design avoids a race where two concurrent updates collide and accidentally discard the wrong version.

## Confidence Scores

Each `MemoryEntry` in the semantic store carries a `confidence: float` (0.0–1.0) set by the extraction pipeline. High-confidence facts (extracted from explicit user statements) rank above low-confidence inferences during recall. The confidence is not used in eviction — a low-confidence but high-importance fact is still retained.

## GDPR Deletion

Mirroring `ProceduralStore`, two targeted deletion methods were added:
- `search_and_delete(query)` — removes all facts that match a semantic query (useful for "forget everything about topic X").
- `delete_before(timestamp)` — time-based sweep for data retention compliance.

Both return deleted IDs for the audit log.

## Known Gaps

- Eviction is O(n) — a linear scan of all facts to find the minimum-importance entry. At the default cap of 1000 this is negligible, but larger deployments may want a heap or sorted structure.
- Supersession detection is external to `SemanticStore` — the extraction pipeline marks entries as superseded before calling `add()`. If two concurrent writes update the same fact, the last writer wins without conflict detection.
