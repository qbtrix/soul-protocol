---
{
  "title": "Runtime Types: The Complete Soul Protocol Pydantic Model Library",
  "summary": "`types.py` is the canonical data model layer for Soul Protocol — over 30 Pydantic models covering identity, personality (OCEAN), psychology-informed memory, emotional state, evolution, and interaction. It is the schema backbone that all other runtime modules depend on.",
  "concepts": [
    "SoulConfig",
    "Identity",
    "DNA",
    "Personality",
    "OCEAN",
    "Biorhythms",
    "MemoryEntry",
    "SomaticMarker",
    "SignificanceScore",
    "GeneralEvent",
    "SelfImage",
    "Interaction",
    "MemoryType",
    "MemoryCategory",
    "Mutation",
    "Rubric",
    "progressive disclosure",
    "multi-participant"
  ],
  "categories": [
    "runtime",
    "data models",
    "memory",
    "identity"
  ],
  "source_docs": [
    "8c88acd6ba1a23c7"
  ],
  "backlinks": null,
  "word_count": 429,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`types.py` defines every persistent and runtime data structure in Soul Protocol. It is the single source of truth for what a soul *is* — all serialization, deserialization, storage, and inter-module communication flows through these models.

## Identity Layer

`Identity` holds a soul's DID, name, archetype, bonds, and lifecycle metadata. The `model_post_init` hook auto-migrates the legacy `bonded_to: str` field into the newer `bonds: list[BondTarget]` list:

```python
if self.bonded_to and not self.bonds:
    self.bonds.append(BondTarget(id=self.bonded_to, bond_type="human"))
```

This silent migration means existing `.soul` files written with the old schema load correctly without a schema migration step.

## Personality: OCEAN and DNA

`Personality` encodes the Big Five OCEAN model as five floats in `[0.0, 1.0]`. `Biorhythms` configures energy dynamics — defaulting to zero drain/regen for tool-use agents that do not simulate fatigue. `DNA` bundles `Personality`, `CommunicationStyle`, and `Biorhythms` into the complete behavioral blueprint.

## Psychology-Informed Memory Fields

Several models are grounded in cognitive science literature:

- **`SomaticMarker`** (Damasio): Attaches emotional context (valence, arousal, label) to memories. Emotions guide recall and decision-making.
- **`SignificanceScore`** (LIDA): A four-dimension gate (novelty, emotional intensity, goal relevance, content richness) that controls whether an experience is stored as episodic memory.
- **`GeneralEvent`** (Conway's Self-Memory System): Groups episodes into thematic clusters and lifetime periods.
- **`SelfImage`** (Klein): Domain-specific self-concept facets built from accumulated interaction evidence.

## MemoryEntry: Progressive Content Loading

`MemoryEntry` carries three content layers added in v0.3.4:

| Field | Size | Purpose |
|-------|------|---------|
| `content` | Full | Complete memory text |
| `overview` | ~1K tokens | Structured summary (L1) |
| `abstract` | ~100 tokens | Semantic fingerprint (L0) |

This enables progressive disclosure: recall operations can return `abstract` for non-critical memories and `content` only for high-salience ones, reducing context window usage.

## Interaction: Multi-Participant Model

`Interaction` was generalized from a 2-party to an N-participant model. Backward compatibility is preserved via:

- A `model_validator` that auto-converts legacy `user_input`/`agent_output` kwargs to the `participants` list.
- `user_input` and `agent_output` properties that search for the first matching role.
- A `from_pair()` factory for the common 2-party case.

## SoulConfig: The Complete Serializable Soul

`SoulConfig` is the root model for persistence — it bundles `Identity`, `DNA`, `MemorySettings`, `CoreMemory`, `SoulState`, `EvolutionConfig`, and `LifecycleState` into one serializable unit. The `interaction_count` field drives auto-consolidation: after every N observations, the memory manager archives and reflects.

## Known Gaps

The `scope: list[str]` field on `MemoryEntry` uses hierarchical glob matching (`org:sales:*`), but the glob logic lives in `spec/scope.py`, not in `types.py`. Documentation of the expected scope format is only in comments and the scope module — callers must read both to understand the contract.