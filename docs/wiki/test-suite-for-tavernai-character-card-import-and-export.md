---
{
  "title": "Test Suite for TavernAI Character Card Import and Export",
  "summary": "Tests for the TavernAI importer, which converts Character Card V2 JSON (and PNG-embedded cards) into Soul Protocol `SoulConfig`, and the exporter that writes cards back. Covers field mapping to memory tiers, validation errors, and PNG tEXt chunk embedding.",
  "concepts": [
    "TavernAI",
    "Character Card V2",
    "importer",
    "exporter",
    "PNG embedding",
    "tEXt chunk",
    "chara_card_v2",
    "memory tiers",
    "core memory",
    "procedural memory",
    "semantic memory",
    "core_values",
    "round-trip",
    "SoulConfig"
  ],
  "categories": [
    "testing",
    "importers",
    "TavernAI",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "7ff5cd54257aa2f8"
  ],
  "backlinks": null,
  "word_count": 435,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

TavernAI Character Cards are a widely used format for AI character definitions, often distributed as PNG images with embedded JSON in a tEXt chunk. Soul Protocol's TavernAI importer enables migration from this ecosystem. `test_tavernai.py` validates field-by-field mapping, error handling, and the PNG embedding round-trip.

## Character Card V2 Structure

The spec requires:
```json
{
  "spec": "chara_card_v2",
  "data": {
    "name": "...",
    "description": "...",
    "personality": "...",
    "first_mes": "...",
    "scenario": "...",
    "mes_example": "...",
    "tags": [...],
    "creator": "...",
    "extensions": {...}
  }
}
```

A `full_card()` fixture provides all fields; `minimal_card()` provides only a name.

## Import: Memory Tier Assignments

| Card Field | Memory Tier | Rationale |
|---|---|---|
| `description` + `personality` | Core memory persona | Combined into the self-model narrative |
| `first_mes` | Procedural memory | Greeting behaviour instruction |
| `scenario` | Semantic memory | World context the soul knows |
| `mes_example` | Procedural memory | Example dialogue as behavioural guidance |
| `tags` | `core_values` | Character tags map to soul values |
| `creator` | Semantic memory | Attribution/metadata |
| `extensions` | Semantic memory | Platform-specific extras |

## Validation

The importer enforces spec compliance strictly:

- `test_from_json_missing_spec` — missing `spec` key raises `ValueError`.
- `test_from_json_wrong_spec` — wrong spec value (not `chara_card_v2`) raises `ValueError`.
- `test_from_json_missing_data` — missing `data` object raises `ValueError`.
- `test_from_json_missing_name` — missing name raises `ValueError`.

These guards prevent silently importing malformed cards as blank souls.

## Partial Cards

- `test_from_json_description_only` — card with `description` but no `personality` imports successfully.
- `test_from_json_personality_only` — card with `personality` but no `description` imports successfully.

## Export

- `test_to_character_card_structure` verifies the exported JSON has correct V2 structure.
- Core memory persona becomes `description`.
- Core values become `tags`.
- Archetype becomes `creator_notes`.

## Round-Trip (JSON)

`test_round_trip_json` imports a full card and exports it back, checking that `first_mes` and `scenario` survive the cycle. These fields are stored in procedural and semantic memory respectively, so the round-trip confirms memory-tier storage and retrieval are both correct.

## PNG Embedding

TavernAI cards are commonly shared as PNG files with card JSON in a `tEXt` chunk under the key `chara`.

- `test_from_png_extraction` creates a real PNG with an embedded tEXt chunk and verifies the importer extracts the card.
- `test_from_png_not_found` → `FileNotFoundError`.
- `test_from_png_invalid_file` → `ValueError` for a non-PNG file.
- `test_from_png_no_chara_chunk` → `ValueError` for a PNG without a character chunk.
- `test_to_png_creates_valid_file` exports a soul to PNG and validates the output.
- `test_round_trip_png` performs a full Soul → PNG → Soul cycle.

## Known Gaps

- No tests for large `extensions` objects.
- No tests for Unicode or non-ASCII content in card fields.