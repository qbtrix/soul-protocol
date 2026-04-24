---
{
  "title": "Test Suite for the Spec Sub-Package",
  "summary": "The `tests/spec/__init__.py` file marks the `tests/spec/` directory as a Python package, enabling pytest to discover and correctly import the spec-level test modules it contains. This is a structural init with no executable code.",
  "concepts": [
    "spec tests",
    "test sub-package",
    "pytest discovery",
    "protocol conformance",
    "spec isolation"
  ],
  "categories": [
    "testing",
    "project-structure",
    "test"
  ],
  "source_docs": [
    "e3b0c44298fc1c14"
  ],
  "backlinks": null,
  "word_count": 169,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The `tests/spec/` sub-package groups tests that target `soul_protocol.spec.*` — the standard's data models and Protocols — separately from tests that target `soul_protocol.runtime.*`. This separation makes the distinction between spec conformance tests and runtime behavior tests visible at the directory level.

## Why It Matters

The `soul_protocol.spec` package defines the contracts that third-party implementations must satisfy: Pydantic models, runtime-checkable Protocols, and vocabulary types. Tests in `tests/spec/` verify these contracts in isolation, without importing any runtime machinery. This means:

- Spec tests can pass even when runtime components have bugs
- Third-party implementors can copy `tests/spec/` into their own repo as a conformance suite
- CI can fail fast on spec-level regressions before running slower integration tests

## Package Structure

```
tests/spec/
    __init__.py          # this file — makes spec/ a package
    test_retrieval.py    # spec-level tests for retrieval vocabulary
```

More spec test modules are expected here as the spec surface grows (memory, journal, template, scope).

## Known Gaps

None. This is a structural file with a single well-understood responsibility.