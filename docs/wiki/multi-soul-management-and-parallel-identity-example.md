---
{
  "title": "Multi-Soul Management and Parallel Identity Example",
  "summary": "Shows how to create and manage multiple independent Soul instances in a single process, each with distinct archetypes, values, and memory spaces. The example covers the full lifecycle from birth to export and reawakening, demonstrating that memory isolation is maintained across souls and that soul files persist identity correctly across process restarts.",
  "concepts": [
    "multi-soul",
    "Soul.birth",
    "Soul.awaken",
    "Soul.export",
    "memory isolation",
    "DID",
    "decentralized identifier",
    "MemoryType",
    "semantic memory",
    "soul lifecycle",
    "personality archetype",
    "emotional state",
    "persistence",
    "soul file format"
  ],
  "categories": [
    "examples",
    "identity",
    "memory",
    "soul-protocol"
  ],
  "source_docs": [
    "693d0d9214e303a8"
  ],
  "backlinks": null,
  "word_count": 532,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`multi_soul.py` addresses one of the most common integration questions: can an application host multiple AI companions simultaneously, and will each soul's memories stay isolated? This example answers both questions with a concrete two-soul scenario — Aria (a thoughtful companion focused on ML topics) and Luna (a creative writer handling story requests).

## Why Multiple Souls Matter

A chat platform, customer support system, or game might maintain dozens or hundreds of active soul instances — one per user, or one per conversation context. Without memory isolation between souls, a fact learned in one user's conversation would bleed into another user's context, a serious privacy and correctness failure. This example demonstrates the isolation guarantee.

## Soul Construction with Differentiated Identities

```python
aria = await Soul.birth(
    name="Aria",
    archetype="The Thoughtful Companion",
    values=["curiosity", "empathy", "honesty"],
)

luna = await Soul.birth(
    name="Luna",
    archetype="The Creative Writer",
    values=["creativity", "imagination", "wit"],
)
```

Each soul receives a stable DID (Decentralized Identifier) on birth, shown by `soul.did[:20]`. DIDs are the portable identity anchor — they survive export, reawakening, and platform migration. The archetype and values fields shape both the soul's persona string and its memory extraction heuristics.

## Memory Isolation in Practice

After teaching Aria about machine learning and Luna about story writing, the example queries each soul independently:

```python
aria_memories = await aria.recall("machine learning", limit=3)
luna_memories = await luna.recall("story", limit=3)
```

Aria's recall returns ML-related memories; Luna's returns story-related ones. If memory leaked between souls (e.g., through a shared in-process store), Aria would incorrectly recall story content. The test is implicit but meaningful.

## State After Observation

Each soul tracks its own emotional state independently:

```python
print(f"{aria.name}: mood={aria.state.mood.value}, energy={aria.state.energy:.0f}%")
print(f"{luna.name}: mood={luna.state.mood.value}, energy={luna.state.energy:.0f}%")
```

State divergence after different interactions confirms that the two souls are truly independent in-memory objects, not shared state with different views.

## Export and Reawakening

The persistence round-trip is the most important section:

```python
await aria.export("aria.soul")
await luna.export("luna.soul")

aria2 = await Soul.awaken("aria.soul")
memories = await aria2.recall("machine learning", limit=3)
print(f"Reloaded {aria2.name}: {len(memories)} ML memory(ies) preserved")
```

`Soul.export()` writes the soul's complete state — DNA, memories, state, bond scores — to a `.soul` file (a zip archive). `Soul.awaken()` reads it back. The final assertion that ML memories are preserved confirms that the serialization round-trip is lossless.

## MemoryType Usage

The example uses explicit `MemoryType.SEMANTIC` when calling `soul.remember()` directly. This bypasses the automatic extraction pipeline and stores a fact directly as a semantic memory. This is useful when the caller already knows the memory type and doesn't want the overhead of the full observe pipeline for programmatically generated facts.

## Data Flow

```
Soul.birth() → in-memory Soul object with unique DID
  ↓
Soul.observe(Interaction) → automatic memory extraction and state update
Soul.remember(content, type=MemoryType.SEMANTIC) → direct storage
  ↓
Soul.recall(query) → BM25 + salience-weighted retrieval
  ↓
Soul.export(path) → .soul zip archive
Soul.awaken(path) → restored Soul object
```

## Known Gaps

- The example does not show concurrent soul management patterns (e.g., asyncio.gather across multiple souls). High-throughput applications will need to understand whether soul operations are coroutine-safe for parallel `observe()` calls on the same soul instance.
- Bond tracking (mentioned in v0.2.3 features) is referenced in the file header but not exercised in the example body — no bond strength queries are shown.