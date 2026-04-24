---
{
  "title": "RecallEngine: Cross-Store Memory Retrieval with ACT-R Activation",
  "summary": "The RecallEngine is Soul Protocol's central retrieval coordinator, querying episodic, semantic, and procedural stores in parallel, ranking results via ACT-R activation scores, applying OCEAN personality modulation and visibility filtering, and optionally enriching results through the knowledge graph. It is the single integration point through which all memory retrieval flows.",
  "concepts": [
    "RecallEngine",
    "ACT-R activation",
    "cross-store retrieval",
    "memory recall",
    "knowledge graph",
    "visibility filtering",
    "progressive disclosure",
    "OCEAN modulation",
    "bond strength",
    "somatic marker",
    "memory pipeline",
    "spreading activation"
  ],
  "categories": [
    "memory",
    "recall",
    "retrieval",
    "privacy"
  ],
  "source_docs": [
    "910cdb9509e69155"
  ],
  "backlinks": null,
  "word_count": 487,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Why a Unified Recall Engine?

Without a unified engine, each memory store would need its own ranking logic, and cross-tier retrieval (e.g., "what do I know about deployments from both procedural how-tos and past episodic events?") would require the caller to merge and re-rank multiple lists. `RecallEngine` eliminates that complexity: callers call one method and get a single ranked list.

## Architecture

`RecallEngine` is wired at construction time with references to the individual stores and optional components:

```python
def __init__(self, episodic, semantic, procedural,
             strategy, personality, graph) -> None:
```

All parameters are optional — the engine degrades gracefully when a store or feature is absent, enabling lightweight deployments.

## The Recall Pipeline

`recall()` executes in several ordered phases:

1. **Fan-out**: Query all configured stores concurrently for candidates.
2. **Type filter**: If `types` is specified, discard entries not in the requested set.
3. **Importance filter**: Drop entries below `min_importance`.
4. **Visibility filter**: Gate `BONDED` memories behind `bond_strength >= bond_threshold`; gate `PRIVATE` memories to system/soul requesters only (`requester_id=None`). `PUBLIC` memories always pass.
5. **ACT-R scoring**: Score each candidate via `compute_activation()` — recency, frequency, spreading activation from the query, and emotional somatic markers.
6. **Personality modulation**: Add per-OCEAN-trait bonus to each score.
7. **Knowledge graph enrichment**: If `use_graph=True`, query the graph for entities mentioned in the query and inject connected memories as additional candidates.
8. **Sort and truncate**: Return top-`limit` entries.
9. **Access timestamp update**: Strengthen future recall by recording this retrieval on each returned entry.

## Progressive Disclosure

Added in v0.4.0, the `progressive` flag enables returning up to `limit*2` results. The first `limit` entries are full-content "primary" memories. Overflow entries have their content replaced with their abstract (summary) to reduce token cost while still signaling that the knowledge exists:

```python
# Overflow entries: replace content with abstract
for entry in overflow:
    if entry.abstract:
        entry.content = entry.abstract
```

This pattern matters for LLM-powered agents on tight context budgets — the primary set delivers actionable details while the overflow set helps the LLM decide whether to ask for more.

## Privacy Design

The visibility system prevents memory leakage between principals. A bonded companion can read relationship memories (`BONDED`) but not private diary entries (`PRIVATE`). Without this guard, a compromised requester ID could exfiltrate all memories. The `bond_threshold` default gives operators a tunable privacy boundary.

## PII Protection in Logs

Logs emit `query_len=N` rather than the raw query text. This prevents PII from appearing in application logs when the query contains user names, emails, or sensitive context.

## Known Gaps

- Graph enrichment is an additive pass — graph-connected memories are appended after initial ranking rather than being fully re-ranked with graph context. This can push highly relevant graph memories below the cutoff.
- The `personality` parameter accepted by `recall()` is reserved but the modulation call is delegated to the activation layer; the engine itself does not gate on personality being present vs. absent, relying on activation to return 0-delta gracefully.
