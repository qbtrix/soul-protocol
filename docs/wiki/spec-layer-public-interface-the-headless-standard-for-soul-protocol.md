---
{
  "title": "Spec Layer Public Interface: The Headless Standard for Soul Protocol",
  "summary": "The `spec/__init__.py` is the public surface of Soul Protocol's headless spec layer — minimal, unopinionated primitives that any runtime can implement with zero dependencies on opinionated modules like memory, cognitive engines, or evolution systems. It aggregates over 60 exported symbols spanning identity, memory, retrieval, context management, A2A interop, decision traces, and eternal storage.",
  "concepts": [
    "spec layer",
    "headless standard",
    "ContextEngine",
    "MemoryStore",
    "A2AAgentCard",
    "EternalStorageProvider",
    "StorageProtocol",
    "decision traces",
    "retrieval protocol",
    "soul file format",
    "LCM",
    "embedding provider"
  ],
  "categories": [
    "spec",
    "protocol design",
    "public API"
  ],
  "source_docs": [
    "89b1d60011fd80fd"
  ],
  "backlinks": null,
  "word_count": 457,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The spec layer is the "HTTP layer" of Soul Protocol: it defines what a soul *can do* without specifying *how*. The `spec/__init__.py` is the public surface of this layer — over 60 exported symbols spanning identity, memory, retrieval, context management, A2A interop, decision traces, journal primitives, eternal storage, and the `.soul` file format. All symbols are pure data models or `Protocol` interfaces — no concrete implementations, no LLM calls, no filesystem I/O.

This design means any runtime (PocketPaw, a headless agent, a browser extension, a mobile SDK) can depend on the spec without pulling in the full runtime stack.

## Export Groups

### Identity
`Identity`, `BondTarget` — the core identity primitives. Kept at the spec layer because even the thinnest consumer (e.g., an A2A agent card generator) needs to construct and inspect soul identities.

### Memory
`MemoryEntry`, `Interaction`, `Participant`, `MemoryStore`, `DictMemoryStore`, `MemoryVisibility` — the spec-level memory vocabulary. `DictMemoryStore` is the reference `MemoryStore` implementation for consumers that need a working store without the full runtime.

### Context (LCM — Lossless Context Management)
`ContextEngine`, `ContextMessage`, `ContextNode`, `AssembleResult`, `CompactionLevel`, `GrepResult`, `ExpandResult`, `DescribeResult` — the protocol and data models for lossless context window management. Any implementation satisfying `ContextEngine` can be plugged into the runtime.

### Retrieval
`SourceAdapter`, `AsyncSourceAdapter`, `CredentialBroker`, `Credential`, `RetrievalRequest`, `RetrievalCandidate`, `RetrievalResult`, `RetrievalDataRef`, plus a full exception hierarchy (`RetrievalError`, `NoSourcesError`, `SourceTimeoutError`, `CredentialScopeError`, `CredentialExpiredError`). Concrete implementations (`RetrievalRouter`, `InMemoryCredentialBroker`) are application-layer and live in PocketPaw.

### Decision Traces
`AgentProposal`, `HumanCorrection`, `DecisionGraduation`, `Disposition`, plus helpers (`build_proposal_event`, `build_correction_event`, `find_corrections_for`, `trace_decision_chain`, `cluster_correction_patterns`). These are the structured proposal/correction event payloads that power agent auditing and learning from human feedback.

### Journal
`Actor`, `DataRef`, `EventEntry`, `ACTION_NAMESPACES` — the org-level event sourcing primitives. Decision trace events are stored as `EventEntry` instances in the journal.

### A2A Interop
`A2AAgentCard`, `A2ASkill`, `SoulExtension` — Pydantic models mapping Google's A2A Agent Card spec to Soul Protocol primitives.

### Eternal Storage
`EternalStorageProvider`, `ArchiveResult`, `RecoverySource` — the protocol for immutable eternal storage backends (Arweave, IPFS).

### Embeddings
`EmbeddingProvider`, `cosine_similarity`, `dot_product`, `euclidean_distance` — the embedding protocol and similarity utility functions.

### Scope and Soul File Format
`match_scope`, `normalise_scopes` — RBAC/ABAC scope matching utilities. `pack_soul`, `unpack_soul`, `unpack_to_container` — functions for the `.soul` zip archive format.

### Templates and Manifests
`SoulTemplate` — the blueprint model for `SoulFactory`. `Manifest` — metadata for soul archives.

## Boundary Enforcement

The spec layer imports zero opinionated modules. A `grep` for `soul_protocol.runtime` in `spec/` should return empty. This boundary is enforced by convention, not by an automated import boundary check.

## Known Gaps

There is no automated test or linter rule that prevents a spec module from accidentally importing a runtime module. An import boundary test (e.g., using `importlib` to walk all spec submodules and assert no runtime imports) would catch violations at CI time rather than during code review.