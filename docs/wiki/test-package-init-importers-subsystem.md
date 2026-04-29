---
{
  "title": "Test Package Init: Importers Subsystem",
  "summary": "Empty package initialiser that designates `tests/test_importers/` as a Python package, enabling pytest to collect the importer-specific test modules contained within. No executable code is present.",
  "concepts": [
    "pytest",
    "package init",
    "test discovery",
    "importers",
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
    "e3b0c44298fc1c14"
  ],
  "backlinks": null,
  "word_count": 146,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`tests/test_importers/__init__.py` is a structural file that declares the `test_importers` directory as a Python package. This is required for pytest to correctly discover and import test modules within the subdirectory under certain project layouts.

Without this file, pytest may silently skip the importer tests (`test_detect_format.py`, `test_soulspec.py`, `test_tavernai.py`) depending on the `rootdir` and `pythonpath` configuration.

## Contents

The file is completely empty — no imports, no fixtures, no shared utilities. Any shared test helpers for the importer suite are either co-located in individual test modules or live in the top-level `conftest.py`.

## Test Modules in This Package

| Module | Scope |
|---|---|
| `test_detect_format.py` | Auto-detection of soul character format |
| `test_soulspec.py` | SoulSpec directory import/export |
| `test_tavernai.py` | TavernAI Character Card V2 import/export |

## Known Gaps

None. An empty package init is the standard and complete pattern for a pytest sub-package.