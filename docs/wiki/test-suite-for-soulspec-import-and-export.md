---
{
  "title": "Test Suite for SoulSpec Import and Export",
  "summary": "Tests for the SoulSpec importer, which converts a human-authored directory of markdown files and soul.json into a Soul Protocol `SoulConfig`, and the corresponding exporter that writes those files back out. Covers OCEAN trait mapping, memory tier assignments, round-trip fidelity, and error handling.",
  "concepts": [
    "SoulSpec",
    "importer",
    "exporter",
    "soul.json",
    "SOUL.md",
    "IDENTITY.md",
    "STYLE.md",
    "OCEAN traits",
    "DNA",
    "memory tiers",
    "core memory",
    "semantic memory",
    "procedural memory",
    "round-trip",
    "SoulConfig"
  ],
  "categories": [
    "testing",
    "importers",
    "SoulSpec",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "dad4027c123360e7"
  ],
  "backlinks": null,
  "word_count": 363,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

SoulSpec is a creator-friendly format where a soul's identity lives in plain markdown files and a structured JSON. The importer translates this into Soul Protocol's internal model; the exporter does the reverse. `test_soulspec.py` validates both directions and the round-trip.

## Directory Structure Under Test

```
soulspec_dir/
  soul.json       — OCEAN traits, values, name
  SOUL.md         — core persona narrative
  IDENTITY.md     — backstory, origin story
  STYLE.md        — communication style (warmth, formality, etc.)
```

A `minimal_soulspec_dir` (only `soul.json`) and an `identity_only_dir` (only `IDENTITY.md`) fixture exercise graceful degradation paths.

## Import: Memory Tier Assignments

Each source file maps to a specific memory tier:

| Source | Memory Tier | Rationale |
|---|---|---|
| `SOUL.md` | Core memory persona | Defines the agent's self-model |
| `IDENTITY.md` | Semantic memory | Factual background the soul "knows" |
| `STYLE.md` | Procedural memory | How-to-communicate instructions |

`test_from_directory_style_as_procedural` and `test_from_directory_identity_as_semantic` enforce these assignments, preventing future refactors from silently mis-routing content.

## OCEAN Trait Mapping

`test_from_directory_ocean_mapping` verifies that OCEAN personality scores from `soul.json` are correctly mapped to the `DNA.personality` model. The OCEAN model (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism) is central to soul identity, so mapping correctness is non-negotiable.

## Name Extraction

Name resolution falls through a priority chain:
1. `soul.json` → `name` field
2. `IDENTITY.md` → first `# Heading` parsed as name
3. No name → `ValueError` (tested by `test_from_directory_no_name`)

## Values Parsing

`test_from_directory_values_as_string` verifies that values supplied as a comma-separated string in `soul.json` are parsed into a list, accommodating the common human-authored format.

## Export: File Generation

`test_to_soulspec_creates_all_files` checks that exporting produces all four expected files. Individual content tests confirm:
- `soul.json` contains `name`, `traits`, and `values`
- `SOUL.md` contains the persona text
- `IDENTITY.md` contains the soul name
- `STYLE.md` contains communication style fields

## Round-Trip Tests

`test_round_trip_soulspec` and `test_round_trip_soul_json` import a SoulSpec, export it back, and re-import, verifying data is preserved across the cycle. This guards against lossy serialisation where fields silently vanish.

## Known Gaps

- `test_from_directory_partial_style` covers only some STYLE.md fields — edge cases with partially populated style files may not be fully exercised.
- Trait mapping aliases are tested (`test_trait_mapping_aliases`) but the full alias table is not visible from the test structure alone.