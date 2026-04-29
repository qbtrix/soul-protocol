---
{
  "title": "Spike Namespace: In-Progress Design Experiments",
  "summary": "The `spike/` package is a dedicated quarantine zone for experimental code that is under active design validation but not yet ready for the public API. It exists to allow risky ideas to be tested inside the full suite without any risk of accidental consumer imports.",
  "concepts": [
    "spike namespace",
    "experimental code",
    "API segregation",
    "design validation",
    "promotion lifecycle",
    "package isolation",
    "XP spike",
    "in-tree experiments"
  ],
  "categories": [
    "architecture",
    "development-process"
  ],
  "source_docs": [
    "7e33ced9492bea3a"
  ],
  "backlinks": null,
  "word_count": 413,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The `soul_protocol.spike` package is a deliberate sandbox within the source tree. Code lands here when the design thesis is still being validated — the implementation works well enough to test, but the API contract is not yet stable enough to expose as part of the shipped library.

This segregation solves a real operational problem: advanced features need to run against the complete test suite (to catch regressions they might cause in existing code) without being importable by library consumers. A consumer who accidentally depends on spike code would break when that code is promoted or deleted.

## Design Pattern

The module docstring says exactly one thing: `"Spike-only code. Not part of the public API."` This is intentional bluntness. There are no re-exports, no `__all__`, and no facade that might tempt a consumer to import from it.

The naming convention follows XP/agile "spike" terminology — a time-boxed experiment to answer a specific technical question. In this project, spikes graduate to `runtime/` once the design thesis validates.

## Promotion Lifecycle

The header comment documents the expected lifecycle:

```
Spike created in feature branch
        ↓
Runs in full test suite (catches integration issues early)
        ↓
Design validates against benchmarks / docs/memory-journal-spike.md
        ↓
Code promoted to runtime/
        ↓
Spike module deleted
```

This means the `spike/` directory is intentionally temporary. Any module here should have a companion design document in `docs/` that describes what question it is answering and what the acceptance criteria for promotion look like.

## Why Keep It In-Tree?

Alternatives — a separate repo, a local branch, a scratch file — all share the same flaw: they do not run in CI. By living in-tree, spike code:

- Gets caught by pre-commit hooks and lint rules immediately
- Can import from `soul_protocol.*` without path hacks
- Appears in coverage reports, revealing whether it is actually being tested
- Is visible to the full team via normal code review

The cost is a small amount of cognitive overhead when reading the package listing. The benefit is that design experiments are grounded in real behavior, not imaginary behavior.

## Known Gaps

- There is no automated check that prevents `soul_protocol.spike` from being imported in non-spike test files. A future lint rule (e.g., a custom ruff plugin) could enforce this boundary statically.
- The graduation process (promoting a spike to `runtime/`) is currently manual and undocumented as a checklist. The design document referenced in the header (`docs/memory-journal-spike.md`) describes one instance but not a generalized process.