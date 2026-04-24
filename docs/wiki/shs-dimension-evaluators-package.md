---
{
  "title": "SHS Dimension Evaluators Package",
  "summary": "Package marker for the `research/eval/dimensions/` directory, which houses the seven individual Soul Health Score dimension evaluators. Each sub-module implements one evaluation axis of soul quality.",
  "concepts": [
    "dimensions package",
    "DimensionResult",
    "lazy loading",
    "importlib",
    "eval convention",
    "d1-d7",
    "Soul Health Score axes"
  ],
  "categories": [
    "evaluation",
    "package-structure",
    "soul-health-score"
  ],
  "source_docs": [
    "75da817829db853a"
  ],
  "backlinks": null,
  "word_count": 258,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`research/eval/dimensions/__init__.py` declares the `dimensions` sub-package within the eval framework. Like the parent `__init__.py`, it is intentionally empty aside from a comment, acting purely as a namespace boundary.

## Package Role

The dimensions package contains seven modules, each following the naming convention `d{N}_{name}.py`:

| Module | Dimension | Weight |
|--------|-----------|--------|
| `d1_memory.py` | Memory Recall | 20% |
| `d2_emotion.py` | Emotional Intelligence | 20% |
| `d3_personality.py` | Personality Expression | 15% |
| `d4_bond.py` | Bond / Relationship | 15% |
| `d5_self_model.py` | Self-Model | 15% |
| `d6_continuity.py` | Identity Continuity | 10% |
| `d7_portability.py` | Portability | 5% |

Each module exports a single `async evaluate(seed: int, quick: bool) -> DimensionResult` function. This uniform interface allows the suite runner to discover and invoke all evaluators dynamically via `importlib.import_module`.

## Why Lazy Loading Matters

The suite uses `importlib.import_module` rather than static imports for each dimension. This prevents a dimension with a broken dependency from blocking the entire eval run. If `d2_emotion.py` fails to import (e.g., a missing corpus file), only D2 is skipped—the other six dimensions still execute and produce results.

## Design Constraint

All dimensions must be stateless at import time. No dimension module should execute code at module level that makes network calls, opens files, or instantiates souls. All heavy operations are deferred to the `evaluate()` function call.

## Known Gaps

No `__all__` list is defined. The package relies on the naming convention (`d{N}_`) for discovery rather than explicit registration, which means a misnamed file would be silently ignored.