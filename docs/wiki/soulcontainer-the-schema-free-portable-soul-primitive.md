---
{
  "title": "SoulContainer: The Schema-Free Portable Soul Primitive",
  "summary": "`SoulContainer` is the core-layer primitive introduced in v0.4.0 — a schema-free portable AI identity that holds an `Identity` and a `MemoryStore` with no opinions about personality models, cognitive engines, or evolution systems. It supports a `create`/`open`/`save` lifecycle for `.soul` file archives.",
  "concepts": [
    "SoulContainer",
    "Identity",
    "MemoryStore",
    "schema-free",
    "portable soul",
    "soul file",
    "pack_soul",
    "unpack_to_container",
    "create",
    "open",
    "save",
    "core layer"
  ],
  "categories": [
    "spec",
    "core primitives",
    "portability"
  ],
  "source_docs": [
    "1ba277b5b64b4a6e"
  ],
  "backlinks": null,
  "word_count": 491,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`SoulContainer` is the minimal building block of Soul Protocol — the equivalent of a raw TCP connection before application-level framing. Introduced in v0.4.0, it holds exactly two things: an `Identity` and a `MemoryStore`. Everything else — OCEAN personality, biorhythms, evolution systems, cognitive engines — belongs to higher layers.

This separation was introduced to make the core layer usable by consumers that do not need the full runtime stack: thin agents, browser extensions, mobile SDKs, or tools that only need to read a soul's identity and recent memories.

## Lifecycle: Create, Open, Save

### Creating a New Soul

```python
soul = SoulContainer.create("Aria", traits={"role": "assistant", "openness": 0.8})
```

`traits` is a schema-free `dict[str, Any]`. No OCEAN model is required at this layer. The container does not validate trait keys or types — that is the runtime's responsibility. This allows consumers to encode any key-value metadata without conforming to a specific personality schema.

### Opening an Existing Soul

```python
soul = SoulContainer.open("aria.soul")
```

Raises `FileNotFoundError` if the path does not exist and `ValueError` if the file is not a valid `.soul` archive. These are explicit errors rather than silent `None` returns — a missing soul file is always a caller error, not an expected condition.

### Saving to a .soul File

```python
soul.save("aria.soul")
```

Writes a `.soul` zip archive using `pack_soul()`. Overwrites any existing file at the path. The caller is responsible for choosing the destination — no default path is assumed.

## Properties

```python
soul.identity    # Identity object — DID, name, traits, bonds
soul.memory      # MemoryStore — the soul's memory backend
soul.name        # convenience: identity.name
soul.id          # convenience: identity.id
```

The `memory` property returns the `MemoryStore` interface, which defaults to `DictMemoryStore()` if no store was provided at construction. Callers can replace it with any `MemoryStore`-compatible implementation.

## Why Schema-Free

The runtime `SoulConfig` (in `types.py`) enforces a specific personality model and requires all fields to be present. `SoulContainer` does not. This design lets:

- Non-Python runtimes construct valid souls without implementing the OCEAN model.
- Spec-layer consumers read and write souls portably across language boundaries.
- Future spec versions add optional fields without breaking existing containers.
- Lightweight tools (e.g., a soul browser or an import utility) work with `.soul` files without pulling in the full runtime dependency tree.

## Memory Operations

```python
from soul_protocol.spec.memory import MemoryEntry, MemoryType

soul.memory.store("episodic", MemoryEntry(
    type=MemoryType.EPISODIC,
    content="User mentioned they prefer morning meetings.",
    importance=6
))
memories = soul.memory.recall("episodic", limit=10)
```

The default `DictMemoryStore` keeps memories in memory for the lifetime of the container instance.

## Relationship to the Runtime Soul

The runtime `Soul` class wraps `SoulConfig`, not `SoulContainer`. The two layers coexist:
- `SoulContainer` — portable, headless, spec-layer; for reading, writing, and migrating souls.
- `Soul` — full-featured runtime; for cognition, evolution, and interaction processing.

## Known Gaps

No conversion utility exists between `SoulContainer` and the runtime `Soul`/`SoulConfig`. Callers that want to upgrade a container to a full runtime soul must manually map fields between the two schemas.