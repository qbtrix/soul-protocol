---
{
  "title": "Core Memory Manager — Always-In-Context Identity Block",
  "summary": "Manages the ~2KB core memory block that stays loaded in context at all times. It holds two editable sections — `persona` (the soul's own identity) and `human` (profile of the bonded human) — with distinct `set`, `edit`, and `append` operations.",
  "concepts": [
    "core memory",
    "persona",
    "human profile",
    "always-in-context",
    "CoreMemoryManager",
    "CoreMemory",
    "memory budget",
    "set vs append",
    "Bug #15",
    "context injection"
  ],
  "categories": [
    "memory",
    "identity",
    "soul-protocol-core"
  ],
  "source_docs": [
    "b9a22f40d504e0ec"
  ],
  "backlinks": null,
  "word_count": 319,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## What is Core Memory?

In the Soul Protocol memory architecture, core memory is the always-present context block — the soul's minimum viable identity. It is not retrieved by search; it is injected into every LLM prompt unconditionally. The 2KB budget reflects practical LLM context constraints: enough for a rich persona and basic human profile, small enough to not crowd out conversation history.

## Two Sections

- **persona** — Who is the soul? Its role, personality description, communication style, and backstory live here.
- **human** — Who is the human? Name, preferences, and relationship context the soul should always remember.

## Operations

`CoreMemoryManager` wraps a `CoreMemory` Pydantic model and exposes four operations:

| Method | Behavior |
|---|---|
| `get()` | Return the current `CoreMemory` model |
| `set(persona, human)` | Replace fields entirely (None = leave unchanged) |
| `edit(persona, human)` | Alias for `set()` — replaces values |
| `append(persona, human)` | Append to existing values with newline separator |

## The Bug That Created append()

Before v0.2.0 (Bug #15 fix, 2026-03-06), `edit()` would *append* to existing values rather than replace them. The fix made `edit()` a true replacement. To preserve the old behavior for callers that needed incremental updates, `append()` was introduced as an explicit method.

This distinction matters: a soul migrated from an old version that calls `edit()` expecting replacement will now get replacement — the breaking behavior was the old append-on-edit.

## Integration Context

`CoreMemoryManager` is held by `MemoryManager` and exposed via `soul.get_core_memory()`. When generating a prompt, the runtime injects `core.persona` and `core.human` into the system prompt header, then appends retrieved memories from episodic, semantic, and procedural stores.

## Known Gaps

- There is no size enforcement — callers can set a 10KB persona string and the system will not reject it, silently exceeding the intended 2KB budget.
- `edit()` is functionally identical to `set()`. The duplication exists for API compat but adds confusion.