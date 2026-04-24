---
{
  "title": "LCM Data Models: Context Messages, DAG Nodes, and Compaction Levels",
  "summary": "The LCM data models define the atomic units of Lossless Context Management: `ContextMessage` (immutable ingested messages), `ContextNode` (compacted DAG nodes), `CompactionLevel` (verbatim to truncated), and result types for assembly, search, expansion, and metadata queries.",
  "concepts": [
    "ContextMessage",
    "ContextNode",
    "CompactionLevel",
    "AssembleResult",
    "GrepResult",
    "ExpandResult",
    "DescribeResult",
    "DAG",
    "compaction",
    "immutable messages",
    "seq ordering",
    "token budget"
  ],
  "categories": [
    "spec",
    "context management",
    "LCM",
    "data models"
  ],
  "source_docs": [
    "92e4153cfb273702"
  ],
  "backlinks": null,
  "word_count": 566,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`spec/context/models.py` defines the seven Pydantic data models that underpin Lossless Context Management (LCM): the atomic message unit, the DAG compaction node, the compaction level enum, and four result types for assembly, search, expansion, and metadata queries. These are spec-layer primitives — zero runtime imports, no LLM calls, no filesystem I/O.

## CompactionLevel

An ordered `StrEnum` from least to most lossy compaction:

| Level | Description |
|-------|-------------|
| `VERBATIM` | Original message — no compression applied |
| `SUMMARY` | LLM-generated prose summary of a message batch |
| `BULLETS` | LLM-generated bullet-point summary (more compact than prose) |
| `TRUNCATED` | Deterministic head-truncation — no LLM required, guaranteed to fit |

The order matters: implementations that need to apply compaction progressively can walk up the enum until the token budget is satisfied. `TRUNCATED` is the last resort — it always converges but may lose tail content.

## ContextMessage: The Atomic Unit

A single turn in the conversation, immutable once stored:

```python
ContextMessage(
    role="user",
    content="What was the deadline we agreed on last week?",
    token_count=14,
    seq=142,
)
```

The `seq` field provides a monotonic ordering that survives serialization, replay, and cross-process transfers. Messages are never updated or deleted — the store is append-only. This immutability guarantee is what makes `grep()` reliable: you can always search the full history.

Auto-generated IDs use a 12-hex-char prefix of a UUID4, short enough to embed in logs but unique enough to avoid collisions within a session.

## ContextNode: The DAG Compaction Node

A node representing a compacted view of one or more messages:

```python
ContextNode(
    level=CompactionLevel.SUMMARY,
    content="The user and agent agreed on a Friday deadline for the Q3 report.",
    token_count=18,
    children_ids=["a1b2c3", "d4e5f6", "g7h8i9"],  # IDs of summarized messages
    seq_start=140,
    seq_end=142,
)
```

Nodes form a directed acyclic graph (DAG): a `SUMMARY` node points to the `VERBATIM` messages it compressed. A `BULLETS` node may point to `SUMMARY` nodes it further compressed. The `expand()` operation walks `children_ids` recursively to recover original verbatim messages — this is the structured recovery path.

`seq_start` and `seq_end` allow implementations to quickly determine which portion of the message timeline a node covers without traversing its children.

## AssembleResult

The output of `ContextEngine.assemble()`:

```python
AssembleResult(
    nodes=[...],            # ordered list fitting within token budget
    total_tokens=3200,
    compaction_applied=True,
)
```

`compaction_applied=True` tells callers that some messages were summarized or truncated in this window. This flag is useful for logging, for triggering proactive future compaction, and for testing that compaction fired when expected.

## GrepResult

A single hit from searching the immutable message store:

```python
GrepResult(
    message_id="a1b2c3",
    seq=42,
    role="user",
    content_snippet="deadline we agreed on...",
)
```

Grep results include `seq` so callers can fetch surrounding context (messages with adjacent `seq` values) if needed.

## ExpandResult

Original messages recovered from a compacted node:

```python
ExpandResult(
    node_id="summarynode_x",
    level=CompactionLevel.SUMMARY,
    original_messages=[msg1, msg2, msg3],
)
```

`level` indicates how much information was lost in compaction — a `SUMMARY` node may have paraphrased; a `TRUNCATED` node definitely lost tail content.

## DescribeResult

A metadata snapshot of the entire context store, useful for health monitoring:

```python
DescribeResult(
    total_messages=1450,
    total_nodes=87,
    total_tokens=48000,
    date_range=(first_msg_ts, last_msg_ts),
    compaction_stats={"verbatim": 62, "summary": 21, "bullets": 4},
)
```

## Known Gaps

The `date_range` field is typed as `tuple[datetime | None, datetime | None]`. Pydantic v2 serializes tuples as JSON arrays, which is correct but not immediately obvious. A dedicated `DateRange` model with `start` and `end` fields would be more explicit and easier to extend with additional metadata.