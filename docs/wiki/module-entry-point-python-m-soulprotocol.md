---
{
  "title": "Module Entry Point — `python -m soul_protocol`",
  "summary": "A minimal `__main__.py` that enables running soul-protocol as a module with `python -m soul_protocol`, delegating immediately to the interactive demo. The `__name__` guard prevents accidental execution on import.",
  "concepts": [
    "__main__.py",
    "module entry point",
    "python -m",
    "demo",
    "CLI entry point",
    "name guard",
    "package invocation"
  ],
  "categories": [
    "package-structure",
    "developer-tools"
  ],
  "source_docs": [
    "2cc9ef9039d6a5a4"
  ],
  "backlinks": null,
  "word_count": 435,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`src/soul_protocol/__main__.py` is a two-line entry point that Python executes when the package is invoked with the `-m` flag:

```bash
python -m soul_protocol
```

It imports `main` from `soul_protocol.demo` and calls it inside a standard `if __name__ == "__main__"` guard.

## Why It Exists

Without `__main__.py`, users would need to know the internal module path (`python -m soul_protocol.demo`) to run the demo. Python's `-m` invocation looks specifically for a `__main__.py` at the package root. The `__main__.py` convention provides a discoverable, stable invocation surface that works regardless of how the internal module structure evolves.

This matters for first-run experience: new users who clone the repository can immediately run `python -m soul_protocol` to see a live demo without reading the docs. The module entry point is one of the first things mentioned in the README.

## The `__name__` Guard

The `if __name__ == "__main__"` guard (added 2026-03-12) prevents `main()` from executing if `__main__.py` is accidentally imported as a module rather than executed as a script. This can happen with:

- Certain test runners that import all modules in a package to collect tests
- Import tracers and analysis tools (e.g., `mypy --strict`, `vulture`)
- Recursive import patterns where a module transitively imports from the package root

Without the guard, any tool that does `import soul_protocol.__main__` would trigger the full interactive demo at import time — hanging in a `Rich` TTY prompt or writing to stdout unexpectedly.

## Data Flow

```
python -m soul_protocol
        │
        ▼
__main__.py (Python loads automatically)
        │
        ▼
from soul_protocol.demo import main
        │
        ▼
main()  →  asyncio.run(run_demo())
        │
        ▼
Rich TUI: 5-act interactive walkthrough
```

## Relationship to the CLI

`python -m soul_protocol` runs the **demo**, not the production CLI. The CLI is accessed via the `soul` entry point declared in `pyproject.toml`:

```toml
[project.scripts]
soul = "soul_protocol.cli.main:cli"
```

These are intentionally separate surfaces:

| Invocation | Target | Audience |
|------------|--------|----------|
| `soul --help` | `cli/main.py` | Everyday users |
| `python -m soul_protocol` | `demo.py` | First-time explorers |
| `uv run soul_protocol` | same as above | Development workflows |

## Versioning Consideration

Because `__main__.py` delegates entirely to `demo.py`, changes to the demo (new acts, different conversations, Rich styling updates) do not require any change here. This separation keeps the entry point stable across demo rewrites.

## Known Gaps

None. This file is intentionally minimal — any logic added here would be better placed in `demo.py` where it can be tested independently via direct function calls. The only acceptable change to this file would be switching the demo target (e.g., pointing to a different demo module for a future v2 walkthrough).
