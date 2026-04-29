---
{
  "title": "Test Package Init: Evolution Subsystem",
  "summary": "Empty package initialiser that makes `tests/test_evolution/` a proper Python package, enabling pytest to discover and import the evolution test modules correctly. No executable code is present; the file's value is purely structural.",
  "concepts": [
    "pytest",
    "package init",
    "test discovery",
    "evolution",
    "sub-package",
    "Python package"
  ],
  "categories": [
    "testing",
    "infrastructure",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "2ed3dad98393cdb9"
  ],
  "backlinks": null,
  "word_count": 140,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Python test directories must be packages (i.e. contain an `__init__.py`) when the project uses `src`-layout or when test modules need to import siblings. `tests/test_evolution/__init__.py` satisfies that requirement for the evolution test sub-package.

Without this file:
- `pytest` may fail to collect `test_evolution.py` on some configurations.
- Relative imports between test helpers inside the same sub-package would raise `ImportError`.

## Contents

The file is entirely empty (no imports, no fixtures, no constants). This is intentional — shared fixtures for the evolution suite are either inlined in `test_evolution.py` or live in the top-level `conftest.py`.

## Relationship to Other Files

| File | Role |
|---|---|
| `tests/test_evolution/__init__.py` | Package marker (this file) |
| `tests/test_evolution/test_evolution.py` | Actual test cases for `EvolutionManager` |

## Known Gaps

None. An empty `__init__.py` is the correct and complete implementation for a test sub-package marker.