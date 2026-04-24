---
{
  "title": "Test Suite: Soul Templates and Batch Spawning via SoulFactory",
  "summary": "Validates `SoulTemplate` (reusable soul blueprints with personality profiles, memories, and skills) and `SoulFactory` (the factory that instantiates souls from templates, including batch spawning with controlled personality variance). The suite covers model validation, override semantics, variance clamping, reproducible seeding, and public API exports.",
  "concepts": [
    "SoulTemplate",
    "SoulFactory",
    "batch_spawn",
    "personality_variance",
    "rng_seed",
    "from_template",
    "name_prefix",
    "name_pattern",
    "core_memories",
    "skills registration",
    "unique DID",
    "MemoryVisibility",
    "public API exports"
  ],
  "categories": [
    "testing",
    "soul factory",
    "batch operations",
    "templates",
    "test"
  ],
  "source_docs": [
    "bc0a036822f61835"
  ],
  "backlinks": null,
  "word_count": 520,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Templates solve the problem of deploying many similar souls — a fleet of customer service agents, a cohort of research assistants — without manually configuring each one. `SoulTemplate` is a Pydantic model that defines a soul's default configuration. `SoulFactory.from_template()` instantiates one soul from a template; `SoulFactory.batch_spawn()` creates N souls with controlled personality variation.

## SoulTemplate Model

Minimal construction only requires `name`:

```python
t = SoulTemplate(name="test")
assert t.archetype == "assistant"
assert t.personality == {}
assert t.personality_variance == 0.1  # default 10% variance
assert t.name_prefix == ""
```

Personality variance is clamped to `[0.0, 0.5]` by Pydantic validation:
```python
with pytest.raises(Exception):  # ValidationError
    SoulTemplate(name="t", personality_variance=0.6)
```

The upper bound of 0.5 prevents spawned souls from having personality values that bear no resemblance to the template — a variance of 0.5 on a base of 0.5 could produce values from 0.0 to 1.0, covering the full range. Both JSON and Pydantic `model_dump` round-trips are tested to ensure the template is portable.

## SoulFactory.from_template()

```python
t = SoulTemplate(name="Template")
soul = await SoulFactory.from_template(t, name="CustomName")
assert soul.name == "CustomName"  # override wins
```

Keyword overrides take precedence over template values, allowing one template to serve as a base with per-instance customizations. Each `from_template()` call generates a unique DID even for the same template — preventing identity collisions in fleets.

- Core memories from the template are stored in the soul's memory at birth (tested via `soul.recall()`)
- Skills from the template are registered in the skill registry
- Empty personality dict defaults all traits to 0.5 — not zero, not undefined

## SoulFactory.batch_spawn()

```python
souls = await SoulFactory.batch_spawn(t, count=5, rng_seed=42)
```

Key behaviors:
- **Correct count**: Exactly N souls returned
- **Unique names**: Formatted with prefix + zero-padded index (e.g., `A-001`, `A-002`)
- **Unique DIDs**: All N souls have distinct identities
- **Personality variance**: With `variance=0.3`, openness values across 10 souls must differ but stay in `[0.0, 1.0]`
- **Zero variance = exact clones**: All traits match the template exactly
- **Reproducible with seed**: Same `rng_seed` produces the same personality values across two calls
- **Variance clamped to bounds**: Even with `openness=0.95` and `variance=0.5`, values stay in `[0.0, 1.0]`
- **Zero count**: Returns `[]` without error
- **Custom name pattern**: `"{name}-v{index}"` format string produces `"Bot-v1"`, `"Bot-v2"`

The seeding test is particularly important for reproducible deployments: operators may need to recreate a specific cohort for debugging or auditing.

## SoulFactory Registry

`SoulFactory` instances maintain a named registry of templates:

```python
factory = SoulFactory()
factory.register(t1)
factory.register(t2)
assert set(factory.list_templates()) == {"Alpha", "Beta"}
```

This enables application-level template management without global state.

## Public API Export Tests

`TestPublicExports` verifies that `SoulTemplate`, `SoulFactory`, and `MemoryVisibility` are importable from both `soul_protocol.spec` and the top-level `soul_protocol` package. These tests catch the common mistake of adding a class to a submodule but forgetting to re-export it from `__init__.py`.

## Known Gaps

There is no test for what happens when `batch_spawn` is called with a template that has `personality_variance=0.0` and a `rng_seed` — confirming that seeding has no effect on zero-variance batches. The `test_custom_name_pattern` test uses a hardcoded format string but does not test what happens with an invalid pattern (e.g., missing `{index}`).