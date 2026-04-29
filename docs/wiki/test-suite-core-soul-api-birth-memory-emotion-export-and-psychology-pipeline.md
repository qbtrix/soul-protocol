---
{
  "title": "Test Suite: Core Soul API — Birth, Memory, Emotion, Export, and Psychology Pipeline",
  "summary": "The primary integration test suite for the `Soul` class, covering the full API surface from construction through the psychology pipeline. It validates that soul birth, memory operations, emotional state, import/export round-trips, system prompt generation, and the attention gate all work correctly together.",
  "concepts": [
    "Soul.birth",
    "Soul.remember",
    "Soul.recall",
    "Soul.feel",
    "Soul.export",
    "Soul.awaken",
    "Soul.observe",
    "psychology pipeline",
    "attention gate",
    "self-model",
    "SelfModelManager",
    "LifecycleState",
    "Mood",
    "energy",
    "DID",
    "from_markdown"
  ],
  "categories": [
    "testing",
    "core API",
    "soul lifecycle",
    "psychology pipeline",
    "test"
  ],
  "source_docs": [
    "f9ef5bd53cca6858"
  ],
  "backlinks": null,
  "word_count": 507,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

This file is the most comprehensive test of Soul Protocol's runtime. It tests `Soul` as an end-to-end object rather than testing subsystems in isolation. Because `Soul` orchestrates many subsystems (memory, emotion, psychology pipeline, serialization), regressions often appear here first even when they originate in a subsystem.

## Birth and Defaults

```python
async def test_birth():
    soul = await Soul.birth("Aria", archetype="The Compassionate Creator")
    assert soul.did.startswith("did:soul:aria-")
    assert soul.lifecycle == LifecycleState.ACTIVE
    assert soul.state.mood == Mood.NEUTRAL
    assert soul.state.energy == 100.0
```

The DID uses the soul's name as a prefix, which makes DIDs human-readable while the suffix ensures uniqueness. Defaults are explicit: NEUTRAL mood, full energy, ACTIVE lifecycle.

## Memory Operations

`remember()` returns a non-empty memory ID — callers can store the ID for later targeted recall or deletion. `recall()` uses keyword search and returns at least one result when the query matches stored content. These two operations together are the minimum viable memory API.

## Emotional State

`feel()` applies delta-based changes:
- Setting a mood directly: `soul.feel(mood=Mood.TIRED)`
- Applying energy deltas: `soul.feel(energy=-20)` reduces energy from 100 to 80

The delta model (rather than absolute assignment for energy) prevents callers from setting energy to arbitrary values and ensures changes compose correctly when multiple systems (interaction drain, rest, etc.) modify energy simultaneously.

## Export and Awaken Round-Trips

Two round-trip tests verify different levels of fidelity:
1. **Basic identity preservation**: Name, archetype, DID, lifecycle state survive `export()` → `awaken()`
2. **Memory preservation**: Both episodic and semantic memories survive. Without this, a soul would lose its learned context every time it was saved and reloaded.
3. **Full config round-trip**: `Soul.save()` + `load_soul_full()` preserves config and all memory tiers together.

## Serialization: serialize() and from_markdown()

`serialize()` returns a `SoulConfig` object that can reconstruct an equivalent soul. The round-trip test creates a new soul from the config and verifies equality. `from_markdown()` parses a `SOUL.md` string format — a human-readable alternative to YAML/JSON configs.

## Psychology Pipeline

```python
async def test_observe_psychology_pipeline():
    # observe 5+ interactions, verify all modules fire
```

After 5+ interactions, the full pipeline must have run: attention gate, somatic markers, self-model updates. This integration test catches cases where a module is silently skipped due to a condition check that's too restrictive.

## Attention Gate

```python
async def test_attention_gate_filters_mundane():
    # Mundane interactions skip episodic storage, meaningful ones are stored
```

The attention gate is what prevents soul memory from filling with low-value noise. Short or generic messages should not reach episodic storage. The test was updated (`phase1-ablation-fixes`) to pass a raised significance threshold (0.5) and account for a short-message penalty — both changes reflect calibration of the significance scoring system.

## Self-Model

`soul.self_model` provides access to `SelfModelManager`. The persistence test verifies that self-model state survives export → awaken, which prevents the soul from losing its self-understanding between sessions.

## Known Gaps

The `test_observe()` test notes that with default biorhythms, energy does not drain. Energy drain is "opt-in for companion souls via Biorhythms config." This means the default test covers a simplified case; there is no test here for energy drain behavior with custom biorhythms.