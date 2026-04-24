---
{
  "title": "DNA Subpackage Public API (Re-export Module)",
  "summary": "The `dna` subpackage `__init__.py` re-exports the two public functions from `dna/prompt.py` — `dna_to_system_prompt` and `dna_to_markdown` — providing a clean, stable import surface for consumers. This thin shim was fixed during a runtime restructure to use absolute import paths rooted at `soul_protocol.runtime`.",
  "concepts": [
    "DNA subpackage",
    "dna_to_system_prompt",
    "dna_to_markdown",
    "re-export",
    "public API",
    "soul personality",
    "package facade",
    "absolute imports"
  ],
  "categories": [
    "soul DNA",
    "package structure",
    "API surface"
  ],
  "source_docs": [
    "8ec22ebc3cda64f6"
  ],
  "backlinks": null,
  "word_count": 226,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `dna` subpackage encapsulates logic for converting a soul's DNA (personality blueprint) into human-readable and LLM-consumable text forms. The `__init__.py` serves purely as a re-export facade — it imports from the implementation module and exposes exactly what external code should use.

## Why a Separate Re-export Layer?

Directly importing from `soul_protocol.runtime.dna.prompt` works, but it exposes the internal module layout. If the implementation ever splits across multiple files (e.g., a dedicated `markdown.py` and a `system_prompt.py`), callers importing from `dna.prompt` would break. By routing through `__init__.py`, the internal layout can change without affecting consumers:

```python
from soul_protocol.runtime.dna import dna_to_system_prompt, dna_to_markdown
```

This is a conventional Python pattern for stable subpackage APIs.

## Exported Symbols

```python
from soul_protocol.runtime.dna.prompt import dna_to_markdown, dna_to_system_prompt

__all__ = ["dna_to_system_prompt", "dna_to_markdown"]
```

- **`dna_to_system_prompt`** — Converts identity, DNA, core memory, and current state into a multi-section system prompt suitable for an LLM.
- **`dna_to_markdown`** — Converts identity and DNA into a human-readable markdown document for export or debugging.

## History: Import Path Fix

The module comment notes that absolute import paths were fixed during a runtime restructure. Early versions used relative paths that broke when the package was installed as a dependency rather than run from source. Switching to `soul_protocol.runtime.dna.prompt` ensures correctness regardless of working directory or import context.

## Known Gaps

No TODOs or FIXMEs are present. The module is intentionally minimal.