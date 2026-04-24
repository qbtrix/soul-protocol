---
{
  "title": "Markdown Soul Parser: soul.md to SoulConfig Conversion",
  "summary": "Parses human-authored soul.md files into SoulConfig, supporting optional YAML frontmatter for structured metadata alongside free-form markdown sections for identity, personality, core memory, and DNA. Automatically generates a DID if one is not provided.",
  "concepts": [
    "markdown parser",
    "soul.md",
    "YAML frontmatter",
    "SoulConfig",
    "DID generation",
    "regex parsing",
    "personality parsing",
    "soul configuration",
    "section splitting"
  ],
  "categories": [
    "parsers",
    "configuration",
    "markdown"
  ],
  "source_docs": [
    "fe7818d4fbc60195"
  ],
  "backlinks": null,
  "word_count": 415,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Why Markdown?

Markdown is the natural format for humans to describe an AI companion's character. Authors can write prose in the `# Identity` section, list values under `# Values`, and describe the soul's persona in natural language. This lowers the barrier to creating souls compared to JSON/YAML, which require knowledge of the SoulConfig schema.

## File Format

A typical `soul.md` file:

```markdown
---
name: Luna
archetype: creative_companion
---

# Identity
Luna is a creative writing partner...

# Personality
openness: 0.8
conscientiousness: 0.5

# Core Memory
## Persona
Luna values creative exploration...

# DNA
## Values
- creativity
- curiosity
```

The YAML frontmatter between `---` delimiters carries structured metadata (name, archetype, DID). The markdown body carries prose and list sections.

## Parsing Pipeline

`soul_from_md()` is `async` because DID generation (called when no DID is in the frontmatter) may eventually involve network calls:

```python
async def soul_from_md(content: str) -> SoulConfig:
    fm, body = _extract_frontmatter(content)
    sections = _split_sections(body)
    # Build SoulConfig from sections + frontmatter...
```

**Frontmatter extraction** uses a regex for the `---...---` YAML block. If absent, frontmatter defaults to `{}` and the entire content is treated as a markdown body.

**Section splitting** uses only top-level `# Heading` markers as delimiters, meaning `## Subheadings` within sections are preserved as part of that section's content. This prevents the parser from misidentifying personality sub-sections as top-level soul properties.

**Personality parsing** via `_parse_personality()` reads `key: value` lines from the Personality section, mapping trait names to floats:

```python
def _parse_personality(text: str) -> Personality:
    # Reads "openness: 0.8", "neuroticism: 0.3", etc.
```

**DID generation**: If no `did` is in frontmatter, `generate_did(name)` is called to produce a deterministic `did:soul:...` identifier for the soul.

## List Item Extraction

`_parse_list_items()` handles both `- item` and `* item` markdown list syntax, stripping leading list markers. This is used for `# Values` and `# Goals` sections where content is enumerated rather than prose.

## Robustness

The parser is intentionally lenient — missing sections fall back to sensible defaults rather than raising errors. A `soul.md` with only a `# Identity` section produces a valid `SoulConfig` with default personality and empty DNA. This makes it easy to start minimal and add detail incrementally.

## Known Gaps

- The regex-based parser is fragile against unusual whitespace (Windows CRLF line endings in frontmatter can break the `---` match) and markdown tables, which would be mis-parsed as list items.
- Nested YAML frontmatter keys (e.g., `personality.openness: 0.8`) are not supported — personality must be in the markdown `# Personality` section.
