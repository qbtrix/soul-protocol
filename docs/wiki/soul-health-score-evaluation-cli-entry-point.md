---
{
  "title": "Soul Health Score Evaluation CLI Entry Point",
  "summary": "Thin `__main__.py` that enables `python -m research.eval.suite` as a runnable command by delegating immediately to `suite.main()`. Provides zero additional logic, keeping the entry point surface minimal.",
  "concepts": [
    "__main__.py",
    "CLI entry point",
    "python -m",
    "module runner",
    "eval suite",
    "argparse delegation"
  ],
  "categories": [
    "evaluation",
    "cli",
    "package-structure"
  ],
  "source_docs": [
    "bbbcef7292c3a682"
  ],
  "backlinks": null,
  "word_count": 208,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`research/eval/__main__.py` is the Python module entry point that makes `python -m research.eval` work as a command. Without this file, Python would refuse to execute the package with the `-m` flag, requiring users to call the full module path (`python -m research.eval.suite`) instead.

The entire file contains two lines:

```python
from research.eval.suite import main
main()
```

## Why This Pattern?

Separating the entry point from the logic is a well-established Python convention. The benefits:

1. **Testability**: `suite.main()` can be called from tests without triggering `if __name__ == "__main__"` guards.
2. **Import safety**: the `__main__.py` only runs when the package is invoked directly—not on `import research.eval`.
3. **Flexibility**: if the primary CLI entry point ever changes to a different function or module, only `__main__.py` needs updating.

## Invocation

Users run the evaluation suite through the suite module directly:

```bash
python -m research.eval.suite --quick --dimensions 1 2 3
python -m research.eval.suite --seed 99 --dashboard
```

The `__main__.py` enables a shorter alias: `python -m research.eval` would also work if `__main__.py` were at the package root (but the suite's own `__main__.py` at `research/eval/__main__.py` handles the `python -m research.eval` invocation).

## Known Gaps

No argument forwarding or signal handling is done here. Any `SystemExit` from argparse propagates cleanly, which is correct behavior.