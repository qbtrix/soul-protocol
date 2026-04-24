---
{
  "title": "SoulFactory: Template-Driven Soul Creation and Batch Spawning",
  "summary": "`SoulFactory` creates souls from `SoulTemplate` blueprints via `from_template()` (single soul) and `batch_spawn()` (N souls with controlled OCEAN personality variance). Both methods propagate `default_scope` from template metadata into seeded core memories, enabling RBAC/ABAC recall filtering on freshly created souls.",
  "concepts": [
    "SoulFactory",
    "SoulTemplate",
    "from_template",
    "batch_spawn",
    "OCEAN variance",
    "personality variance",
    "default_scope",
    "core memories",
    "skills registration",
    "bundled templates",
    "lazy import"
  ],
  "categories": [
    "runtime",
    "templates",
    "soul creation"
  ],
  "source_docs": [
    "e7ba3406c1653dca"
  ],
  "backlinks": null,
  "word_count": 407,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`SoulFactory` solves the bootstrapping problem: how do you create many souls with consistent personalities, skills, and core memories without manually calling `Soul.birth()` for each one? Templates encode the blueprint; the factory instantiates it.

## Loading Templates

Templates can be loaded from files or from the bundled catalog:

```python
# From a YAML or JSON file
template = SoulFactory.load_template("my-template.yaml")

# From the bundled catalog (arrow, flash, cyborg, analyst)
template = SoulFactory.load_bundled("arrow")
```

`load_template()` raises `FileNotFoundError` for missing files and `pydantic.ValidationError` for malformed payloads — callers see the offending field clearly rather than a generic parse error. YAML support requires PyYAML; the error message tells the user exactly which extra to install.

## Creating a Single Soul

```python
soul = await SoulFactory.from_template(template, name="Aria")
```

`from_template()` calls `Soul.birth()` with the template's personality and archetype, then:

1. Seeds core memories from `template.core_memories` at importance 9.
2. Registers skills from `template.skills`.
3. Propagates `template.metadata["default_scope"]` into each seeded memory.

The lazy import of `Soul` (`from soul_protocol.runtime.soul import Soul`) inside the method body breaks the circular dependency that would arise from a top-level import (soul → templates → soul).

## Batch Spawning with Controlled Variance

```python
souls = await SoulFactory.batch_spawn(template, count=50, rng_seed=42)
```

Each spawned soul gets:

- A unique name from `name_pattern` (default: `"{prefix}{index:03d}"`)
- A unique DID from `Soul.birth()`
- OCEAN traits varied within `±template.personality_variance`

Variance is drawn from a seeded `random.Random` instance, making batches reproducible. This is critical for testing and for multi-agent environments where the same batch must be recreated identically across deployments.

```python
varied_ocean = {}
for trait, base_val in base_ocean.items():
    delta = rng.uniform(-variance, variance)
    varied_ocean[trait] = max(0.0, min(1.0, base_val + delta))
```

Traits are clamped to `[0.0, 1.0]` after applying variance to prevent invalid OCEAN values.

## Scope Propagation (Move 5)

Both `from_template` and `batch_spawn` propagate `template.metadata["default_scope"]` into seeded core memories:

```python
default_scope = template.metadata.get("default_scope")
if isinstance(default_scope, str):
    default_scope = [default_scope]
```

This means an org-scoped template (e.g., `default_scope: "org:sales:*"`) automatically tags all seeded memories with the correct RBAC scope. Without this, a freshly spawned soul would have unscoped memories that bypass access controls until explicitly tagged.

## Template Registration

`SoulFactory` instances also support a registry (`register`, `list_templates`, `get`) for managing templates at runtime. This is useful for multi-template pipelines where different roles use different blueprints.

## Known Gaps

`batch_spawn` does not parallelize soul creation with `asyncio.gather()` — souls are created sequentially in a for loop. For large batches (N > 100), this is noticeably slow.