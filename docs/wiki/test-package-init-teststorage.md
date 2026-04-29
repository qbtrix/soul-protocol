---
{
  "title": "Test Package Init: test_storage",
  "summary": "This is the package initializer for the `tests/test_storage/` directory, containing a minimal comment identifying the package. It enables pytest to discover storage backend tests and scopes them under a dedicated package namespace.",
  "concepts": [
    "test package",
    "pytest discovery",
    "package init",
    "storage backends",
    "InMemoryStorage",
    "FileStorage"
  ],
  "categories": [
    "testing",
    "test-infrastructure",
    "storage",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "3c5bfb6fd283823c"
  ],
  "backlinks": null,
  "word_count": 207,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The `tests/test_storage/__init__.py` file is a minimal Python package marker for the `test_storage/` directory. Unlike the fully empty `__init__.py` files in other test subdirectories, this one contains a single comment — `# test_storage package init` — which serves as a breadcrumb for maintainers browsing the directory structure.

## What Is in the test_storage Package?

This package contains tests for Soul Protocol's persistence backends. At present it covers:

- `InMemoryStorage`: a dict-backed in-process store for testing and ephemeral deployments.
- `FileStorage`: a filesystem-backed store that persists soul data as a directory of JSON files.

Both implement the same async storage protocol, allowing soul runtime code to switch backends without changing business logic.

## Why a Separate Package?

Storage tests often require `tmp_path` fixtures and can produce side effects on disk. Isolating them in a dedicated package:

- Allows selective runs: `pytest tests/test_storage/` for storage-specific CI jobs.
- Prevents `tmp_path`-related fixture names from colliding with memory or state test helpers.
- Makes it clear that persistent storage has its own coverage boundary, separate from in-memory spec tests.

## Known Gaps

- No shared fixtures are defined here. Each test file sets up its own `tmp_path` and `config` fixtures, which could be consolidated into this `__init__.py` in the future.