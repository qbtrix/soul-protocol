---
{
  "title": "Research Package Entry Point (`python -m research`)",
  "summary": "A minimal `__main__.py` that enables the research package to be invoked directly with `python -m research`, delegating immediately to `research.run.main()`. This is the standard Python idiom for making a package executable without requiring the user to know the internal module structure.",
  "concepts": [
    "__main__.py",
    "python -m",
    "package entry point",
    "research.run",
    "delegation pattern",
    "CLI entry point",
    "module execution",
    "experiment runner"
  ],
  "categories": [
    "research",
    "infrastructure",
    "CLI",
    "soul-protocol"
  ],
  "source_docs": [
    "91760dfeaaec25a5"
  ],
  "backlinks": null,
  "word_count": 310,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`research/__main__.py` is a single-purpose entry point file. Its entire content is:

```python
# __main__.py — Enables `python -m research.run` invocation.
from .run import main

main()
```

## Why This File Exists

Python's `-m` flag runs a module or package as a script. When applied to a package (`python -m research`), Python looks for `__main__.py` inside the package directory and executes it. Without this file, `python -m research` raises `No module named research.__main__; 'research' is a package and cannot be directly executed`.

The file's value is ergonomic — it gives users a single, memorable command to run the experiment rather than requiring them to know that the entry point lives in `research.run`:

```bash
# With __main__.py:
python -m research

# Without __main__.py (requires knowing internal structure):
python -m research.run
```

## Delegation Pattern

Rather than putting experiment logic directly in `__main__.py`, the file delegates to `research.run.main()`. This is standard practice for two reasons:

1. **Testability** — `research.run.main()` can be imported and called in tests without triggering the `__main__` execution path
2. **Import hygiene** — code in `__main__.py` runs at import time when the package is used as a module, but `run.main()` is protected by being a named function

## Data Flow

```
python -m research
  → Python executes research/__main__.py
  → imports main from research.run
  → calls main()
  → experiment runs: agents generated → conditions applied → metrics collected → report written
```

## Known Gaps

- No argument parsing or `--help` is shown at this level — any CLI flags must be handled inside `research.run.main()`. If the experiment grows to support sub-commands (e.g., `python -m research analyze`, `python -m research run`), this entry point will need to be expanded with a dispatcher.
- The comment says `python -m research.run` but the correct invocation is `python -m research` (the package), since this file is `__main__.py`. The docstring is slightly misleading.