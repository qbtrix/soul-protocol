---
{
  "title": "Test Suite: Context Store Retrieval — Grep, Expand, and Describe",
  "summary": "Validates the three retrieval operations on Soul Protocol's conversation context store: regex-based message search (`grep`), DAG node expansion to recover original messages (`expand`), and metadata snapshot generation (`describe`). These operations power agent tools that let an LLM inspect its own conversation history without re-loading the full context window.",
  "concepts": [
    "grep",
    "expand",
    "describe",
    "SQLiteContextStore",
    "ContextMessage",
    "ContextNode",
    "CompactionLevel",
    "SUMMARY",
    "BULLETS",
    "TRUNCATED",
    "recursive expansion",
    "DAG",
    "context window"
  ],
  "categories": [
    "testing",
    "context management",
    "retrieval",
    "conversation history",
    "test"
  ],
  "source_docs": [
    "ba9f71cbe4267ed4"
  ],
  "backlinks": null,
  "word_count": 496,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul Protocol maintains conversation history in a `SQLiteContextStore` — a DAG where leaf nodes are raw messages and internal nodes are compacted summaries at progressive levels (SUMMARY, BULLETS, TRUNCATED). This file tests the three retrieval helpers that sit on top of the store, providing agent-accessible introspection without requiring a full context reload.

## Fixtures

```python
@pytest.fixture
async def store():
    s = SQLiteContextStore(":memory:")
    await s.initialize()
    yield s
    await s.close()

@pytest.fixture
async def populated_store(store):
    """Store with 10 messages for grep/expand tests."""
    for i in range(10):
        await store.append_message(ContextMessage(
            id=f"msg{i}",
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message {i}: {'hello' if i < 5 else 'goodbye'} world",
            token_count=10,
        ))
    return store
```

Using `:memory:` for SQLite ensures tests are isolated, fast, and leave no on-disk artifacts. The alternating role pattern (`user`/`assistant`) lets role-filtering tests work with a minimal dataset.

## Grep

`grep(store, pattern, limit)` performs case-insensitive regex search across all messages and returns `GrepResult` objects containing `message_id`, `role`, and `content_snippet`.

- **Case-insensitive matching**: Searching for `"hello"` finds messages containing `"HELLO WORLD"`. Without this, agents would miss matches due to capitalization differences in user input.
- **Regex support**: Full Python regex patterns are supported (e.g., `r"\$\d+\.\d+"` to find price mentions). The test for special regex characters (`$`, `.`) prevents the implementation from treating the pattern as a literal string.
- **Limit**: Prevents runaway result sets on large histories.
- **Empty store**: Returns `[]` without error — callers don't need to check store size before calling.

## Expand

`expand(store, node_id)` recovers the original messages that a compaction node summarized.

```
ContextNode (BULLETS)
  └─ ContextNode (SUMMARY)
       └─ ContextMessage msg0 ... msg4
```

Key behaviors:
- **Nonexistent node**: Returns an `ExpandResult` with `original_messages=[]` rather than raising. This prevents agents from crashing when they reference a node that was evicted.
- **Order preservation**: Even if `children_ids` are stored out of order, expand sorts by `seq` to return messages in chronological order. Without this, the recovered context would be incoherent.
- **Recursive expansion**: A BULLETS node pointing to a SUMMARY node pointing to messages is fully unwound. This handles the multi-level compaction pipeline where summaries are themselves further summarized.
- **Truncated nodes**: When a TRUNCATED node only has partial children (the rest were evicted), expand returns what is available rather than failing. This prevents hard errors when long-running contexts have partially expired.

## Describe

`describe(store)` returns a metadata snapshot: total message count, total token count, node count, compaction stats by level, and date range.

- **Empty store**: Returns zeroed fields and `date_range=(None, None)` — no errors.
- **Compaction stats**: Returns per-level counts (e.g., `{"summary": 1, "bullets": 1}`), enabling agents to report memory state.
- **Date range**: The `(start, end)` tuple always has `start <= end` when non-null — a basic sanity check that prevents inverted ranges from confusing callers.

## Known Gaps

No TODO or FIXME markers are present. The `test_expand_truncated_node` only tests partial children (2 of 5 advertised) — there is no test for a TRUNCATED node with zero surviving children.