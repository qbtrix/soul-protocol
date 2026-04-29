---
{
  "title": "Test Suite for Soul Format Auto-Detection",
  "summary": "Tests for `detect_format()`, the function that inspects a filesystem path and returns the soul character format it represents — SoulSpec, TavernAI, Soul Protocol native, or unknown. Covers directory structures, JSON shapes, file extensions, PNG files, and error cases.",
  "concepts": [
    "detect_format",
    "format auto-detection",
    "soulspec",
    "TavernAI",
    "soul_protocol",
    "SoulSpec",
    "SOUL.md",
    "IDENTITY.md",
    "STYLE.md",
    "PNG",
    "YAML",
    "FileNotFoundError",
    "importers",
    "character format"
  ],
  "categories": [
    "testing",
    "importers",
    "format-detection",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "ba1654daba0937a2"
  ],
  "backlinks": null,
  "word_count": 348,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Before importing a soul definition, the importer layer must determine what format it is in. `detect_format()` examines the path without performing a full parse, enabling fast routing to the correct importer. `test_detect_format.py` exhaustively validates every detection signal.

## Detected Formats

### SoulSpec
A human-authored directory format using markdown files and a `soul.json`.

```python
def test_detect_soulspec_directory_with_soul_md(tmp_path):
    d = tmp_path / "spec"
    d.mkdir()
    (d / "SOUL.md").write_text("# Test\n")
    assert detect_format(d) == "soulspec"
```

Any of `SOUL.md`, `IDENTITY.md`, or `STYLE.md` in a directory triggers `"soulspec"` detection. A JSON file with `name` + `traits` fields also qualifies. A directory with `soul.json` containing `name+description` (but no `identity/dna` keys) is also soulspec, not native.

### TavernAI
- A JSON file with a `chara_card_v2` spec field → `"tavernai"`.
- A PNG file → `"tavernai_png"` (character cards are often embedded in PNG tEXt chunks).

### Soul Protocol Native
- A `.soul` extension → `"soul_protocol"`.
- A JSON file with `identity/dna` structure → `"soul_protocol"`.
- A directory containing a DSP-formatted `soul.json` → `"soul_protocol"`.
- YAML files → `"soul_protocol"` (native format also supports YAML).

### Unknown
- An empty directory → `"unknown"`.
- A random file type → `"unknown"`.

## Error Cases

`test_detect_nonexistent_path` verifies that a non-existent path raises `FileNotFoundError` rather than returning `"unknown"`. This distinction matters: `"unknown"` means "we recognise the path but can't classify it", while a missing path is a hard error.

## Detection Priority

The tests collectively imply an evaluation order:

1. Path does not exist → `FileNotFoundError`
2. `.soul` extension → `soul_protocol`
3. PNG file → `tavernai_png`
4. Directory with `SOUL.md`/`IDENTITY.md`/`STYLE.md` → `soulspec`
5. JSON with `chara_card_v2` → `tavernai`
6. JSON/YAML with `identity/dna` → `soul_protocol`
7. Directory with DSP soul.json → `soul_protocol`
8. JSON with `name+traits` → `soulspec`
9. Fallback → `unknown`

Each test uses `tmp_path` (pytest's temporary directory fixture) to avoid filesystem side effects between tests.

## Known Gaps

- No tests for ambiguous files (e.g. a JSON that matches both soulspec and soul_protocol signals).
- No tests for very large files — detection is assumed to read only the first few bytes or field names, but this is not verified.