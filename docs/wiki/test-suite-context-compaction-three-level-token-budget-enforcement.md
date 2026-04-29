---
{
  "title": "Test Suite: Context Compaction -- Three-Level Token Budget Enforcement",
  "summary": "Tests for Soul Protocol's context compaction system, which keeps conversation history within a token budget through three escalating strategies: LLM-generated summaries, bullet compression, and hard truncation. Covers zero-cost paths, summary/bullet/truncation tiers, idempotency, and guaranteed convergence.",
  "concepts": [
    "context compaction",
    "token budget",
    "Level 1 summary",
    "Level 2 bullets",
    "Level 3 truncation",
    "ContextNode",
    "seq range",
    "convergence guarantee",
    "is_seq_covered",
    "compaction idempotency",
    "FailingCognitiveEngine",
    "context store",
    "token estimation"
  ],
  "categories": [
    "testing",
    "context management",
    "compaction",
    "LLM token budget",
    "test"
  ],
  "source_docs": [
    "83fbf3bb9f0c3887"
  ],
  "backlinks": null,
  "word_count": 442,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_compaction.py` validates the context window management system that prevents conversation history from exceeding LLM token limits. As souls accumulate more interactions, older context must be compressed without losing essential meaning. The three-level compaction strategy trades fidelity for token efficiency in a controlled, predictable way.

## Architecture: Three Compaction Levels

```
Level 1: Summary   -- oldest N messages -> LLM-generated prose summary
Level 2: Bullets   -- old summaries -> key-point bullet list
Level 3: Truncated -- when all else fails -> hard cut with description
```

Each level is progressively more lossy but guaranteed to reduce token count.

## Zero-Cost Path

```python
async def test_no_compaction_when_under_budget(store, mock_engine):
    # Fill store with messages totaling < budget
    # Compaction should not be triggered at all

async def test_empty_store_no_compaction(store, mock_engine):
    # Empty store -> no compaction, no engine calls
```

These tests ensure compaction is not triggered unnecessarily. Every compaction invocation costs LLM tokens; the zero-cost path prevents wasted spend on contexts that do not need compression.

## Level 1: Summary Nodes

```python
async def test_summarizes_oldest_batch(store, mock_engine):
    # Fill store over budget, run compaction
    # Oldest batch should be summarized into a ContextNode

async def test_summary_node_has_children(store, mock_engine):
    # Summary node links to the original message IDs it replaced

async def test_summary_node_seq_range(store, mock_engine):
    # Summary node records the seq range it covers
```

The seq range and children links are critical for context reconstruction -- tools like `soul context expand` use them to retrieve the original messages when needed.

## Level 2: Bullet Compression

Level 2 fires when multiple Level 1 summaries accumulate. The bullets format is more compact than prose, enabling further token reduction. Tests verify that the bullets node links to the summary nodes it replaced.

## Level 3: Guaranteed Convergence

`TestLevel3Truncated` is the most important class in the suite:

```python
async def test_guaranteed_convergence(store):
    # No matter how full the store, compaction must eventually fit under budget

async def test_convergence_tiny_budget(store):
    # Even with budget=1 token, compaction must not infinite-loop

async def test_falling_back_from_failing_engine(store):
    # FailingEngine during Level 1/2 -> falls through to Level 3
```

Level 3 is the escape hatch that prevents infinite compaction loops. It works without any LLM calls, making it unconditionally safe. The fallback chain means compaction never fails completely, even when the LLM is down.

## Idempotency

```python
async def test_multiple_compaction_rounds(store, mock_engine):
    # Running compaction multiple times does not double-compact already-compacted content
```

The `is_seq_covered()` helper prevents re-compacting messages that are already covered by a summary or bullets node. Without this guard, repeated compaction passes would create nested summaries.

## Known Gaps

No TODOs flagged. The `MockCognitiveEngine` and `FailingCognitiveEngine` fixtures are local to this file rather than shared via `conftest.py`.