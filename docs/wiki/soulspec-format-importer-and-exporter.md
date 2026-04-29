---
{
  "title": "SoulSpec Format Importer and Exporter",
  "summary": "Bridges the SoulSpec open standard (soulspec.org) and the Digital Soul Protocol. Reads a SoulSpec directory structure — `SOUL.md`, `IDENTITY.md`, `STYLE.md`, `soul.json` — and maps each file to the appropriate DSP memory tier and OCEAN personality model.",
  "concepts": [
    "SoulSpec",
    "OCEAN personality model",
    "trait mapping",
    "soul.json",
    "SOUL.md",
    "IDENTITY.md",
    "STYLE.md",
    "procedural memory",
    "semantic memory",
    "Soul.birth"
  ],
  "categories": [
    "importers",
    "personality",
    "interoperability"
  ],
  "source_docs": [
    "2cab99e98ac7dad0"
  ],
  "backlinks": null,
  "word_count": 359,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## What is SoulSpec?

SoulSpec is an open directory-based format for defining AI character personalities. A SoulSpec soul lives in a folder with up to four files: `soul.json` (structured metadata), `SOUL.md` (narrative persona), `IDENTITY.md` (name and backstory), and `STYLE.md` (communication guidelines).

## Import Pipeline

`SoulSpecImporter.from_directory()` reads whatever files are present, extracts identity, and calls `Soul.birth()` with mapped fields:

| SoulSpec Source | DSP Destination |
|---|---|
| `soul.json → name` | Soul identity name |
| `SOUL.md` or `soul.json → description` | Core memory persona |
| `IDENTITY.md` heading or `name:` field | Soul name (fallback) |
| `soul.json → traits` | OCEAN dimensions (mapped) |
| `soul.json → values` | Core values list |
| `STYLE.md` | Procedural memory (importance 7) |
| `IDENTITY.md` body | Semantic memory (importance 7) |

## OCEAN Trait Mapping

SoulSpec traits use arbitrary string keys. The `_OCEAN_TRAIT_MAP` dictionary maps ~20 common synonyms (e.g. `"curious"` → `openness`, `"disciplined"` → `conscientiousness`) to the five OCEAN dimensions. Numeric values are normalized to `0.0–1.0` (dividing by 100 when the value exceeds 1), and string descriptors like `"high"` or `"very low"` are mapped to fixed floats.

```python
_OCEAN_TRAIT_MAP = {
    "openness": "openness",
    "curiosity": "openness",
    "organized": "conscientiousness",
    "sociable": "extraversion",
    # ...
}
```

Only dimensions that can be confidently mapped are included — unmapped traits are silently dropped rather than guessing.

## from_soul_json()

A lighter path for programmatic use: accepts an already-parsed `dict` (no file I/O) and applies the same trait mapping. Useful when the caller has already loaded `soul.json` for other reasons.

## Error Handling

- Raises `FileNotFoundError` if the directory does not exist.
- Raises `ValueError` if no name can be determined from any file — the soul cannot be born nameless.
- JSON parse errors in `soul.json` are silently ignored and the file is treated as absent, preventing crashes on malformed inputs.

## Known Gaps

- Export (SoulSpec → directory) is not yet implemented — import only.
- Traits not in `_OCEAN_TRAIT_MAP` are dropped with no warning, which may surprise users with custom trait schemas.
- The containment boost in token similarity (used elsewhere) is not applied here — trait matching is exact-key lookups only.