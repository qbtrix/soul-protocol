---
{
  "title": "SQLiteContextStore: Immutable Message Store and Compaction DAG",
  "summary": "`SQLiteContextStore` is the persistence layer for LCM, implementing an append-only SQLite database with three tables: immutable conversation messages, compaction DAG nodes, and DAG edges. It uses `asyncio.to_thread()` to make synchronous SQLite calls safe in async code without adding any external dependencies.",
  "concepts": [
    "SQLiteContextStore",
    "append-only",
    "compaction DAG",
    "asyncio.to_thread",
    "check_same_thread",
    "sequence counter",
    "ContextMessage",
    "ContextNode",
    "node_children",
    "thread safety"
  ],
  "categories": [
    "context management",
    "LCM",
    "persistence",
    "SQLite"
  ],
  "source_docs": [
    "583984581da0159b"
  ],
  "backlinks": null,
  "word_count": 459,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`SQLiteContextStore` is the foundation that makes LCM's lossless guarantee possible. By treating the `messages` table as append-only and representing compacted summaries as a separate DAG, it can always recover original conversation content — nothing is ever overwritten or deleted.

## Schema: Three Tables

```sql
-- Append-only conversation messages
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    seq INTEGER UNIQUE NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    metadata TEXT NOT NULL  -- JSON blob
);

-- Compaction summary nodes
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    level INTEGER NOT NULL,  -- 1=SUMMARY, 2=BULLETS, 3=TRUNCATED
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

-- DAG edges: parent node -> child node or message
CREATE TABLE node_children (
    parent_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    PRIMARY KEY (parent_id, child_id)
);
```

## Thread Safety: check_same_thread=False

```python
conn = sqlite3.connect(db_path, check_same_thread=False)
```

This flag is set because all SQLite operations are wrapped in `asyncio.to_thread()`. Python's `asyncio.to_thread()` dispatches to a `ThreadPoolExecutor` — the connection is created on one worker thread but subsequent calls may execute on different threads. `check_same_thread=False` suppresses SQLite's built-in same-thread guard, which would otherwise raise errors on this legitimate pattern.

Without this flag, every operation after the first would fail with a "SQLite objects created in a thread can only be used in that same thread" error.

## Sequence Counter Recovery

```python
async def initialize(self) -> None:
    ...
    row = await asyncio.to_thread(self._execute_fetchone, "SELECT MAX(seq) FROM messages")
    if row and row[0] is not None:
        self._seq_counter = row[0]
```

On startup, the store reads the current maximum sequence number from the database and restores its in-memory counter. This ensures that messages appended after a restart continue from the correct sequence — critical for `expand()`'s sort-by-seq guarantee.

## Async Wrapping Pattern

Every public method follows the same pattern:

```python
async def append_message(self, message: ContextMessage) -> ContextMessage:
    def _insert():
        # synchronous SQLite code
        ...
    return await asyncio.to_thread(_insert)
```

Closures capture local variables and run in the thread pool. This approach avoids blocking the event loop while keeping all SQLite code in straightforward synchronous Python — no async SQLite driver, no aiosqlite dependency.

## grep_messages Implementation

The grep implementation pulls all messages and applies Python's `re.search()` rather than using SQLite's `LIKE` or `GLOB`. This is intentional: SQLite's pattern matching is limited (no full regex support without extensions), and conversation stores are small enough that a full table scan is fast.

## Known Gaps

No WAL (Write-Ahead Logging) mode is enabled. WAL allows concurrent readers without blocking writers, which would benefit multi-threaded access patterns. The current `asyncio.to_thread()` approach serializes writes through Python's GIL, making WAL unnecessary for single-process use, but a future multi-process architecture would need it.