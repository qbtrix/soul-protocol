---
{
  "title": "Context Subpackage Interface: Lossless Context Management Spec Layer",
  "summary": "The `spec/context/__init__.py` re-exports all Lossless Context Management (LCM) primitives — the `ContextEngine` protocol and seven Pydantic models — as the public interface for context window management. This subpackage is spec-only: no opinionated implementations, no runtime imports.",
  "concepts": [
    "ContextEngine",
    "LCM",
    "lossless context management",
    "ContextMessage",
    "ContextNode",
    "CompactionLevel",
    "AssembleResult",
    "GrepResult",
    "ExpandResult",
    "DescribeResult",
    "spec layer"
  ],
  "categories": [
    "spec",
    "context management",
    "LCM"
  ],
  "source_docs": [
    "30ace50864bd680c"
  ],
  "backlinks": null,
  "word_count": 552,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `spec/context/__init__.py` is the public interface for Lossless Context Management (LCM) — Soul Protocol's approach to fitting a growing conversation history into a fixed context window without permanently discarding any information. Introduced in v0.3.0, this subpackage exports the `ContextEngine` protocol and seven Pydantic data models that together define the complete LCM interface.

## The Problem LCM Solves

Traditional context management in AI agents uses a sliding window: when the conversation history exceeds the model's context limit, old messages are dropped permanently. This creates a well-known failure mode — the agent "forgets" critical context (user preferences, agreed decisions, earlier clarifications) simply because they were mentioned long ago.

LCM addresses this with a different approach:
- Messages are **immutable once ingested** — they are never deleted from the store.
- Older messages are **compacted** into summary or bullet nodes that consume fewer tokens.
- Compacted nodes can be **expanded** back to their original messages on demand.
- The `grep()` operation can **search** the full uncompacted history, including content that has been compressed out of the active window.

Under LCM, no information is ever permanently lost — only temporarily compressed.

## Exported Symbols

```python
from soul_protocol.spec.context import (
    ContextEngine,      # Protocol: the interface all implementations must satisfy
    ContextMessage,     # Atomic message unit — immutable once ingested
    ContextNode,        # DAG node representing a compacted view of messages
    CompactionLevel,    # Enum: verbatim / summary / bullets / truncated
    AssembleResult,     # Result of assembling a context window for an LLM call
    GrepResult,         # A single hit from searching the message store
    ExpandResult,       # Original messages recovered from a compacted node
    DescribeResult,     # Metadata snapshot of the entire context store
)
```

## Design Principle: Spec, Not Implementation

All symbols in this subpackage are spec-layer primitives: minimal, zero runtime imports, no LLM calls. The reference implementation (`LCMContext`) lives in the runtime layer. This separation means any consumer can implement their own context engine by satisfying the `ContextEngine` protocol — no dependency on the full Soul Protocol runtime required.

A lightweight agent that only needs basic windowing can implement a trivial `ContextEngine` in a few dozen lines. A production agent can use the full `LCMContext` with DAG-based compaction and LLM-powered summarization.

## Relationship to the Runtime

The `ContextEngine` protocol is consumed by the runtime's cognitive pipeline. When a `Soul` calls its cognitive engine for reflection or observation, the engine uses `ContextEngine.assemble()` to build a context window that fits the model's token limit. The spec layer defines *what* the engine must provide; the runtime provides the concrete `LCMContext` that implements it.

Runtimes that replace the default cognitive engine (e.g., a custom LLM wrapper) must provide a compatible `ContextEngine` to maintain the lossless property.

## Compaction Levels

The `CompactionLevel` enum is central to LCM's design. In ascending order of compression:

| Level | Description |
|-------|-------------|
| `VERBATIM` | Original message, no compression |
| `SUMMARY` | LLM-generated prose summary |
| `BULLETS` | LLM-generated bullet-point summary |
| `TRUNCATED` | Deterministic head-truncation (no LLM, guaranteed convergence) |

`TRUNCATED` is the failsafe: it always fits within budget regardless of LLM availability.

## Known Gaps

The LCM spec does not define a standard serialization format for the context store. Migrating a context across runtimes or restoring it after a process restart requires a custom export/import step not covered by this interface.