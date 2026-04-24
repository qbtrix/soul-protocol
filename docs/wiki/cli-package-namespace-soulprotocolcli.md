---
{
  "title": "CLI Package Namespace — `soul_protocol.cli`",
  "summary": "An intentionally empty package initialiser that establishes `soul_protocol.cli` as a Python package namespace. Its sole function is structural: making the directory importable so that `cli.main`, `cli.inject`, `cli.org`, and `cli.setup` are discoverable.",
  "concepts": [
    "CLI package",
    "__init__.py",
    "namespace package",
    "Python package structure",
    "soul_protocol.cli",
    "Click entry points"
  ],
  "categories": [
    "package-structure",
    "cli"
  ],
  "source_docs": [
    "cb79d8c84dcfca14"
  ],
  "backlinks": null,
  "word_count": 440,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`src/soul_protocol/cli/__init__.py` is an intentionally empty package initialiser created on 2026-02-22. It contains a single header comment and no executable code. Its sole function is to make `soul_protocol.cli` a proper Python package so that its submodules are importable.

## Why It Exists

Python requires an `__init__.py` file in any directory intended as a package. Without it, `cli/` is just a plain directory — Python would not allow `from soul_protocol.cli.main import cli` or `import soul_protocol.cli.org`. The `__init__.py` signals to the import machinery that `cli/` is a namespace under `soul_protocol`.

This is especially important for Click-based CLI tools, where entry points declared in `pyproject.toml` must reference a dotted module path:

```toml
[project.scripts]
soul = "soul_protocol.cli.main:cli"
```

If `cli/` were not a package, this entry point declaration would fail at install time.

## Why It Is Empty

Keeping `__init__.py` empty rather than re-exporting CLI symbols is a deliberate design choice for two reasons:

1. **The CLI is not a library API.** Consumer code should never `import soul_protocol.cli` for its types or functions. The public API lives in `soul_protocol.__init__` (the package root). Adding re-exports here would suggest that `soul_protocol.cli` is a stable, versioned import surface — which it is not.

2. **Click entry points are the access layer.** The `soul` command is wired up through `pyproject.toml` scripts, not through Python imports. The Click group in `main.py` is the root of the CLI graph; nothing needs to import it programmatically.

## Package Structure

```
src/soul_protocol/cli/
├── __init__.py    ← this file (package marker, no exports)
├── main.py        ← 40+ CLI subcommands (soul init, soul recall, ...)
├── inject.py      ← soul context injection into agent config files
├── org.py         ← org-layer commands (soul org init, soul org destroy)
└── setup.py       ← platform detection and MCP server wiring
```

Each submodule has a distinct responsibility:

| Module | Responsibility |
|--------|---------------|
| `main.py` | Full CLI surface, user-facing commands |
| `inject.py` | Writing soul context blocks to config files |
| `org.py` | Multi-soul org lifecycle management |
| `setup.py` | Agent platform auto-detection and MCP config |

## Testing Implications

Because `__init__.py` is empty, test files can import individual submodules directly without pulling in any CLI state:

```python
from soul_protocol.cli.inject import inject_context_block, resolve_target_path
from soul_protocol.cli.setup import detect_platforms, get_platforms
```

This is preferable to importing through the package root (which would also be a no-op here, but signals intent).

## Known Gaps

None. If future work needs to share helper utilities across multiple CLI modules, the recommended pattern is to create a `_utils.py` alongside this file — not to add exports to `__init__.py`, which would blur the boundary between the CLI implementation and the public API.
