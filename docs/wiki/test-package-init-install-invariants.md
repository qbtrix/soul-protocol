---
{
  "title": "Test Package Init: Install Invariants",
  "summary": "Package initialiser for `tests/test_install/`, the sub-package that verifies install-time invariants such as the CLI being functional after a bare `pip install soul-protocol`. Created to address issue #157.",
  "concepts": [
    "pytest",
    "package init",
    "install invariants",
    "issue #157",
    "pip install",
    "CLI entry point",
    "dependencies",
    "soul-protocol"
  ],
  "categories": [
    "testing",
    "infrastructure",
    "install",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "b19d433441ed22cd"
  ],
  "backlinks": null,
  "word_count": 157,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`tests/test_install/__init__.py` designates the `test_install` directory as a Python package so pytest can discover and import `test_base_install.py` and any future install-verification tests.

The file contains a brief comment identifying its creation date (2026-04-14) and linking to issue #157, which reported that a bare `pip install soul-protocol` produced a broken CLI entry point. The comment serves as provenance — future contributors can trace the test package back to the specific incident that motivated it.

## Context: Issue #157

Before the fix, CLI dependencies (`click`, `rich`, `pyyaml`, `cryptography`) were incorrectly placed behind optional extras rather than base dependencies. A user running `pip install soul-protocol` then `soul --help` would get an `ImportError` instead of the help text. The `test_install` sub-package was created to prevent regression.

## Contents

Only the comment header — no imports, no fixtures, no shared code. Individual test modules in this package are self-contained.

## Known Gaps

None. This is a correct and minimal package marker.