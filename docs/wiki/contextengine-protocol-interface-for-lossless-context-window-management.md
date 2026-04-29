---
{
  "title": "ContextEngine Protocol: Interface for Lossless Context Window Management",
  "summary": "`ContextEngine` is a `@runtime_checkable` Python `Protocol` that defines the six operations any context management implementation must provide: `ingest`, `assemble`, `grep`, `expand`, `describe`, and `compact`. It decouples the soul runtime from any specific context engine implementation.",
  "concepts": [
    "ContextEngine",
    "Protocol",
    "runtime_checkable",
    "ingest",
    "assemble",
    "grep",
    "expand",
    "describe",
    "compact",
    "LCM",
    "context window",
    "lossless recovery"
  ],
  "categories": [
    "spec",
    "context management",
    "protocol design"
  ],
  "source_docs": [
    "7fa4fe9d35f00ace"
  ],
  "backlinks": null,
  "word_count": 430,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`ContextEngine` is the interface contract for Lossless Context Management. Any class that implements the six async methods satisfies the protocol — no inheritance required. The runtime ships a reference implementation (`LCMContext`); consumers can provide their own.

## Methods

### ingest(role, content, **metadata) → str

Ingests a new message into the store and returns its ID. Messages are immutable once stored — `ingest` is append-only. The `**metadata` kwargs are forwarded to `ContextMessage.metadata` for consumer-defined tagging (e.g., channel ID, tool call ID).

### assemble(max_tokens, *, system_reserve=0) → AssembleResult

Builds a context window that fits within `max_tokens`. `system_reserve` is subtracted from the budget before assembly — it accounts for the system prompt and tool schemas that will be prepended to the assembled context. The engine compacts older messages as needed to fit the window.

### grep(pattern, *, limit=20) → list[GrepResult]

Searches the full message history by regex pattern. Unlike `assemble`, grep searches the **immutable** message store — including content that has been compacted out of the active context window. This is the lossless recovery path: any message ever ingested can be found via grep.

### expand(node_id) → ExpandResult

Walks the DAG from a compacted node back to its original verbatim messages. This is the structured recovery path: given a summary node, retrieve exactly which messages it compressed.

### describe() → DescribeResult

Returns a metadata snapshot: message counts, token totals, date range, compaction stats. Useful for monitoring context health and deciding when to trigger proactive compaction.

### compact() → int

Forces a compaction pass and returns the number of tokens saved. Useful for proactive compaction before a large ingest, or for testing compaction behavior in isolation.

## Implementation Contract

The protocol is `@runtime_checkable`, enabling:

```python
assert isinstance(my_context, ContextEngine)
```

This is used by the runtime to validate that a provided context engine satisfies the full interface before wiring it into the cognitive pipeline.

## Simplest Valid Implementation

```python
class MyContext:
    async def ingest(self, role, content, **metadata) -> str:
        # store message, return ID
        ...
    async def assemble(self, max_tokens, *, system_reserve=0) -> AssembleResult:
        # build context window
        ...
    async def grep(self, pattern, *, limit=20) -> list[GrepResult]:
        # search messages
        ...
    async def expand(self, node_id) -> ExpandResult:
        # recover originals from compacted node
        ...
    async def describe(self) -> DescribeResult:
        # metadata snapshot
        ...
    async def compact(self) -> int:
        # force compaction, return tokens saved
        ...
```

## Known Gaps

There is no method for bulk ingestion (e.g., `ingest_many`), which would be useful for replaying a conversation history from a stored soul. Callers must call `ingest` in a loop, paying per-call overhead for each message.