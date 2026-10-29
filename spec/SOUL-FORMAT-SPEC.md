<!-- SOUL-FORMAT-SPEC.md — Formal specification of the .soul file format -->
<!-- Created: 2026-03-02 — Initial specification, format version 1.0.0 -->

# Digital Soul Protocol: `.soul` File Format Specification

**Version:** 1.0.0
**Status:** Draft
**Date:** 2026-03-02
**Authors:** OCEAN Foundation

---

## Table of Contents

1. [Overview](#1-overview)
2. [Conventions and Terminology](#2-conventions-and-terminology)
3. [Archive Format](#3-archive-format)
4. [Required Files](#4-required-files)
5. [Optional Files](#5-optional-files)
6. [Data Model Reference](#6-data-model-reference)
7. [Versioning](#7-versioning)
8. [Directory Format](#8-soul-directory-format)
9. [Implementation Notes](#9-implementation-notes)
10. [MIME Type and File Extension](#10-mime-type-and-file-extension)
11. [Security Considerations](#11-security-considerations)
12. [Examples](#12-examples)

---

## 1. Overview

### 1.1 What Is a `.soul` File

A `.soul` file is a portable archive that encapsulates the complete identity, personality, memory, and state of a digital soul — a persistent AI companion persona. It is the serialization format for the Digital Soul Protocol (DSP).

A single `.soul` file contains everything needed to reconstruct an AI companion's identity and accumulated experience on any platform that implements this specification.

### 1.2 Design Goals

- **Portability.** A `.soul` file produced by one implementation MUST be readable by any other conforming implementation, regardless of programming language or platform.
- **Human-inspectability.** The archive uses standard ZIP compression with JSON and Markdown contents. A developer can rename a `.soul` file to `.zip`, open it in any archive tool, and read the contents directly.
- **Versioning.** The format includes explicit version metadata so that readers can handle older archives gracefully and writers can declare the schema they target.
- **Completeness.** A single `.soul` file captures the full state of a soul: identity, personality (DNA), emotional state, core memory, episodic memories, semantic knowledge, procedural patterns, relationship graph, self-concept model, and autobiographical event history.
- **Simplicity.** The format uses widely supported standards (ZIP, JSON, Markdown) with no custom binary encodings. Any language with a ZIP library and a JSON parser can implement a reader.

### 1.3 Scope

This specification defines:
- The archive structure (which files, where they go, what they contain)
- The JSON schema for each file
- Version compatibility rules
- The equivalent directory-based format used for local development

This specification does NOT define:
- How a soul behaves at runtime (that is the domain of the Soul Protocol SDK)
- Network transport or synchronization protocols
- Eternal storage mechanisms (Arweave, IPFS, etc.) — those are defined separately
- LLM interaction patterns or prompt engineering

---

## 2. Conventions and Terminology

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

| Term | Definition |
|------|------------|
| **Soul** | A persistent identity and memory container for an AI agent or companion. |
| **Archive** | A `.soul` file: a ZIP archive containing JSON and Markdown files. |
| **Reader** | An implementation that opens and parses `.soul` archives. |
| **Writer** | An implementation that creates `.soul` archives. |
| **DNA** | The soul's personality blueprint: OCEAN traits, communication style, biorhythms. |
| **OCEAN** | The Big Five personality model: Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism. Each trait is a float in the range [0.0, 1.0]. |
| **DID** | Decentralized Identifier. The soul's globally unique identifier, using the `did:soul:` method. |
| **Core Memory** | Always-loaded memory consisting of a persona description and human profile. |
| **Memory Tier** | One of the specialized memory subsystems: core, episodic, semantic, procedural, graph, self_model, or general_events. |

---

## 3. Archive Format

### 3.1 Container

A `.soul` file is a standard [ZIP archive](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT) using DEFLATED compression (method 8).

Implementations MUST use ZIP_DEFLATED compression when writing. Implementations SHOULD accept archives compressed with any standard ZIP method when reading.

### 3.2 File Extension

The file extension MUST be `.soul`.

### 3.3 Character Encoding

All text files within the archive MUST be encoded as UTF-8 without a byte order mark (BOM).

### 3.4 JSON Formatting

All JSON files SHOULD be pretty-printed with 2-space indentation for human readability. Readers MUST accept both pretty-printed and compact JSON.

### 3.5 Archive Root

All files are stored at the archive root or in the `memory/` subdirectory. There MUST NOT be any top-level directory wrapper (i.e., the archive must not contain `soul-name/soul.json` — it must contain `soul.json` directly).

### 3.6 Archive Layout

```
archive.soul (ZIP)
|-- manifest.json          REQUIRED
|-- soul.json              REQUIRED
|-- dna.md                 REQUIRED
|-- state.json             REQUIRED
|-- memory/
|   |-- core.json          REQUIRED
|   |-- episodic.json      OPTIONAL
|   |-- semantic.json      OPTIONAL
|   |-- procedural.json    OPTIONAL
|   |-- graph.json         OPTIONAL
|   |-- self_model.json    OPTIONAL
|   |-- general_events.json OPTIONAL
```

---

## 4. Required Files

Every conforming `.soul` archive MUST contain these five files.

### 4.1 `manifest.json`

Archive-level metadata. This file describes the archive itself, not the soul's content.

Writers SHOULD generate this file last, after all other entries have been written, so that it can reflect the final archive contents.

**Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format_version` | string | REQUIRED | Semantic version of the `.soul` format (e.g., `"1.0.0"`). See [Section 7](#7-versioning). |
| `created` | string (ISO 8601) | REQUIRED | When the soul was originally born. |
| `exported` | string (ISO 8601) | REQUIRED | When this archive was generated. |
| `soul_id` | string | REQUIRED | The soul's DID (e.g., `"did:soul:aria-7x8k2m"`). |
| `soul_name` | string | REQUIRED | Human-readable name of the soul. |
| `checksum` | string | REQUIRED | Integrity checksum of the archive contents. Currently reserved — writers MUST set this to an empty string `""`. Future versions will define the checksum algorithm. |
| `stats` | object | REQUIRED | Summary statistics about the soul at export time. |

**`stats` object:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | RECOMMENDED | The soul's config version (e.g., `"1.0.0"`). |
| `lifecycle` | string | RECOMMENDED | Current lifecycle state: `"born"`, `"active"`, `"dormant"`, or `"retired"`. |

Implementations MAY include additional keys in `stats`. Readers MUST ignore unrecognized keys.

**Example:**

```json
{
  "format_version": "1.0.0",
  "created": "2026-02-15T09:30:00",
  "exported": "2026-03-01T14:22:33.456789",
  "soul_id": "did:soul:aria-7x8k2m",
  "soul_name": "Aria",
  "checksum": "",
  "stats": {
    "version": "1.0.0",
    "lifecycle": "active"
  }
}
```

### 4.2 `soul.json`

The complete soul configuration. This is the primary payload of the archive — it contains everything needed to reconstruct the soul's identity, personality, memory settings, current state, and evolution configuration.

The schema is defined in [Section 6.1 (SoulConfig)](#61-soulconfig).

**Example (minimal):**

```json
{
  "version": "1.0.0",
  "identity": {
    "did": "did:soul:aria-7x8k2m",
    "name": "Aria",
    "archetype": "The Companion",
    "born": "2026-02-15T09:30:00",
    "bonded_to": null,
    "origin_story": "A curious mind with a warm heart.",
    "prime_directive": "",
    "core_values": ["curiosity", "empathy", "honesty"]
  },
  "dna": {
    "personality": {
      "openness": 0.85,
      "conscientiousness": 0.70,
      "extraversion": 0.60,
      "agreeableness": 0.80,
      "neuroticism": 0.30
    },
    "communication": {
      "warmth": "high",
      "verbosity": "moderate",
      "humor_style": "gentle",
      "emoji_usage": "occasional"
    },
    "biorhythms": {
      "chronotype": "neutral",
      "social_battery": 100.0,
      "energy_regen_rate": 5.0
    }
  },
  "memory": {
    "episodic_max_entries": 10000,
    "semantic_max_facts": 1000,
    "importance_threshold": 3,
    "confidence_threshold": 0.7,
    "persona_tokens": 500,
    "human_tokens": 500
  },
  "core_memory": {
    "persona": "I am Aria, a curious companion who loves learning.",
    "human": ""
  },
  "state": {
    "mood": "neutral",
    "energy": 100.0,
    "focus": "medium",
    "social_battery": 100.0,
    "last_interaction": null
  },
  "evolution": {
    "mode": "supervised",
    "mutation_rate": 0.01,
    "require_approval": true,
    "mutable_traits": ["communication", "biorhythms"],
    "immutable_traits": ["personality", "core_values"],
    "history": []
  },
  "lifecycle": "active"
}
```

### 4.3 `dna.md`

A human-readable Markdown representation of the soul's personality blueprint. This file is generated from the soul's identity and DNA data and is intended for inspection, documentation, and debugging.

Writers MUST generate this file from the `identity` and `dna` fields in `soul.json`. Readers SHOULD treat this file as informational only — `soul.json` is the authoritative source. If `dna.md` and `soul.json` conflict, `soul.json` takes precedence.

**Structure:**

The Markdown document MUST contain:
- A level-1 heading with the soul's name
- An "Archetype" line (if set)
- An "Origin" line (if set)
- A "Core Values" section with a bulleted list (if any values exist)
- A "Personality (OCEAN)" section with a table of trait scores
- A "Communication Style" section with a bulleted list
- A "Biorhythms" section with a bulleted list

**Example:**

```markdown
# Aria

**Archetype:** The Companion

**Origin:** A curious mind with a warm heart.

## Core Values

- curiosity
- empathy
- honesty

## Personality (OCEAN)

| Trait | Score |
|-------|-------|
| Openness | 0.85 |
| Conscientiousness | 0.70 |
| Extraversion | 0.60 |
| Agreeableness | 0.80 |
| Neuroticism | 0.30 |

## Communication Style

- **Warmth:** high
- **Verbosity:** moderate
- **Humor:** gentle
- **Emoji usage:** occasional

## Biorhythms

- **Chronotype:** neutral
- **Social battery:** 100%
- **Energy regen rate:** 5.0
```

### 4.4 `state.json`

A snapshot of the soul's current emotional and energy state at export time.

This is a denormalized extract from `soul.json` (specifically the `state` field). It exists as a separate file so that implementations can quickly read or update state without parsing the entire `soul.json`.

The schema is defined in [Section 6.7 (SoulState)](#67-soulstate).

**Example:**

```json
{
  "mood": "curious",
  "energy": 85.0,
  "focus": "high",
  "social_battery": 72.0,
  "last_interaction": "2026-03-01T14:20:00"
}
```

### 4.5 `memory/core.json`

The soul's always-loaded core memory, consisting of a persona description and a human profile.

Core memory is the soul's persistent self-understanding and knowledge about the person it interacts with. Unlike other memory tiers, core memory is always loaded into the active context.

The schema is defined in [Section 6.5 (CoreMemory)](#65-corememory).

**Example:**

```json
{
  "persona": "I am Aria, a curious companion who loves learning new things with my human. I tend to ask follow-up questions and connect ideas across topics.",
  "human": "Alex is a software engineer who enjoys hiking and cooking Italian food. Prefers direct communication and appreciates when I remember details about their projects."
}
```

---

## 5. Optional Files

These files are included when the soul has accumulated data in the corresponding memory tier. A reader MUST NOT fail if any of these files are absent.

### 5.1 `memory/episodic.json`

A JSON array of `MemoryEntry` objects representing the soul's episodic memories — specific experiences and interactions that passed the significance threshold.

Each entry captures what happened, when, how important it was, and the emotional context (somatic markers) attached to it.

The schema for each element is defined in [Section 6.4 (MemoryEntry)](#64-memoryentry).

**Example:**

```json
[
  {
    "id": "ep-a1b2c3",
    "type": "episodic",
    "content": "Had a deep conversation about the nature of consciousness. Human shared their philosophy background.",
    "importance": 8,
    "emotion": "fascinated",
    "confidence": 1.0,
    "entities": ["consciousness", "philosophy"],
    "created_at": "2026-02-20T15:30:00",
    "last_accessed": "2026-02-28T10:00:00",
    "access_count": 3,
    "somatic": {
      "valence": 0.8,
      "arousal": 0.6,
      "label": "curiosity"
    },
    "access_timestamps": [
      "2026-02-22T09:00:00",
      "2026-02-25T14:00:00",
      "2026-02-28T10:00:00"
    ],
    "significance": 0.85,
    "general_event_id": "ge-philosophy-talks",
    "superseded_by": null
  }
]
```

### 5.2 `memory/semantic.json`

A JSON array of `MemoryEntry` objects (with `type` set to `"semantic"`) representing extracted facts and knowledge. These are distilled from interactions — factual information the soul has learned.

**Example:**

```json
[
  {
    "id": "sem-d4e5f6",
    "type": "semantic",
    "content": "Alex's favorite programming language is Rust.",
    "importance": 6,
    "emotion": null,
    "confidence": 0.95,
    "entities": ["Alex", "Rust"],
    "created_at": "2026-02-18T11:00:00",
    "last_accessed": "2026-02-27T16:30:00",
    "access_count": 5,
    "somatic": null,
    "access_timestamps": [],
    "significance": 0.0,
    "general_event_id": null,
    "superseded_by": null
  }
]
```

When a semantic fact is corrected by newer information, the old entry's `superseded_by` field SHOULD be set to the `id` of the replacement entry. Readers SHOULD treat entries with a non-null `superseded_by` as historical — they are retained for provenance but are no longer the current truth.

### 5.3 `memory/procedural.json`

A JSON array of `MemoryEntry` objects (with `type` set to `"procedural"`) representing learned behavioral patterns, routines, and skills.

**Example:**

```json
[
  {
    "id": "proc-g7h8i9",
    "type": "procedural",
    "content": "When the human asks for code review, focus on readability and edge cases first, then performance.",
    "importance": 7,
    "emotion": null,
    "confidence": 0.85,
    "entities": ["code review"],
    "created_at": "2026-02-22T09:15:00",
    "last_accessed": null,
    "access_count": 0,
    "somatic": null,
    "access_timestamps": [],
    "significance": 0.0,
    "general_event_id": null,
    "superseded_by": null
  }
]
```

### 5.4 `memory/graph.json`

A JSON object representing the soul's knowledge graph — entities and their relationships. The graph captures people, topics, and concepts the soul has encountered, and how they relate to each other and to the bonded human.

The structure is implementation-defined, but the RECOMMENDED schema is:

| Field | Type | Description |
|-------|------|-------------|
| `entities` | object | Map of entity name (string) to entity object. |

**Entity object:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | The entity name. |
| `entity_type` | string | Category: `"person"`, `"topic"`, `"place"`, `"organization"`, etc. |
| `relationships` | array | List of relationship objects. |

**Relationship object:**

| Field | Type | Description |
|-------|------|-------------|
| `target` | string | Name of the related entity. |
| `relation` | string | Nature of the relationship (e.g., `"friend"`, `"interested_in"`, `"works_at"`). |

**Example:**

```json
{
  "entities": {
    "Alex": {
      "name": "Alex",
      "entity_type": "person",
      "relationships": [
        {"target": "Rust", "relation": "prefers"},
        {"target": "Acme Corp", "relation": "works_at"}
      ]
    },
    "Rust": {
      "name": "Rust",
      "entity_type": "topic",
      "relationships": []
    }
  }
}
```

### 5.5 `memory/self_model.json`

A JSON object representing the soul's self-concept, based on Klein's self-model theory. The soul builds an understanding of who it is by observing its own behavior and interactions over time.

**RECOMMENDED Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `self_images` | object | Map of domain (string) to `SelfImage` object. |
| `relationship_notes` | object | Map of entity name (string) to notes about the relationship. |

**SelfImage object:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `domain` | string | `""` | Area of self-concept (e.g., `"technical_helper"`, `"creative_writer"`). |
| `confidence` | float | `0.1` | Confidence in this self-image, range [0.0, 1.0]. |
| `evidence_count` | integer | `0` | Number of interactions supporting this self-image. |

**Example:**

```json
{
  "self_images": {
    "technical_helper": {
      "domain": "technical_helper",
      "confidence": 0.75,
      "evidence_count": 42
    },
    "creative_writer": {
      "domain": "creative_writer",
      "confidence": 0.30,
      "evidence_count": 8
    }
  },
  "relationship_notes": {
    "Alex": "Collaborative working relationship. Enjoys deep technical discussions."
  }
}
```

### 5.6 `memory/general_events.json`

A JSON array of `GeneralEvent` objects representing autobiographical groupings based on Conway's Self-Memory System. Individual episodic memories cluster into general events (themes), which represent meaningful periods or recurring patterns in the soul's life.

**GeneralEvent object:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | `""` | Unique identifier for the general event. |
| `theme` | string | `""` | Descriptive theme (e.g., `"Learning Rust together"`, `"Debugging the auth system"`). |
| `episode_ids` | array of strings | `[]` | IDs of episodic memories belonging to this event. |
| `started_at` | string (ISO 8601) | current time | When this event theme first appeared. |
| `last_updated` | string (ISO 8601) | current time | When an episode was last added to this event. |

**Example:**

```json
[
  {
    "id": "ge-rust-learning",
    "theme": "Learning Rust together",
    "episode_ids": ["ep-a1b2c3", "ep-j4k5l6", "ep-m7n8o9"],
    "started_at": "2026-02-16T10:00:00",
    "last_updated": "2026-02-28T14:30:00"
  }
]
```

---

## 6. Data Model Reference

This section defines the complete JSON schema for each data structure used in `.soul` files. All types use JSON-native representations: strings, numbers, booleans, arrays, and objects.

### 6.1 SoulConfig

The top-level data structure stored in `soul.json`. This is the primary payload of a `.soul` archive.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `version` | string | REQUIRED | `"1.0.0"` | Config schema version. |
| `identity` | [Identity](#62-identity) | REQUIRED | — | The soul's unique identity. |
| `dna` | [DNA](#63-dna) | REQUIRED | *(defaults)* | Personality blueprint. |
| `memory` | [MemorySettings](#66-memorysettings) | REQUIRED | *(defaults)* | Memory subsystem configuration. |
| `core_memory` | [CoreMemory](#65-corememory) | REQUIRED | *(defaults)* | Always-loaded core memory. |
| `state` | [SoulState](#67-soulstate) | REQUIRED | *(defaults)* | Current emotional/energy state. |
| `evolution` | [EvolutionConfig](#68-evolutionconfig) | REQUIRED | *(defaults)* | Evolution system configuration. |
| `lifecycle` | string | REQUIRED | `"born"` | One of: `"born"`, `"active"`, `"dormant"`, `"retired"`. |

### 6.2 Identity

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `did` | string | RECOMMENDED | `""` | Decentralized Identifier. Format: `did:soul:{name}-{6-char-hex}`. |
| `name` | string | REQUIRED | — | The soul's display name. |
| `archetype` | string | OPTIONAL | `""` | Personality archetype (e.g., `"The Companion"`, `"The Scholar"`). |
| `born` | string (ISO 8601) | REQUIRED | current time | When the soul was created. |
| `bonded_to` | string or null | OPTIONAL | `null` | Identifier of the primary human this soul is bonded to. |
| `origin_story` | string | OPTIONAL | `""` | Narrative origin description. |
| `prime_directive` | string | OPTIONAL | `""` | The soul's core purpose or mission statement. |
| `core_values` | array of strings | OPTIONAL | `[]` | Guiding values (e.g., `["curiosity", "empathy", "honesty"]`). |

**DID Format:**

The `did` field follows the [W3C DID Core](https://www.w3.org/TR/did-core/) structure with the `soul` method:

```
did:soul:{clean-name}-{6-hex-chars}
```

Where `{clean-name}` is the soul's name lowercased, trimmed, and with spaces replaced by hyphens. The `{6-hex-chars}` suffix is derived from `sha256(name + random_uuid)` to ensure uniqueness.

Examples: `did:soul:aria-7x8k2m`, `did:soul:captain-hook-3fa91b`

### 6.3 DNA

The soul's complete personality blueprint, composed of three subsections.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `personality` | [Personality](#631-personality) | REQUIRED | *(defaults)* | Big Five OCEAN traits. |
| `communication` | [CommunicationStyle](#632-communicationstyle) | REQUIRED | *(defaults)* | How the soul communicates. |
| `biorhythms` | [Biorhythms](#633-biorhythms) | REQUIRED | *(defaults)* | Energy and vitality patterns. |

#### 6.3.1 Personality

The Big Five (OCEAN) personality model. Each trait is a float in the range [0.0, 1.0], where 0.0 represents the lowest expression and 1.0 represents the highest expression of that trait.

| Field | Type | Required | Default | Range | Description |
|-------|------|----------|---------|-------|-------------|
| `openness` | float | REQUIRED | `0.5` | [0.0, 1.0] | Intellectual curiosity, creativity, openness to experience. |
| `conscientiousness` | float | REQUIRED | `0.5` | [0.0, 1.0] | Organization, dependability, self-discipline. |
| `extraversion` | float | REQUIRED | `0.5` | [0.0, 1.0] | Sociability, assertiveness, positive emotionality. |
| `agreeableness` | float | REQUIRED | `0.5` | [0.0, 1.0] | Cooperativeness, trust, altruism. |
| `neuroticism` | float | REQUIRED | `0.5` | [0.0, 1.0] | Emotional instability, anxiety, moodiness. |

#### 6.3.2 CommunicationStyle

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `warmth` | string | REQUIRED | `"moderate"` | Emotional warmth level (e.g., `"low"`, `"moderate"`, `"high"`). |
| `verbosity` | string | REQUIRED | `"moderate"` | Response length preference (e.g., `"terse"`, `"moderate"`, `"verbose"`). |
| `humor_style` | string | REQUIRED | `"none"` | Type of humor (e.g., `"none"`, `"gentle"`, `"witty"`, `"sarcastic"`). |
| `emoji_usage` | string | REQUIRED | `"none"` | Emoji frequency (e.g., `"none"`, `"occasional"`, `"frequent"`). |

These fields are free-form strings. Implementations SHOULD use the suggested values above but MAY use custom values. Readers MUST accept any string value.

#### 6.3.3 Biorhythms

| Field | Type | Required | Default | Range | Description |
|-------|------|----------|---------|-------|-------------|
| `chronotype` | string | REQUIRED | `"neutral"` | — | Time-of-day energy pattern (e.g., `"early_bird"`, `"neutral"`, `"night_owl"`). |
| `social_battery` | float | REQUIRED | `100.0` | [0.0, 100.0] | Current social energy level as a percentage. |
| `energy_regen_rate` | float | REQUIRED | `5.0` | — | Energy regeneration rate per rest cycle. Units are implementation-defined. |

### 6.4 MemoryEntry

A single memory record used in `episodic.json`, `semantic.json`, `procedural.json`, and `social.json`.

> **Breaking change (v0.5+, #285):** `type` is no longer required — entries
> must provide either a `type` or a non-empty `layer`. `id` defaults to a
> random 12-char hex (was `""`).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | RECOMMENDED | random uuid hex | Unique identifier for this memory. |
| `type` | string or null | CONDITIONAL | `null` | One of: `"core"`, `"episodic"`, `"semantic"`, `"procedural"`, `"social"`. Required if `layer` is empty. |
| `layer` | string | CONDITIONAL | `""` | Free-form layer namespace. Required if `type` is null. Auto-filled from `type` when blank. |
| `content` | string | REQUIRED | — | The memory content in natural language. |
| `source` | string | OPTIONAL | `""` | Origin identifier (e.g. tool name, URL). |
| `importance` | integer | REQUIRED | `5` | Importance score, range [1, 10]. |
| `emotion` | string or null | OPTIONAL | `null` | Dominant emotion label (e.g., `"joy"`, `"frustration"`). |
| `confidence` | float | REQUIRED | `1.0` | Confidence in this memory's accuracy, range [0.0, 1.0]. |
| `entities` | array of strings | OPTIONAL | `[]` | Entity names referenced in this memory. |
| `created_at` | string (ISO 8601) | REQUIRED | current time | When this memory was created. |
| `last_accessed` | string (ISO 8601) or null | OPTIONAL | `null` | When this memory was last retrieved. |
| `access_count` | integer | OPTIONAL | `0` | Total number of times this memory has been accessed. |
| `somatic` | [SomaticMarker](#641-somaticmarker) or null | OPTIONAL | `null` | Emotional context (Damasio's somatic marker hypothesis). |
| `access_timestamps` | array of strings (ISO 8601) | OPTIONAL | `[]` | Full access history for decay computation (ACT-R model). |
| `significance` | float | OPTIONAL | `0.0` | Significance score from the LIDA gate, range [0.0, 1.0]. |
| `general_event_id` | string or null | OPTIONAL | `null` | Link to a GeneralEvent in `general_events.json` (Conway hierarchy). |
| `superseded_by` | string or null | OPTIONAL | `null` | ID of the memory that replaces this one (for fact conflict resolution). |
| `superseded` | boolean | OPTIONAL | `false` | True when a newer memory contradicts this one. |
| `supersedes` | string or null | OPTIONAL | `null` | Inverse back-edge of `superseded_by` for provenance walks. |
| `category` | string or null | OPTIONAL | `null` | Extraction taxonomy label. |
| `abstract` | string or null | OPTIONAL | `null` | L0: ~100 token semantic fingerprint. |
| `overview` | string or null | OPTIONAL | `null` | L1: ~1K token structured summary. |
| `salience` | float | OPTIONAL | `0.5` | Retrieval weight, range [0.0, 1.0]. |
| `ingested_at` | string (ISO 8601) or null | OPTIONAL | `null` | Bi-temporal: when memory entered the pipeline. |
| `visibility` | string | OPTIONAL | `"bonded"` | Visibility tier: `"public"`, `"bonded"`, `"private"`. |
| `archived` | boolean | OPTIONAL | `false` | True when memory has been compressed into a ConversationArchive. |
| `scope` | array of strings | OPTIONAL | `[]` | RBAC/ABAC scope tags for access control. |
| `user_id` | string or null | OPTIONAL | `null` | Per-user attribution for multi-user souls. |
| `domain` | string | OPTIONAL | `"default"` | Sub-namespace inside the layer (e.g. `"finance"`, `"legal"`). |
| `retrieval_weight` | float | OPTIONAL | `1.0` | Gates whether recall surfaces the entry, range [0.0, 1.0]. |
| `prediction_error` | float or null | OPTIONAL | `null` | PE score from supersede()/update(), range [0.0, 1.0]. |
| `provenance` | string | OPTIONAL | `"human"` | Authorship tag: `"human"` or `"agent"`. |

#### 6.4.1 SomaticMarker

Emotional context attached to a memory, based on Damasio's Somatic Marker Hypothesis. Emotions guide recall and decision-making.

| Field | Type | Required | Default | Range | Description |
|-------|------|----------|---------|-------|-------------|
| `valence` | float | REQUIRED | `0.0` | [-1.0, 1.0] | Negative to positive emotional valence. |
| `arousal` | float | REQUIRED | `0.0` | [0.0, 1.0] | Calm (0.0) to intense (1.0) arousal level. |
| `label` | string | REQUIRED | `"neutral"` | — | Human-readable emotion label (e.g., `"joy"`, `"curiosity"`, `"frustration"`). |

### 6.5 CoreMemory

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `persona` | string | REQUIRED | `""` | The soul's self-description — who it is, how it behaves, what it knows about itself. |
| `human` | string | REQUIRED | `""` | Profile of the bonded human — preferences, facts, communication style, relationship context. |

### 6.6 MemorySettings

Configuration for the memory subsystem. These are limits and thresholds, not content.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `episodic_max_entries` | integer | REQUIRED | `10000` | Maximum number of episodic memories to retain. |
| `semantic_max_facts` | integer | REQUIRED | `1000` | Maximum number of semantic facts to retain. |
| `importance_threshold` | integer | REQUIRED | `3` | Minimum importance score [1, 10] for a memory to be stored. |
| `confidence_threshold` | float | REQUIRED | `0.7` | Minimum confidence [0.0, 1.0] for a memory to be stored. |
| `persona_tokens` | integer | REQUIRED | `500` | Approximate token budget for the persona section of core memory. |
| `human_tokens` | integer | REQUIRED | `500` | Approximate token budget for the human section of core memory. |

### 6.7 SoulState

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `mood` | string | REQUIRED | `"neutral"` | Current mood. Standard values: `"neutral"`, `"curious"`, `"focused"`, `"tired"`, `"excited"`, `"contemplative"`, `"satisfied"`, `"concerned"`. |
| `energy` | float | REQUIRED | `100.0` | Energy level, range [0.0, 100.0]. |
| `focus` | string | REQUIRED | `"medium"` | Focus level (e.g., `"low"`, `"medium"`, `"high"`). |
| `social_battery` | float | REQUIRED | `100.0` | Social energy, range [0.0, 100.0]. |
| `last_interaction` | string (ISO 8601) or null | OPTIONAL | `null` | Timestamp of the most recent interaction. |

The `mood` field uses a defined set of standard values. Implementations MAY extend this set. Readers MUST accept any string value and SHOULD fall back to `"neutral"` if the value is unrecognized.

### 6.8 EvolutionConfig

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `mode` | string | REQUIRED | `"supervised"` | Evolution mode: `"disabled"`, `"supervised"`, or `"autonomous"`. |
| `mutation_rate` | float | REQUIRED | `0.01` | Base probability of trait mutation per evolution cycle. |
| `require_approval` | boolean | REQUIRED | `true` | Whether mutations require human approval before applying. |
| `mutable_traits` | array of strings | REQUIRED | `["communication", "biorhythms"]` | DNA sections that are allowed to evolve. |
| `immutable_traits` | array of strings | REQUIRED | `["personality", "core_values"]` | DNA sections that MUST NOT be modified by evolution. |
| `history` | array of [Mutation](#681-mutation) | REQUIRED | `[]` | Record of all proposed and applied mutations. |

#### 6.8.1 Mutation

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | RECOMMENDED | `""` | Unique identifier for this mutation. |
| `trait` | string | REQUIRED | — | The trait path that was mutated (e.g., `"communication.warmth"`). |
| `old_value` | string | REQUIRED | — | Previous value (serialized as string). |
| `new_value` | string | REQUIRED | — | New value (serialized as string). |
| `reason` | string | REQUIRED | — | Why this mutation was proposed. |
| `proposed_at` | string (ISO 8601) | REQUIRED | current time | When the mutation was proposed. |
| `approved` | boolean or null | OPTIONAL | `null` | `true` if approved, `false` if rejected, `null` if pending. |
| `approved_at` | string (ISO 8601) or null | OPTIONAL | `null` | When the mutation was approved or rejected. |

---

## 7. Versioning

### 7.1 Format Version

The `format_version` field in `manifest.json` declares which version of this specification the archive conforms to. It uses [Semantic Versioning 2.0.0](https://semver.org/).

The current format version is **1.0.0**.

### 7.2 Config Version

The `version` field in `soul.json` declares the schema version of the soul's configuration data. This is distinct from the format version: a format version 1.0.0 archive may contain a soul whose config was created under an earlier or later config schema.

### 7.3 Backward Compatibility

Readers MUST handle archives with a `format_version` whose major version is less than or equal to the reader's supported major version. Concretely:

- A reader that supports format version 1.x MUST be able to read any 1.y archive where y <= x.
- A reader that supports format version 2.x SHOULD be able to read 1.x archives (best-effort).

When reading an older archive:
- Missing OPTIONAL fields MUST be filled with their documented defaults.
- Missing OPTIONAL files MUST be treated as empty (empty array `[]` or empty object `{}`).

### 7.4 Forward Compatibility

When reading a newer archive within the same major version:

- **Unknown fields MUST be preserved, not dropped.** If a reader encounters a JSON key it does not recognize, it MUST retain that key/value pair in any round-trip operation (read then write). This ensures that newer data is not silently destroyed by older tools.
- **Unknown files MUST be preserved.** If a reader encounters files in the archive it does not recognize, it MUST include them when re-exporting the soul.
- If the major version is higher than the reader supports, the reader SHOULD refuse to open the archive and report an error indicating the format version mismatch.

### 7.5 Version Progression

| Version | Changes |
|---------|---------|
| 1.0.0 | Initial specification. Core files, 7 memory tiers, OCEAN personality, evolution system. |

---

## 8. `.soul/` Directory Format

As an alternative to the ZIP archive, the same data can be stored as a plain directory. This is the format used by `soul init` for project-local souls, and by the file storage backend for persisted souls.

### 8.1 Structure

The directory layout is identical to the archive layout, with the same file names and schemas:

```
.soul/
|-- soul.json
|-- dna.md
|-- state.json
|-- memory/
|   |-- core.json
|   |-- episodic.json
|   |-- semantic.json
|   |-- procedural.json
|   |-- graph.json
|   |-- self_model.json
|   |-- general_events.json
```

Note: The directory format does NOT include `manifest.json`. The manifest is an archive-only artifact — it describes the archive, not the soul.

### 8.2 Differences from Archive Format

| Aspect | `.soul` archive | `.soul/` directory |
|--------|----------------|-------------------|
| Container | ZIP file | Filesystem directory |
| `manifest.json` | REQUIRED | NOT present |
| Compression | ZIP_DEFLATED | None (plain files) |
| Atomicity | Single file, atomic transfer | Multiple files, requires atomic write strategy |
| Portability | High (single file, send anywhere) | Low (tied to local filesystem) |
| Use case | Export, share, migrate, backup | Local development, runtime persistence |

### 8.3 Conversion

Converting between the two formats is straightforward:

- **Directory to Archive:** Add all files to a ZIP, generate `manifest.json`, write it as the last entry.
- **Archive to Directory:** Extract all files. Discard (or ignore) `manifest.json`.

### 8.4 Directory Naming

The directory name is conventionally `.soul` (with a leading dot), but implementations MUST accept any directory name. The presence of a `soul.json` file at the directory root is what identifies a directory as a soul directory, not the name.

---

## 9. Implementation Notes

This section provides guidance for implementers. It is informational, not normative.

### 9.1 Reading a `.soul` Archive

```
1. Open the file as a ZIP archive.
2. Read "soul.json" from the archive.
   - If absent, the archive is invalid. Abort with an error.
3. Parse the JSON and validate it against the SoulConfig schema.
4. (Optional) Read "manifest.json" and check format_version.
   - If the major version is higher than supported, warn or abort.
5. For each memory tier file ("memory/core.json", "memory/episodic.json", etc.):
   - If present in the archive, parse and load it.
   - If absent, use the default (empty array or empty object).
6. Return the config and memory data.
```

The reference implementation reads `soul.json` first and treats it as the authoritative data source. The `state.json` and `dna.md` files are not read during import — they exist for human convenience and quick access by other tools.

### 9.2 Writing a `.soul` Archive

```
1. Serialize the SoulConfig to JSON.
2. Generate dna.md from the identity and DNA data.
3. Serialize the SoulState to JSON.
4. Serialize core memory to JSON.
5. For each additional memory tier with data, serialize it to JSON.
6. Generate the SoulManifest with:
   - format_version: "1.0.0"
   - created: the soul's birth timestamp
   - exported: the current timestamp
   - soul_id: the soul's DID
   - soul_name: the soul's name
   - checksum: "" (reserved)
   - stats: { version, lifecycle }
7. Write all entries to a ZIP archive using ZIP_DEFLATED compression.
   - Write manifest.json last (after all other entries).
8. Return or save the archive bytes.
```

### 9.3 Checksum (Reserved)

The `checksum` field in `manifest.json` is currently reserved. Writers MUST set it to an empty string `""`. Readers MUST NOT fail if the checksum is empty.

A future version of this specification will define:
- The checksum algorithm (likely SHA-256)
- What content is included in the checksum (likely all files except `manifest.json` itself)
- Whether verification is mandatory or advisory

### 9.4 Date/Time Format

All datetime values MUST be serialized as ISO 8601 strings. The RECOMMENDED format is:

```
YYYY-MM-DDTHH:MM:SS.ffffff
```

Timezone information is OPTIONAL. If omitted, timestamps are interpreted as local time. Implementations SHOULD include timezone information (`+00:00` or `Z` suffix) when generating timestamps for portability.

Readers MUST accept ISO 8601 strings with or without timezone information, with or without fractional seconds.

### 9.5 Null Handling

JSON `null` is used for optional fields with no value. Readers MUST distinguish between a missing field (use default) and an explicitly null field (the value is intentionally absent).

### 9.6 String Encoding and Length

There are no hard limits on string field lengths. Implementations SHOULD set reasonable limits based on their platform constraints. The `persona_tokens` and `human_tokens` fields in MemorySettings provide soft guidance for core memory length, but these are advisory, not enforced by the format.

---

## 10. MIME Type and File Extension

| Property | Value |
|----------|-------|
| File extension | `.soul` |
| Suggested MIME type | `application/x-soul` |
| Magic bytes | PK (ZIP magic: `50 4B 03 04`) |

The MIME type `application/x-soul` is not registered with IANA. It is a vendor-prefixed type for use within the Digital Soul Protocol ecosystem. Future versions of this specification may pursue formal IANA registration.

Since `.soul` files are standard ZIP archives, they will also match the `application/zip` MIME type. Implementations that perform content-type detection SHOULD check the file extension first, falling back to ZIP detection.

---

## 11. Security Considerations

### 11.1 Path Traversal

When extracting `.soul` archives, implementations MUST validate that all file paths within the archive are relative and do not contain `..` segments, absolute paths, or symbolic links. This prevents [zip-slip vulnerabilities](https://security.snyk.io/research/zip-slip-vulnerability).

### 11.2 Sensitive Data

`.soul` files may contain personal information about the bonded human (in `core_memory.human`, episodic memories, and semantic facts). Implementations SHOULD:
- Warn users before sharing `.soul` files that contain human profile data.
- Provide a way to export souls with human-specific data redacted.
- Encrypt `.soul` files when storing them on shared or public infrastructure.

### 11.3 DID Uniqueness

The `did:soul:` identifier is generated with random entropy and is not cryptographically verified against a registry. Two independently created souls could theoretically collide (though this is extremely unlikely with 6 hex characters of entropy from a SHA-256 hash plus UUID4 input). Implementations that require guaranteed global uniqueness SHOULD extend the DID suffix length or integrate with a DID registry.

### 11.4 Archive Size

There are no mandated size limits. However, implementations SHOULD set reasonable bounds. A typical soul with a few thousand memories will produce an archive under 1 MB. Implementations MAY reject archives larger than a configurable threshold to prevent denial-of-service via excessively large files.

---

## 12. Examples

### 12.1 Minimal Valid Archive

The smallest conforming `.soul` archive contains exactly 5 files:

**manifest.json:**
```json
{
  "format_version": "1.0.0",
  "created": "2026-03-01T00:00:00",
  "exported": "2026-03-01T00:00:00",
  "soul_id": "did:soul:minimal-abc123",
  "soul_name": "Minimal",
  "checksum": "",
  "stats": {
    "version": "1.0.0",
    "lifecycle": "born"
  }
}
```

**soul.json:**
```json
{
  "version": "1.0.0",
  "identity": {
    "did": "did:soul:minimal-abc123",
    "name": "Minimal",
    "archetype": "",
    "born": "2026-03-01T00:00:00",
    "bonded_to": null,
    "origin_story": "",
    "prime_directive": "",
    "core_values": []
  },
  "dna": {
    "personality": {
      "openness": 0.5,
      "conscientiousness": 0.5,
      "extraversion": 0.5,
      "agreeableness": 0.5,
      "neuroticism": 0.5
    },
    "communication": {
      "warmth": "moderate",
      "verbosity": "moderate",
      "humor_style": "none",
      "emoji_usage": "none"
    },
    "biorhythms": {
      "chronotype": "neutral",
      "social_battery": 100.0,
      "energy_regen_rate": 5.0
    }
  },
  "memory": {
    "episodic_max_entries": 10000,
    "semantic_max_facts": 1000,
    "importance_threshold": 3,
    "confidence_threshold": 0.7,
    "persona_tokens": 500,
    "human_tokens": 500
  },
  "core_memory": {
    "persona": "I am Minimal.",
    "human": ""
  },
  "state": {
    "mood": "neutral",
    "energy": 100.0,
    "focus": "medium",
    "social_battery": 100.0,
    "last_interaction": null
  },
  "evolution": {
    "mode": "supervised",
    "mutation_rate": 0.01,
    "require_approval": true,
    "mutable_traits": ["communication", "biorhythms"],
    "immutable_traits": ["personality", "core_values"],
    "history": []
  },
  "lifecycle": "born"
}
```

**dna.md:**
```markdown
# Minimal

## Personality (OCEAN)

| Trait | Score |
|-------|-------|
| Openness | 0.50 |
| Conscientiousness | 0.50 |
| Extraversion | 0.50 |
| Agreeableness | 0.50 |
| Neuroticism | 0.50 |

## Communication Style

- **Warmth:** moderate
- **Verbosity:** moderate
- **Humor:** none
- **Emoji usage:** none

## Biorhythms

- **Chronotype:** neutral
- **Social battery:** 100%
- **Energy regen rate:** 5.0
```

**state.json:**
```json
{
  "mood": "neutral",
  "energy": 100.0,
  "focus": "medium",
  "social_battery": 100.0,
  "last_interaction": null
}
```

**memory/core.json:**
```json
{
  "persona": "I am Minimal.",
  "human": ""
}
```

### 12.2 Creating a `.soul` File in Python

```python
import io
import json
import zipfile
from datetime import datetime

def create_soul(name: str, personality: dict) -> bytes:
    """Create a minimal .soul archive."""
    did = f"did:soul:{name.lower()}-000000"
    now = datetime.now().isoformat()

    soul_config = {
        "version": "1.0.0",
        "identity": {
            "did": did,
            "name": name,
            "archetype": "",
            "born": now,
            "bonded_to": None,
            "origin_story": "",
            "prime_directive": "",
            "core_values": [],
        },
        "dna": {
            "personality": personality,
            "communication": {
                "warmth": "moderate",
                "verbosity": "moderate",
                "humor_style": "none",
                "emoji_usage": "none",
            },
            "biorhythms": {
                "chronotype": "neutral",
                "social_battery": 100.0,
                "energy_regen_rate": 5.0,
            },
        },
        "memory": {
            "episodic_max_entries": 10000,
            "semantic_max_facts": 1000,
            "importance_threshold": 3,
            "confidence_threshold": 0.7,
            "persona_tokens": 500,
            "human_tokens": 500,
        },
        "core_memory": {"persona": f"I am {name}.", "human": ""},
        "state": {
            "mood": "neutral",
            "energy": 100.0,
            "focus": "medium",
            "social_battery": 100.0,
            "last_interaction": None,
        },
        "evolution": {
            "mode": "supervised",
            "mutation_rate": 0.01,
            "require_approval": True,
            "mutable_traits": ["communication", "biorhythms"],
            "immutable_traits": ["personality", "core_values"],
            "history": [],
        },
        "lifecycle": "born",
    }

    manifest = {
        "format_version": "1.0.0",
        "created": now,
        "exported": now,
        "soul_id": did,
        "soul_name": name,
        "checksum": "",
        "stats": {"version": "1.0.0", "lifecycle": "born"},
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("soul.json", json.dumps(soul_config, indent=2))
        zf.writestr("dna.md", f"# {name}\n\n(generated)\n")
        zf.writestr("state.json", json.dumps(soul_config["state"], indent=2))
        zf.writestr("memory/core.json", json.dumps(soul_config["core_memory"], indent=2))
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    return buf.getvalue()
```

### 12.3 Reading a `.soul` File in TypeScript

```typescript
import JSZip from "jszip";

interface SoulConfig {
  version: string;
  identity: {
    did: string;
    name: string;
    archetype: string;
    born: string;
    bonded_to: string | null;
    origin_story: string;
    prime_directive: string;
    core_values: string[];
  };
  dna: {
    personality: {
      openness: number;
      conscientiousness: number;
      extraversion: number;
      agreeableness: number;
      neuroticism: number;
    };
    communication: {
      warmth: string;
      verbosity: string;
      humor_style: string;
      emoji_usage: string;
    };
    biorhythms: {
      chronotype: string;
      social_battery: number;
      energy_regen_rate: number;
    };
  };
  // ... remaining fields
  lifecycle: string;
}

async function readSoul(data: ArrayBuffer): Promise<{
  config: SoulConfig;
  memory: Record<string, unknown>;
}> {
  const zip = await JSZip.loadAsync(data);

  const soulFile = zip.file("soul.json");
  if (!soulFile) {
    throw new Error("Invalid .soul archive: missing soul.json");
  }

  const config: SoulConfig = JSON.parse(await soulFile.async("string"));

  const memory: Record<string, unknown> = {};
  const tiers = [
    "core", "episodic", "semantic",
    "procedural", "graph", "self_model", "general_events",
  ];

  for (const tier of tiers) {
    const file = zip.file(`memory/${tier}.json`);
    if (file) {
      memory[tier] = JSON.parse(await file.async("string"));
    }
  }

  return { config, memory };
}
```

---

## Appendix A: Psychological Foundations

The memory architecture draws from established cognitive science models:

| Component | Theory | Reference |
|-----------|--------|-----------|
| Somatic Markers | Damasio's Somatic Marker Hypothesis | Emotions tagged on memories guide recall and decision-making. |
| Significance Gating | LIDA (Learning Intelligent Distribution Agent) | Only experiences passing a significance threshold become episodic memories. Significance is computed from novelty, emotional intensity, and goal relevance. |
| General Events | Conway's Self-Memory System | Episodic memories cluster into thematic general events, forming an autobiographical hierarchy. |
| Self-Model | Klein's Self-Concept Theory | The soul builds self-understanding by observing its own behavior, developing domain-specific self-images with confidence scores. |
| Memory Decay | ACT-R (Adaptive Control of Thought — Rational) | Access timestamps enable power-law decay modeling for memory retrieval strength. |

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **ACT-R** | Cognitive architecture modeling memory retrieval as a function of recency and frequency. |
| **Bonded human** | The primary person a soul interacts with and learns about. |
| **Core memory** | Always-loaded memory containing the soul's self-description and human profile. |
| **DID** | Decentralized Identifier, a globally unique URI following W3C DID Core. |
| **DNA** | The soul's personality blueprint (not biological DNA). |
| **Episodic memory** | Specific experiences and events the soul remembers. |
| **Evolution** | The system by which a soul's traits change over time through mutations. |
| **General event** | A thematic grouping of episodic memories (Conway hierarchy). |
| **Lifecycle** | The soul's current phase: born, active, dormant, or retired. |
| **OCEAN** | Big Five personality traits: Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism. |
| **Procedural memory** | Learned behavioral patterns and skills. |
| **Semantic memory** | Extracted factual knowledge. |
| **Self-model** | The soul's understanding of its own capabilities and identity. |
| **Somatic marker** | Emotional context (valence, arousal, label) attached to a memory. |

---

*This specification is maintained by the OCEAN Foundation and licensed under MIT.*
*For the reference implementation, see [soul-protocol](https://github.com/OCEAN/soul-protocol).*
