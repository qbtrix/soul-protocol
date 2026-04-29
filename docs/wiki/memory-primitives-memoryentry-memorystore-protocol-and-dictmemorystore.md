---
{
  "title": "Memory Primitives — MemoryEntry, MemoryStore Protocol, and DictMemoryStore",
  "summary": "This module defines the atomic unit of soul memory (`MemoryEntry`), the backend-agnostic `MemoryStore` protocol, and a reference in-memory implementation (`DictMemoryStore`). It also introduces `Interaction` and `Participant` models for multi-party conversations, along with `MemoryVisibility` tiers for controlling what surfaces in public channel contexts.",
  "concepts": [
    "MemoryEntry",
    "MemoryStore",
    "DictMemoryStore",
    "Interaction",
    "Participant",
    "MemoryVisibility",
    "layer",
    "scope",
    "superseded",
    "bi-temporal",
    "ingested_at",
    "recall",
    "search"
  ],
  "categories": [
    "memory",
    "spec layer",
    "protocol interfaces",
    "soul persistence"
  ],
  "source_docs": [
    "6ec438b557d084c5"
  ],
  "backlinks": null,
  "word_count": 460,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Memory is the core capability that makes AI companions persistent. This module provides the protocol-layer primitives that any memory backend — in-memory dict, SQLite, Redis, vector database — must satisfy. By defining these at the spec layer, Soul Protocol ensures that runtimes can swap backends without changing the retrieval interface.

## `MemoryEntry`

```python
class MemoryEntry(BaseModel):
    id: str
    content: str
    timestamp: datetime
    source: str = ""
    layer: str = ""
    visibility: MemoryVisibility = MemoryVisibility.BONDED
    scope: list[str]        # hierarchical RBAC/ABAC tags
    metadata: dict[str, Any]
    ingested_at: datetime | None  # bi-temporal: when it entered the pipeline
    superseded: bool = False       # True when contradicted by newer memory
```

### Bi-temporal fields
`timestamp` records when the remembered event occurred; `ingested_at` records when it entered the memory pipeline. These differ for imported memories, historical reconstructions, or delayed processing. The distinction matters for sorting (show most recently *experienced* events) vs. pipeline debugging (find memories ingested in the last hour).

### `superseded`
When a newer memory contradicts an older one (e.g., a contact's job title changed), the old entry is marked `superseded=True` rather than deleted. This preserves the historical record while allowing retrieval to filter out stale entries.

### `scope` and `visibility`
Scope tags are hierarchical RBAC/ABAC strings (`"org:sales:*"`). `visibility` is a coarser three-level tier (`PUBLIC`, `BONDED`, `PRIVATE`) for channel-level access control. Both operate at retrieval time — the memory is stored without filtering; the retrieval layer applies the checks.

## `MemoryStore` Protocol

```python
class MemoryStore(Protocol):
    def store(self, layer: str, entry: MemoryEntry) -> str: ...
    def recall(self, layer: str, *, limit: int) -> list[MemoryEntry]: ...
    def search(self, query: str, *, limit: int) -> list[MemoryEntry]: ...
    def delete(self, memory_id: str) -> bool: ...
    def layers(self) -> list[str]: ...
```

Layers are free-form strings (e.g., `"episodic"`, `"semantic"`, `"working"`), not an enum. Runtimes define their own layer namespaces. The protocol deliberately omits `count()` and `all_entries()` — those are convenience methods on `DictMemoryStore` but not required of all backends.

## `DictMemoryStore`

The reference implementation. Uses `dict[str, list[MemoryEntry]]` keyed by layer name. `search()` uses Jaccard token overlap — fast and dependency-free, suitable for tests and small datasets. Production runtimes replace this with BM25, vector search, or hybrid retrieval.

## `Interaction` and Multi-Participant Support

Added in `feat/spec-multi-participant`, `Interaction` generalizes the two-party user/agent model:

```python
class Interaction(BaseModel):
    participants: list[Participant]
    timestamp: datetime
    metadata: dict[str, Any]
```

Backward compatibility is maintained via `user_input` and `agent_output` properties (return first participant with role `"user"`/`"agent"`) and a `from_pair()` factory for the common two-party case.

## Data Flow

```
Interaction occurs
  └─ MemoryEntry created (content, layer, visibility, scope)
       └─ MemoryStore.store("episodic", entry)
            └─ MemoryStore.recall("episodic", limit=10) -> recent memories
                 └─ Injected into LLM context for next interaction
```

## Known Gaps

- `DictMemoryStore.search()` uses basic token overlap with no TF-IDF weighting. Adequate for unit tests, not for production recall quality.