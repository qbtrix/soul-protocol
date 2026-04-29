---
{
  "title": "Bundled Soul Templates: Role Archetype Registry",
  "summary": "The `soul_protocol.templates` package ships four pre-built YAML role archetypes — Arrow (sales), Flash (content), Cyborg (recruiting), and Analyst (research) — alongside a small discovery API. It gives consumers a zero-configuration starting point while keeping custom templates fully supported via path-based loading.",
  "concepts": [
    "soul templates",
    "role archetypes",
    "SoulFactory",
    "YAML configuration",
    "bundled templates",
    "Arrow",
    "Flash",
    "Cyborg",
    "Analyst",
    "template discovery"
  ],
  "categories": [
    "templates",
    "configuration",
    "soul-identity"
  ],
  "source_docs": [
    "2923d1fe342cdb19"
  ],
  "backlinks": null,
  "word_count": 460,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

When a developer instantiates a soul for a specific business role, they need a starting personality, skill set, and core memories tuned to that context. Without bundled defaults, every deployment would require hand-crafting a YAML template from scratch — a friction point that would slow adoption.

The `templates/` package solves this by shipping role-tuned archetypes alongside the library itself. Because the templates live in the package directory, they are always available after a standard `pip install` with no additional download or configuration step.

## Public API

```python
from soul_protocol.templates import (
    BUNDLED_TEMPLATES,   # canonical list: ["arrow", "flash", "cyborg", "analyst"]
    TEMPLATES_DIR,       # Path to the templates directory
    template_path,       # template_path("arrow") → Path(...)/arrow.yaml
    list_bundled,        # list_bundled() → names of .yaml files on disk
)
```

### `template_path(name)` vs `list_bundled()`

These two functions serve different purposes:

- `template_path(name)` is deterministic — it always returns the expected path for a named template, whether or not the file actually exists on disk. This lets `SoulFactory.load_bundled()` give a clear `FileNotFoundError` when a template is missing rather than a confusing `KeyError`.
- `list_bundled()` reflects actual disk state by globbing `*.yaml`. This means newly added templates are discovered automatically without updating `BUNDLED_TEMPLATES`. It also means a partially-installed package (a broken wheel, a missing file) will surface here rather than silently serving a stale hardcoded list.

## The Four Archetypes

| Template | Role | Key Characteristics |
|---|---|---|
| `arrow` | Sales agent | `default_scope: [org:sales:*]`, outbound-focused skills |
| `flash` | Content creator | Speed, breadth, social media workflows |
| `cyborg` | Recruiter | `recommended_tools: [instinct_propose]`, candidate-matching |
| `analyst` | Researcher | Structured reasoning, report generation |

Each ships as a YAML file that `SoulFactory.load_template()` can parse into a `SoulTemplate` Pydantic model. Custom templates follow the same schema — there is no special handling for bundled ones at the loader level.

## Integration with SoulFactory

Consumers typically access bundled templates through `SoulFactory.load_bundled(name)` rather than calling `template_path()` directly. The factory handles the load → validate → instantiate pipeline. The `templates/__init__.py` module is the inventory layer that the factory queries.

```python
from soul_protocol.runtime.templates import SoulFactory

arrow = SoulFactory.load_bundled("arrow")
soul = await SoulFactory.from_template(arrow, name="My Sales Agent")
```

## Why YAML, Not Python Config?

YAML templates can be edited by non-developers (product managers tuning a sales agent's core memories) and can be packaged as standalone artifacts that travel with deployments. A Python-based config would require code changes to update an archetype's personality values.

## Known Gaps

- `BUNDLED_TEMPLATES` is a hardcoded list. If a new YAML is added to the directory without updating this constant, `list_bundled()` will find it but `BUNDLED_TEMPLATES` will be stale. A future improvement could derive the constant from `list_bundled()` at import time, or add a CI check that asserts parity between the two.