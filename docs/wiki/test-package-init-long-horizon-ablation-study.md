---
{
  "title": "Test Package Init: Long-Horizon Ablation Study",
  "summary": "Package initialiser for `tests/test_long_horizon/`, the sub-package housing ablation study tests that evaluate soul memory and context performance over extended interaction sequences. Created 2026-03-11.",
  "concepts": [
    "pytest",
    "package init",
    "long-horizon",
    "ablation study",
    "memory degradation",
    "context compaction",
    "soul evolution",
    "extended interactions"
  ],
  "categories": [
    "testing",
    "infrastructure",
    "long-horizon",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "0a446d5b73b70b3f"
  ],
  "backlinks": null,
  "word_count": 170,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`tests/test_long_horizon/__init__.py` marks the `test_long_horizon` directory as a Python package so that pytest can collect tests within it. The comment header identifies this as the package for long-horizon ablation study tests, created on 2026-03-11.

## What Are Long-Horizon Ablation Tests?

Ablation studies systematically disable or degrade components to measure their contribution. In the context of Soul Protocol, long-horizon ablation tests likely evaluate:

- How much memory recall quality degrades over many conversation turns.
- Whether compaction strategies preserve relevant context over long sessions.
- How soul state evolves (or drifts) over extended interaction sequences.

These tests are structurally separate from unit tests because they require longer-running fixtures and may exercise different failure modes than short interaction tests.

## Contents

Only the comment header — no imports, fixtures, or shared utilities. Individual test modules in this package carry their own fixtures.

## Known Gaps

The package exists but its test modules are not visible in this batch — the actual ablation study implementations are in sibling files not captured here.