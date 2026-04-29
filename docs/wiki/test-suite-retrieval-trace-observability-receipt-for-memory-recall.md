---
{
  "title": "Test Suite: Retrieval Trace — Observability Receipt for Memory Recall",
  "summary": "Locks the shape and runtime behavior of `RetrievalTrace`, the observability receipt emitted by `Soul.recall()` and `Soul.smart_recall()` after every memory lookup. The suite verifies that traces are populated even on empty results, are not serialized into `.soul` files, and correctly record actor, query, candidates, and rerank metadata.",
  "concepts": [
    "RetrievalTrace",
    "TraceCandidate",
    "mark_used",
    "last_retrieval",
    "soul.recall",
    "smart_recall",
    "requester_id",
    "actor",
    "observability",
    "in-memory trace",
    "reranked flag",
    "candidate_pool",
    "latency_ms"
  ],
  "categories": [
    "testing",
    "observability",
    "memory retrieval",
    "audit trail",
    "test"
  ],
  "source_docs": [
    "befb027764a96c44"
  ],
  "backlinks": null,
  "word_count": 531,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Before `RetrievalTrace` existed, callers had no way to inspect _why_ a soul returned specific memories — which candidates were considered, what scores they received, whether reranking ran, or how long retrieval took. The trace is a lightweight in-memory receipt attached to `soul.last_retrieval` after every recall. This file locks the spec (model shape, serialization), the `mark_used` helper, and the runtime contract that the receipt is always populated.

## Spec: RetrievalTrace Model

```python
trace = RetrievalTrace()
assert trace.candidates == []
assert trace.picked == []
assert trace.source == "soul"
assert trace.latency_ms == 0
assert isinstance(trace.timestamp, datetime)
assert len(trace.id) == 12
```

Default construction produces a valid empty trace, which matters because the runtime builds the trace incrementally and needs safe zero values at construction time. The round-trip serialization test confirms all fields survive `model_dump()` / `model_validate()` cycles, important for any future logging or export pipeline.

`TraceCandidate` accepts an optional `metadata` dict for rerank-specific fields like `rerank_rank` and `original_rank`. The open dict type allows the reranker to annotate candidates without modifying the spec model.

## Spec: mark_used Helper

`trace.mark_used(picked_ids, used_by=...)` records which candidates were ultimately selected by a downstream action. Three defensive behaviors are tested:

- **Records picked IDs and used_by together**: Calling once sets both atomically.
- **Preserves existing used_by when omitted**: Callers can update `picked` without overwriting the already-set `used_by` reference.
- **Copies the input list**: Mutating the list after calling `mark_used` does not alter the trace. This prevents accidental aliasing bugs where the caller reuses the same list.

## Runtime: Soul.recall Emits Traces

```python
results = await soul.recall("coffee")
trace = soul.last_retrieval
assert trace.query == "coffee"
assert trace.actor == soul.did
assert trace.latency_ms >= 0
assert len(trace.candidates) == len(results)
```

Critical behaviors:
- **Empty store still emits a trace**: Even when `results == []`, `soul.last_retrieval` is set. This prevents callers from having to check both `results` and `trace` for None.
- **requester_id becomes actor**: When `soul.recall("x", requester_id="user:sarah@co.com")` is called, `trace.actor` reflects the requester, not the soul's own DID. This is the audit identity for access control logging.
- **Traces are not serialized**: After export → awaken, `restored.last_retrieval is None`. Traces are deliberately ephemeral — they must not accumulate in `.soul` files. The comment `# Traces are in-memory only` appears in both the spec and runtime tests.

## Runtime: smart_recall Trace Instrumentation

`smart_recall()` overwrites the trace set by its internal `recall()` call with a new trace using `source="soul.smart"`. This overwrites the inner `"soul"` source so callers can distinguish which pipeline ran.

The `metadata` dict on the final trace carries rerank parameters:
```python
assert trace.metadata.get("reranked") is False  # no engine installed
assert trace.metadata.get("candidate_pool") == 5
assert trace.metadata.get("limit") == 1
```

The `reranked` flag lets callers distinguish the fallback path (no engine → heuristic order) from an actual LLM reranking run.

## Edge Case: Spec MemoryEntry Compatibility

`_build_trace()` must not raise when given `spec.MemoryEntry` objects (which lack `importance` and `type` fields present in `runtime.MemoryEntry`). This guards against spec-layer consumers calling recall and receiving a crash from the trace builder.

## Known Gaps

A comment in the tests notes: `# v0.3 TODO: RetrievalResult.trace was Any | None, now RetrievalTrace | None` — indicating a field type was recently tightened and the TODO references tracking that migration.