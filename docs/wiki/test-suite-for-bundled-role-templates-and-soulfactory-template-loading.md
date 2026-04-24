---
{
  "title": "Test Suite for Bundled Role Templates and SoulFactory Template Loading",
  "summary": "This test suite locks the contracts for the four bundled archetypes (Arrow, Flash, Cyborg, Analyst), the YAML/JSON template loaders, template instantiation into real souls, and the scope propagation behavior that ensures Arrow's sales-scoped core memories are visible to concrete `org:sales:leads` callers.",
  "concepts": [
    "bundled templates",
    "SoulFactory",
    "Arrow archetype",
    "Flash archetype",
    "Cyborg archetype",
    "Analyst archetype",
    "scope propagation",
    "match_scope",
    "SoulTemplate",
    "YAML loader",
    "JSON loader"
  ],
  "categories": [
    "testing",
    "templates",
    "scope",
    "test"
  ],
  "source_docs": [
    "773aad15ede0be80"
  ],
  "backlinks": null,
  "word_count": 453,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

This suite was created for Move 6 PR-A (2026-04-13) to serve as the contract test for the bundled template system. It is intentionally separate from `test_soul_templates.py`, which covers `SoulFactory.from_template` and `batch_spawn` in more general scenarios.

## Bundled Inventory Tests (`TestBundledInventory`)

The suite verifies that every template listed in `BUNDLED_TEMPLATES` actually exists on disk as a YAML file:

```python
for expected in BUNDLED_TEMPLATES:
    assert expected in set(list_bundled())
```

Beyond existence, each template is loaded and validated as a `SoulTemplate` Pydantic model. Personality values are checked to be in `[0.0, 1.0]` — an out-of-range value would silently produce a broken personality if not caught here.

Archetype-specific metadata is also locked:

- `arrow.metadata["default_scope"] == ["org:sales:*"]` — Arrow's scope tag must be present for recall filtering to work correctly
- `cyborg.metadata["recommended_tools"]` must include `"instinct_propose"` — a recruiting agent needs that tool declared
- Every template must ship with at least one skill — a soul with no skills is technically valid but practically useless

## Generic Loader Tests (`TestLoadTemplate`)

`SoulFactory.load_template(path)` accepts both YAML and JSON:

```python
# YAML load
path.write_text("name: Helper\narchetype: ...\n")
tmpl = SoulFactory.load_template(path)
assert tmpl.name == "Helper"

# JSON load
path.write_text(json.dumps({"name": "Helper", ...}))
tmpl = SoulFactory.load_template(path)
assert tmpl.name == "Helper"

# Missing file
with pytest.raises(FileNotFoundError):
    SoulFactory.load_template(tmp_path / "nope.yaml")
```

The `FileNotFoundError` test prevents a silent failure where a missing template returns `None` or a default template — both of which would produce confusing behavior at instantiation time.

## Instantiation Tests (`TestInstantiation`)

End-to-end tests create real `Soul` objects from bundled templates:

- Arrow instantiates with `soul.name == "Arrow"`
- Flash seeds at least as many memories as the template declares in `core_memories`
- `from_template(analyst, name="Custom Analyst")` overrides the default name

### Scope Propagation (v0.3.1 Bug Fix)

The most important test here locks a regression fix:

```python
arrow = SoulFactory.load_bundled("arrow")
soul = await SoulFactory.from_template(arrow)

# Every seeded core memory must carry the template's default_scope
for entry in soul._memory._semantic._facts.values():
    assert entry.scope == ["org:sales:*"]

# A concrete caller (org:sales:leads) must see glob-scoped (org:sales:*) memories
concrete_caller = ["org:sales:leads"]
assert all(match_scope(e.scope, concrete_caller) for e in entries)
```

Before the `match_scope` containment fix, a caller with scope `org:sales:leads` could not see memories tagged with `org:sales:*` because the match was directional. The fix made the glob match work in the containment direction (concrete scope ⊂ glob scope), and this test ensures it stays fixed.

## Template Helper Tests (`TestTemplateHelpers`)

- `template_path("arrow")` returns a path with `.yaml` extension
- `list_bundled()` includes all four canonical names

## Known Gaps

- There are no tests for custom templates with invalid personality values (e.g., `openness: 1.5`). The Pydantic validation would catch this, but there is no explicit test confirming the error message.
- Template versioning (a `version` field in the YAML) is not yet tested.