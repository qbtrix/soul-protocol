---
{
  "title": "Soul Format Auto-Detection and Importer Registry",
  "summary": "The importers package entry point exposes `SoulSpecImporter`, `TavernAIImporter`, and the `detect_format()` utility. `detect_format()` inspects a file or directory and returns a format tag so callers can route to the correct importer without knowing the format in advance.",
  "concepts": [
    "format detection",
    "importer",
    "SoulSpec",
    "TavernAI",
    "soul_protocol format",
    "file routing",
    "PNG magic bytes",
    "detect_format",
    "character card"
  ],
  "categories": [
    "importers",
    "interoperability",
    "soul-protocol-core"
  ],
  "source_docs": [
    "593e87c7a338bcf8"
  ],
  "backlinks": null,
  "word_count": 297,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Soul Protocol needs to ingest souls from multiple external formats — SoulSpec directories, TavernAI character cards (JSON and PNG), and native DSP files. The `importers/__init__.py` module is the single entry point for all of these. It re-exports the two concrete importer classes and provides `detect_format()` so upstream code can make routing decisions with one function call.

## detect_format() Logic

The function accepts a `str | Path` and raises `FileNotFoundError` if the path does not exist. Detection is purely heuristic — no LLM calls — which keeps it fast and side-effect-free.

**Directory rules (checked first):**

- Presence of `SOUL.md`, `IDENTITY.md`, or `STYLE.md` → `"soulspec"` (SoulSpec format uses markdown sidecar files)
- `soul.json` with `identity`, `dna`, or `format_version` keys → `"soul_protocol"`
- `soul.json` with `name` + `traits`/`description` → `"soulspec"`

**File rules:**

- `.png` with PNG magic bytes `\x89PNG...` → `"tavernai_png"`
- `.json` with `{"spec": "chara_card_v2"}` → `"tavernai"`
- `.json` with `identity`/`dna`/`version` keys → `"soul_protocol"`
- `.soul` (ZIP archive), `.yaml`, `.yml`, `.md` → `"soul_protocol"`
- Anything unrecognized → `"unknown"`

## Why a Fallback Chain?

Formats share file extensions (e.g. `.json`). Without content inspection, a TavernAI card and a DSP export are indistinguishable by extension alone. The function reads only the minimum amount of data — the PNG header (8 bytes), or a partial JSON parse — to keep I/O low.

## Integration Pattern

```python
from soul_protocol.runtime.importers import detect_format, SoulSpecImporter, TavernAIImporter

fmt = detect_format(path)
if fmt == "soulspec":
    soul = await SoulSpecImporter.from_directory(path)
elif fmt in ("tavernai", "tavernai_png"):
    soul = await TavernAIImporter.from_png(path)
elif fmt == "soul_protocol":
    soul = await Soul.load(path)
```

## Known Gaps

- Detection is purely structural — a `.json` file that happens to have an `identity` key but is not a DSP file will be mis-classified as `"soul_protocol"`.
- No plugin mechanism for registering third-party format detectors.