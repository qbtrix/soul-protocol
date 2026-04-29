---
{
  "title": "DNA to System Prompt and Markdown Renderer",
  "summary": "Converts a soul's identity, DNA (personality blueprint), core memory, and current state into either an LLM system prompt or a human-readable markdown document. The system prompt renderer is the primary mechanism by which a soul's personality becomes an active influence on its LLM-driven behavior.",
  "concepts": [
    "system prompt",
    "dna_to_system_prompt",
    "dna_to_markdown",
    "OCEAN personality",
    "biorhythms",
    "core memory",
    "soul state",
    "DNA renderer",
    "personality encoding",
    "LLM context"
  ],
  "categories": [
    "soul DNA",
    "LLM integration",
    "prompt engineering"
  ],
  "source_docs": [
    "2d228ce7298ff924"
  ],
  "backlinks": null,
  "word_count": 428,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The `dna/prompt.py` module is the bridge between a soul's structured data model and the text formats that actually shape behavior. It handles two output modes:

1. **System prompt** — consumed by LLMs at inference time to set the soul's persona, values, personality traits, state, and memory context.
2. **Markdown** — used for export, debugging, and human inspection of the soul's current configuration.

## System Prompt Structure

The `dna_to_system_prompt()` function assembles sections in this order:

```
[Identity: name, archetype, origin, prime directive, values]
[Personality: OCEAN scores]
[Communication Style: warmth, verbosity, humor, emoji]
[Current State: mood, energy, focus]
[Biorhythms: compact non-default summary]
[Core Memory: persona + human sections]
```

Each section is only added if it contains non-empty data, keeping prompts concise for souls with minimal configuration.

### OCEAN Personality Encoding

```python
f"Openness: {p.openness:.1f} | Conscientiousness: {p.conscientiousness:.1f} | "
f"Extraversion: {p.extraversion:.1f} | Agreeableness: {p.agreeableness:.1f} | "
f"Neuroticism: {p.neuroticism:.1f}"
```

All five OCEAN traits are written as a single pipe-delimited line. The `.1f` format provides one decimal place — enough precision for the LLM to differentiate trait levels without overwhelming the prompt.

### Biorhythms: Non-Default Only

The `_biorhythms_summary()` helper compares each biorhythm field to the default `Biorhythms()` instance and only emits fields that differ. This prevents cluttering the system prompt with default values the LLM doesn't need to act on. Two special cases:

- If both `energy_drain_rate` and `social_drain_rate` are 0, it emits `"Energy: always-on (no drain)"` — a clear signal to the LLM that energy is not a constraint.
- If `auto_regen` is disabled, it's explicitly noted.

### Self-Model Separation

A key architectural note: self-model insights (the soul's introspective understanding of itself) are **not** generated here. As of v0.2.0, `Soul.to_system_prompt()` appends them after calling `dna_to_system_prompt()`. This separation keeps the DNA renderer stateless and testable without a full `Soul` instance.

## Markdown Output

`dna_to_markdown()` produces a full markdown document with headed sections for personality, communication style, and biorhythms. Unlike the system prompt, markdown always includes **all** biorhythm fields (not just non-defaults), making it suitable for a complete snapshot:

```python
lines.append(f"- **Energy drain rate:** {b.energy_drain_rate}/interaction")
lines.append(f"- **Social drain rate:** {b.social_drain_rate}/interaction")
lines.append(f"- **Tired threshold:** {b.tired_threshold:.0f}%")
```

The OCEAN traits are rendered as a markdown table for readability.

## Data Flow

```
Identity + DNA + CoreMemory + SoulState
        │
        ▼
  dna_to_system_prompt()
        │
        ▼
  str (LLM system message)
```

## Known Gaps

No TODOs or FIXMEs in this file. The Agreeableness and Neuroticism traits from OCEAN appear in the system prompt output but the biorhythms analysis in `dream.py` notes they are not yet covered there — that gap lives outside this module.