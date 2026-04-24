---
{
  "title": "Test Suite for Base Install Invariants (Issue #157)",
  "summary": "Regression tests that verify a bare `pip install soul-protocol` produces a working CLI, by checking that click, rich, pyyaml, and cryptography are declared as base dependencies, the deprecated `[engine]` extra still exists for backwards compatibility, and the CLI module imports cleanly without optional extras.",
  "concepts": [
    "issue #157",
    "base dependencies",
    "optional extras",
    "click",
    "rich",
    "pyyaml",
    "cryptography",
    "engine extra",
    "backwards compatibility",
    "CLI entry point",
    "pyproject.toml",
    "tomllib",
    "importlib",
    "pip install"
  ],
  "categories": [
    "testing",
    "install",
    "dependencies",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "0f6ffbf1617d4fd9"
  ],
  "backlinks": null,
  "word_count": 366,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Issue #157 reported that `soul --help` failed with `ImportError` after a plain `pip install soul-protocol` because CLI-required packages were behind optional extras. `test_base_install.py` is the regression suite that prevents this class of bug from recurring.

## Architecture

The tests drive directly from `pyproject.toml` via `tomllib`:

```python
PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

def _load_pyproject() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)
```

This approach avoids testing a stale in-memory state — it reads the canonical source of truth for package metadata.

## Test 1: CLI Deps in Base

```python
def test_cli_required_deps_are_in_base():
    """click, rich, pyyaml, cryptography must be in [project].dependencies."""
    ...
```

Asserts that each of the four packages appears in `[project].dependencies` (not `[project.optional-dependencies]`). The error message names issue #157 explicitly so a future failure immediately points to the root cause.

## Test 2: Engine Extra Preserved

```python
def test_engine_extra_preserved_for_backwards_compat():
    """The `[engine]` extra must still exist so old pins keep resolving."""
    ...
```

When the engine dependencies were moved to base, keeping the `[engine]` extra as an empty list ensures that `requirements.txt` files pinning `soul-protocol[engine]` do not break. Without this test, a well-intentioned cleanup could delete the extra and break dependent projects silently.

## Test 3: CLI Module Importable

```python
def test_cli_module_imports_without_optional_extras():
    """`soul_protocol.cli.main` must import with only base deps present."""
    assert importlib.util.find_spec("soul_protocol.cli.main") is not None
    module = importlib.import_module("soul_protocol.cli.main")
    assert hasattr(module, "cli")
```

This is the end-to-end smoke test: actually importing the CLI module in the test process. If any of the four base deps were re-placed behind an optional extra, this import would raise `ImportError`, reproducing the original #157 bug directly.

Checking `hasattr(module, "cli")` confirms the entry point is defined, not just that the module loads without error.

## Data Flow

```
pyproject.toml
    ↓ tomllib.load()
[project].dependencies  →  assert click, rich, pyyaml, cryptography present
[project.optional-dependencies]  →  assert "engine" key present
    ↓ importlib.import_module()
soul_protocol.cli.main  →  assert "cli" attribute exists
```

## Known Gaps

- Tests run in the current environment, which likely already has the packages installed. They do not simulate a true bare install in an empty venv — that would require a subprocess test creating a fresh environment.
- The `[engine]` extra content is not validated (it may be empty), only its existence is checked.