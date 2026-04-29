---
{
  "title": "Parsers Subpackage: Soul Configuration File Loader Registry",
  "summary": "The parsers subpackage is the namespace for soul configuration format readers — soul.md, soul.yaml, and soul.json parsers live here. The __init__.py is intentionally empty so each parser module is imported directly, avoiding circular dependency risks.",
  "concepts": [
    "parsers subpackage",
    "soul configuration",
    "soul.md",
    "soul.yaml",
    "soul.json",
    "SoulConfig",
    "package init",
    "import design",
    "format support"
  ],
  "categories": [
    "parsers",
    "configuration",
    "architecture"
  ],
  "source_docs": [
    "ee345d999fdec2e4"
  ],
  "backlinks": null,
  "word_count": 427,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Role of the Parsers Subpackage

Soul Protocol supports three human-authored configuration formats for defining a soul's identity:

| Format | File | Use Case |
|---|---|---|
| Markdown | `soul.md` | Human-readable, narrative soul definitions |
| YAML | `soul.yaml` | Structured, machine-readable, minimal |
| JSON | `soul.json` | Programmatic generation, API output |

All three formats parse into the same `SoulConfig` Pydantic model, which is then passed to `Soul.birth_from_config()`. The parsers subpackage groups these converters under a common namespace.

## Empty `__init__.py` Design

The `__init__.py` contains no imports:

```python
# parsers/__init__.py — Parser subpackage for soul.md, soul.yaml, and soul.json files
# Created: 2026-02-22 — Empty init, individual parsers imported directly
```

This is a deliberate choice. Importing all parsers eagerly from `__init__.py` would force `pyyaml` (used only by `markdown.py` and `yaml_parser.py`) to be importable even in environments that only use JSON. Since Soul Protocol aims to be embeddable with minimal dependencies, each parser is imported on-demand by the caller:

```python
from soul_protocol.runtime.parsers.json_parser import parse_soul_json
from soul_protocol.runtime.parsers.yaml_parser import parse_soul_yaml
from soul_protocol.runtime.parsers.markdown import soul_from_md
```

This pattern also avoids circular import risk — if `__init__.py` imported all parsers and a parser imported something that transitively imported the parsers package, Python's import system could deadlock.

## Namespace Cohesion

Even without re-exports, the subpackage provides value: it groups all format-specific parsing logic into one directory, making it easy to add new formats (e.g., TOML, XML) without modifying any existing code. New parsers need only to produce a `SoulConfig` and live in this directory to be logically part of the system.

## Known Gaps

- There is no parser registry or format auto-detection. The caller is responsible for choosing the correct parser based on file extension or content sniffing. A future `parse_soul_auto(path)` helper could infer the format from the file extension and dispatch accordingly.

## Parser Dispatch Pattern

The typical consumer pattern delegates format selection based on file extension:

```python
suffix = Path(config_path).suffix
if suffix == ".json":
    from soul_protocol.runtime.parsers.json_parser import parse_soul_json
    config = parse_soul_json(text)
elif suffix in (".yaml", ".yml"):
    from soul_protocol.runtime.parsers.yaml_parser import parse_soul_yaml
    config = parse_soul_yaml(text)
elif suffix == ".md":
    from soul_protocol.runtime.parsers.markdown import soul_from_md
    config = await soul_from_md(text)
```

This pattern keeps the import cost proportional to what is used — a JSON-only deployment never imports `pyyaml`.

## Extension Point

Adding a new format (e.g., TOML) requires only creating `parsers/toml_parser.py` with a `parse_soul_toml(content) -> SoulConfig` function. No changes to existing parsers, no `__init__.py` modifications, and no changes to the `Soul` class beyond adding a new suffix case in the dispatch logic. The empty `__init__.py` keeps this extension surface clean.
