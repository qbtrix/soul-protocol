---
{
  "title": "Memory Subsystem Package Exports",
  "summary": "The `memory` package `__init__.py` re-exports every public symbol from the memory subsystem's modules into a single flat namespace. It acts as a versioned registry — each significant export addition is tagged in the file header — so consumers can import everything from `soul_protocol.runtime.memory` without knowing which submodule it lives in.",
  "concepts": [
    "memory subsystem",
    "package exports",
    "MemoryManager",
    "EpisodicStore",
    "SemanticStore",
    "RecallEngine",
    "ContradictionDetector",
    "rerank_memories",
    "public API",
    "ACT-R"
  ],
  "categories": [
    "memory",
    "package-structure",
    "soul-protocol-core"
  ],
  "source_docs": [
    "298a0eba5f76393a"
  ],
  "backlinks": null,
  "word_count": 265,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Role of This File

The memory subsystem is split across ~15 modules. Without a consolidated `__init__.py`, every consumer would need to know the exact submodule for each import. This file provides a single stable import surface:

```python
from soul_protocol.runtime.memory import (
    MemoryManager, EpisodicStore, SemanticStore,
    RecallEngine, ContradictionDetector, rerank_memories
)
```

## Exported Symbols by Category

**Core stores:**
- `MemoryManager` — top-level facade
- `CoreMemoryManager` — always-in-context 2KB block
- `EpisodicStore` — timestamped interaction history
- `SemanticStore` — long-term facts
- `ProceduralStore` — how-to knowledge
- `KnowledgeGraph`, `TemporalEdge` — entity relationship graph

**Recall and retrieval:**
- `RecallEngine` — BM25 + ACT-R scoring
- `SearchStrategy`, `TokenOverlapStrategy` — pluggable retrieval strategies (v0.2.2)

**Archival:**
- `ArchivalMemoryStore`, `ConversationArchive` — compressed conversation storage

**Psychology pipeline:**
- `detect_sentiment` — somatic marker detection
- `compute_activation` — ACT-R base-level activation
- `compute_significance`, `is_significant` — LIDA attention gate
- `SelfModelManager` — soul's self-concept

**Memory hygiene:**
- `MemoryCompressor` — rule-based compression without LLM
- `reconcile_fact` — deduplication / SKIP / MERGE / CREATE routing
- `ContradictionDetector` — semantic contradiction detection (v0.4.0)
- `rerank_memories` — LLM-based reranking

## Version History as Documentation

The file header serves as a changelog for the public API surface — each new export is tagged with the version or branch that introduced it. This makes it easy to audit when a symbol became available without reading git history.

## Known Gaps

- No `__version__` attribute or formal API versioning is exported — callers must check the package version separately.
- The flat export list can produce `ImportError` at import time if any submodule fails — there is no lazy-loading or graceful degradation.