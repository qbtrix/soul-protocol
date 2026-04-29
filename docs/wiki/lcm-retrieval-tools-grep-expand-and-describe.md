---
{
  "title": "LCM Retrieval Tools: grep, expand, and describe",
  "summary": "This module provides three retrieval functions — `grep`, `expand`, and `describe` — that expose different views into the immutable LCM message store. `grep` searches by regex, `expand` recursively reconstructs original messages from compacted DAG nodes, and `describe` returns a metadata snapshot of the entire store.",
  "concepts": [
    "grep",
    "expand",
    "describe",
    "GrepResult",
    "ExpandResult",
    "DescribeResult",
    "ContextNode",
    "DAG recovery",
    "retrieval",
    "LCM"
  ],
  "categories": [
    "context management",
    "LCM",
    "retrieval",
    "runtime"
  ],
  "source_docs": [
    "770a9ffa6f26dd02"
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

Once messages are ingested into `SQLiteContextStore`, callers need ways to inspect and recover that content beyond simple sequential assembly. These three functions provide targeted retrieval capabilities designed for both agent tool use (grep, expand) and observability (describe).

## grep: Regex Search

```python
async def grep(
    store: SQLiteContextStore,
    pattern: str,
    *,
    limit: int = 20,
) -> list[GrepResult]:
```

Searches all stored messages (including those buried under compaction nodes) by regex pattern. Delegates to `store.grep_messages()`, which scans the immutable `messages` table — compaction never removes rows from this table, so `grep` always searches the complete conversation history regardless of what has been compacted.

Results include message IDs, content snippets, roles, and sequence numbers ordered by recency. This makes `grep` useful for agents that need to verify whether a specific topic was discussed earlier in the session.

## expand: DAG Recovery

```python
async def expand(
    store: SQLiteContextStore,
    node_id: str,
) -> ExpandResult:
```

Given a `ContextNode` ID (a compacted summary), `expand` walks the DAG edges to recover the original verbatim messages. The algorithm is recursive:

1. Get the node's children IDs
2. For each child: try as message first, then as a node
3. If child is a node, recurse into `expand(child_id)`
4. Sort recovered messages by sequence number

This handles arbitrary nesting depth — a BULLETS node (Level 2) whose children are SUMMARY nodes (Level 1) whose children are original messages will correctly unroll to verbatim content through two levels of recursion.

The lossless guarantee of LCM depends entirely on `expand` working correctly. If compaction only stored summaries without DAG edges, the original messages would be irrecoverable.

## describe: Store Metadata

```python
async def describe(store: SQLiteContextStore) -> DescribeResult:
```

Returns a snapshot containing message count, total token estimate, date range, node counts by level, and other statistics. Delegates entirely to `store.describe()`. Used by `LCMContext.describe()` and the MCP `context_describe` tool to give agents and operators visibility into context store health.

## Module Design

The module deliberately contains only three thin functions that delegate to the store. The actual database queries live in `SQLiteContextStore` where they can be optimized independently. This separation means retrieval logic is testable without needing to understand SQLite internals.

## Known Gaps

`grep` searches only the `messages` table, not the content of summary nodes. If a fact appears only in a SUMMARY or BULLETS node (because it was compacted from messages that were then deleted — though LCM never deletes), it would not appear in grep results. In practice, LCM's append-only design means this edge case cannot occur, but the documentation does not make this invariant explicit.