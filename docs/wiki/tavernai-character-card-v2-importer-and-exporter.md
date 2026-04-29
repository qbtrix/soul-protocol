---
{
  "title": "TavernAI Character Card V2 Importer and Exporter",
  "summary": "Supports full round-trip conversion between TavernAI Character Card V2 (JSON and PNG-embedded) and DSP Soul objects. Handles PNG binary parsing — extracting and embedding character JSON in `tEXt`/`iTXt` chunks — without any external image library dependency.",
  "concepts": [
    "TavernAI",
    "character card V2",
    "PNG tEXt chunk",
    "chara_card_v2",
    "base64",
    "iTXt",
    "struct parsing",
    "round-trip conversion",
    "procedural memory",
    "semantic memory"
  ],
  "categories": [
    "importers",
    "interoperability",
    "binary-formats"
  ],
  "source_docs": [
    "75d730f54e51abc4"
  ],
  "backlinks": null,
  "word_count": 360,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Background

TavernAI character cards are a popular community format for sharing AI personas. Version 2 (`chara_card_v2`) stores character data as JSON — either standalone or embedded in a PNG file's metadata chunks. Soul Protocol supports importing these cards to lower friction for users migrating from TavernAI-compatible platforms.

## JSON Import Flow

`TavernAIImporter.from_json()` validates the card structure, then maps fields to DSP concepts:

| Card Field | DSP Destination |
|---|---|
| `data.name` | Soul identity name |
| `data.description` + `data.personality` | Core memory persona |
| `data.first_mes` | Procedural memory — default greeting |
| `data.scenario` | Semantic memory — scenario context |
| `data.mes_example` | Procedural memory — conversation examples |
| `data.tags` | Core values list |
| `data.creator` | Semantic memory — attribution |
| `data.extensions` | Semantic memory — serialized extensions |

## PNG Binary Parsing

TavernAI PNG cards embed character JSON in a `tEXt` chunk with keyword `"chara"`, base64-encoded. The parser walks the PNG chunk stream manually using `struct.unpack` — no PIL/Pillow dependency required.

```python
def _extract_json_from_png(png_bytes: bytes) -> dict:
    # Validate PNG signature, walk chunks
    # Find tEXt or iTXt chunk with keyword "chara"
    # base64.b64decode the value → JSON
```

Both `tEXt` (uncompressed) and `iTXt` (optionally zlib-compressed) chunks are handled, matching real-world card variety.

## PNG Export

`TavernAIImporter.to_png()` inserts a new `tEXt` chunk just before the PNG's `IEND` marker. If no source image is provided, `_minimal_png()` synthesizes a 1×1 transparent PNG from scratch using raw struct packing — again with no external dependency.

## Round-Trip Export

`to_character_card()` reconstructs the Card V2 JSON from the soul's memory stores — procedural memories are scanned for the greeting and example patterns, semantic memories for scenario and creator. Tags are rebuilt from `soul.identity.core_values`.

## Known Gaps

- OCEAN personality data has no Card V2 equivalent — personality dimensions are lost on export.
- The `extensions` dict is stored as a raw JSON string in semantic memory; on re-export it is set to an empty dict since parsing the serialized string back is not implemented.
- iTXt compressed chunk extraction assumes the text data is base64 even after decompression, which may not hold for all generators.