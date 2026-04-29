---
{
  "title": "Retrieval Trace — Observability Receipt for Every Recall and Search Operation",
  "summary": "`RetrievalTrace` is a lightweight receipt written once per retrieval call, capturing the ranked candidate list, which candidates were actually used, latency, and a downstream reference. It feeds the paw-runtime JSONL sink, graduation policy, the \"Why?\" explainability drawer, and SoulBench fixture generation — all from a single portable shape.",
  "concepts": [
    "RetrievalTrace",
    "TraceCandidate",
    "mark_used",
    "picked",
    "used_by",
    "pocket_id",
    "latency_ms",
    "observability",
    "graduation policy",
    "JSONL sink",
    "Why? drawer",
    "SoulBench",
    "retrieval observability"
  ],
  "categories": [
    "retrieval",
    "observability",
    "spec layer",
    "tracing"
  ],
  "source_docs": [
    "32a22db4dab63304"
  ],
  "backlinks": null,
  "word_count": 502,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

When a soul recalls a memory or searches a knowledge base, the retrieval layer makes decisions that affect the LLM's response. For debugging, evaluation, and compliance, those decisions need to be observable after the fact: what was the query, what candidates were ranked, which ones actually made it into the context window, and how long did it take?

`RetrievalTrace` is the portable answer. It is intentionally separated from the router-level `RetrievalResult` (which carries the merged candidates for the caller) to avoid naming collisions and to serve a different concern: `RetrievalResult` is the router's output to the application; `RetrievalTrace` is the receipt for downstream observability systems.

## `TraceCandidate`

```python
class TraceCandidate(BaseModel):
    id: str
    source: str = "soul"
    score: float = 0.0
    tier: str | None = None
    metadata: dict[str, Any]
```

`score` is runtime-defined and not normalized across sources — an ACT-R activation score, a BM25 score, and a cosine similarity score all appear here but are not comparable without normalization. `tier` is optional so kb articles and skills (which have no tier concept) don't need to fake one.

## `RetrievalTrace`

```python
class RetrievalTrace(BaseModel):
    id: str
    actor: str
    query: str
    source: str
    candidates: list[TraceCandidate]   # all candidates, ranked
    picked: list[str]                  # IDs actually used
    used_by: str | None                # e.g. "action:act_123"
    latency_ms: int
    pocket_id: str | None
    timestamp: datetime
    metadata: dict[str, Any]

    def mark_used(self, picked_ids, used_by=None) -> None:
        self.picked = list(picked_ids)
        if used_by is not None: self.used_by = used_by
```

### `candidates` vs `picked`
The trace records all candidates that the retrieval function returned. The **caller** populates `picked` after deciding which candidates to include in the LLM context. The separation is intentional: the retrieval function doesn't know what the application will do with its results. `mark_used()` is called after the application has made that decision.

### `used_by`
A downstream reference string — e.g., `"action:act_123"` when the retrieved memories fed an Instinct proposal. This allows traces to be joined to the audit log without duplicating the retrieved content.

### `pocket_id`
Optional context identifier for when retrieval happens within a specific Pocket (Soul Protocol's scoped conversation container). Allows traces to be filtered to a specific conversation thread.

## Why a Separate Module?

The trace module explicitly avoids `spec/retrieval.py` to prevent name collision with `RetrievalCandidate` and `RetrievalResult` — two existing types that operate at the router level. `TraceCandidate` and `RetrievalTrace` are observability primitives; they are read by the JSONL sink, graduation policy, and debug tooling. Keeping them separate avoids circular imports and makes the concern boundary explicit.

## Data Flow

```
Retrieval call
  └─ RetrievalTrace created (candidates ranked, latency measured)
       └─ Application picks subset -> trace.mark_used(picked_ids, used_by)
            └─ paw-runtime sinks trace to JSONL log
                 └─ graduation policy reads traces -> upgrades persistent memories
                      └─ Why? drawer reads traces -> shows user what was recalled
```

## Known Gaps

- `score` is not normalized. Downstream consumers that try to compare scores across sources (soul memory BM25 vs kb article cosine similarity) will get meaningless comparisons without a normalization step that the spec does not prescribe.