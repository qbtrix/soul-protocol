---
{
  "title": "Eternal Storage Test Package Initializer",
  "summary": "Marks `tests/test_eternal/` as a Python package, enabling pytest discovery of the eternal storage subsystem's test modules. Created when the eternal storage subsystem was introduced on 2026-03-06.",
  "concepts": [
    "Python package",
    "__init__.py",
    "pytest discovery",
    "eternal storage",
    "test organization",
    "subsystem boundary"
  ],
  "categories": [
    "testing",
    "infrastructure",
    "eternal storage",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "16f349ee08c2fb56"
  ],
  "backlinks": null,
  "word_count": 231,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`tests/test_eternal/__init__.py` is a package marker file for the eternal storage test subdirectory. It contains no executable code and exists solely to make `tests/test_eternal/` a Python package, enabling pytest to discover and import test modules from within it.

## Why It Exists

Python's import system requires `__init__.py` files to treat directories as packages. Without it, pytest configurations that use the `importmode=prepend` or `importmode=auto` strategies would fail to resolve imports in test modules within the subdirectory, producing `ModuleNotFoundError` at collection time.

## Subsystem Context

The `test_eternal/` package groups tests for the **eternal storage subsystem** — the component responsible for archiving soul files to permanent decentralized storage backends (IPFS, Arweave, blockchain, and local fallback). This subsystem was introduced on 2026-03-06 as a distinct module separate from the runtime layer, hence its own test subdirectory.

The subdirectory contains:

```
tests/test_eternal/
    __init__.py              ← this file
    test_cli_eternal.py      ← CLI command tests (archive, recover, eternal-status)
    test_e2e_eternal.py      ← end-to-end lifecycle tests
    test_manager.py          ← EternalStorageManager unit tests
    test_protocol.py         ← protocol compliance tests
    test_providers.py        ← per-provider tests (IPFS, Arweave, Blockchain, Local)
    test_soul_eternal.py     ← Soul + eternal integration tests
```

## Relationship to Source Layout

The test package mirrors `soul_protocol/runtime/eternal/` in the source tree, making it easy to find which tests cover which implementation files. This symmetry is a deliberate convention in the soul-protocol project.

## Known Gaps

None. This is a standard package marker with no logic to maintain.
