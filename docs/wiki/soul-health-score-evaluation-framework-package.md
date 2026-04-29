---
{
  "title": "Soul Health Score Evaluation Framework Package",
  "summary": "Package marker and documentation anchor for the 7-dimension Soul Health Score (SHS) evaluation framework. Signals to Python's import system that `research/eval/` is a package while documenting the framework's creation context.",
  "concepts": [
    "Soul Health Score",
    "SHS",
    "evaluation framework",
    "package structure",
    "7-dimension",
    "DimensionResult",
    "lazy import",
    "research package"
  ],
  "categories": [
    "evaluation",
    "package-structure",
    "soul-health-score"
  ],
  "source_docs": [
    "9a2e001a6c6357fb"
  ],
  "backlinks": null,
  "word_count": 301,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `research/eval/__init__.py` file is the entry point namespace for the Soul Health Score evaluation framework. While minimal in code content, it plays an important structural role: it declares `research.eval` as a Python package, enabling all sub-modules (`suite`, `report`, `llm_judge`, `dimensions/*`) to be imported using dotted paths.

## Why a Dedicated Eval Package?

Evaluation code is separated from the core `soul_protocol` library intentionally. Mixing evaluation harnesses with production code creates several failure modes:

- **Test dependencies leak into production**: eval uses heavyweight libraries and external LLM calls that should never run in production.
- **Circular import risk**: eval imports from `soul_protocol`; if `soul_protocol` imported from `eval`, cycles would break module initialization.
- **Deployment boundary**: the `research/` tree is never shipped in the published `soul_protocol` package. The package boundary enforces this separation.

## Framework Architecture Signal

The comment in this file—"7-dimension eval suite for measuring soul quality"—serves as the canonical description of what the eval package does. The seven dimensions correspond to the Soul Health Score (SHS) axes:

1. Memory Recall (D1, weight 20%)
2. Emotional Intelligence (D2, weight 20%)
3. Personality Expression (D3, weight 15%)
4. Bond / Relationship (D4, weight 15%)
5. Self-Model (D5, weight 15%)
6. Identity Continuity (D6, weight 10%)
7. Portability (D7, weight 5%)

Each dimension lives in `research/eval/dimensions/d{N}_{name}.py` and exports a single async `evaluate(seed, quick) -> DimensionResult` function.

## Package Initialization Pattern

Keeping `__init__.py` empty (aside from a comment) is a deliberate choice. Importing the package does not trigger any expensive dimension loading or LLM connections. The `suite.py` module uses lazy `importlib.import_module` calls to load dimension runners only when an evaluation actually runs, keeping import time fast.

## Known Gaps

No explicit `__all__` export list is defined, so `from research.eval import *` would export nothing. This is acceptable since all consumers import specific sub-modules directly.