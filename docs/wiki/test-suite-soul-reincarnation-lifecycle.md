---
{
  "title": "Test Suite: Soul Reincarnation Lifecycle",
  "summary": "Validates that `Soul.reincarnate()` correctly transitions a soul to a new identity while preserving accumulated state. The suite ensures that reincarnation is not a hard reset — personality, memories, values, archetype, and bond all carry forward, while the DID and incarnation counter change to mark the new life.",
  "concepts": [
    "reincarnation",
    "Soul.reincarnate",
    "DID rotation",
    "incarnation counter",
    "previous_lives",
    "DNA preservation",
    "memory transfer",
    "bond strength",
    "logarithmic growth",
    "lifecycle state",
    "personality traits",
    "OCEAN model"
  ],
  "categories": [
    "testing",
    "soul lifecycle",
    "identity management",
    "memory continuity",
    "test"
  ],
  "source_docs": [
    "4c177d58c06ccbab"
  ],
  "backlinks": null,
  "word_count": 493,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Reincarnation is one of Soul Protocol's core lifecycle operations. When a soul is reincarnated, it should receive a fresh decentralized identity (DID) while retaining the psychological and relational state it built up. Without these tests, a refactor of `Soul.reincarnate()` could silently drop memories or reset personality traits, breaking the continuity guarantee at the heart of the protocol.

## What is Tested

### Identity Transition

```python
async def test_basic_reincarnation():
    original = await Soul.birth("Aria", archetype="The Creator")
    reborn = await Soul.reincarnate(original)
    assert reborn.did != original.did
    assert reborn.did.startswith("did:soul:aria-")
    assert reborn.lifecycle == LifecycleState.ACTIVE
```

The test asserts a new DID is minted, the name-based DID prefix is maintained, and the lifecycle state starts fresh at `ACTIVE`. A separate test (`test_reincarnation_with_new_name`) confirms that an optional `name` argument also updates the DID prefix, enabling renames during reincarnation.

### Incarnation Counter

The `identity.incarnation` field is an ever-increasing integer. Three successive reincarnations must yield counters 1, 2, and 3. This prevents ambiguity in audit trails when multiple incarnations of the same soul have existed.

### Previous Lives Tracking

The `identity.previous_lives` list accumulates old DIDs. After each reincarnation, the prior DID is appended so that lineage can always be reconstructed. The test walks through two reincarnations and verifies both prior DIDs appear in order.

### Personality (DNA) Preservation

```python
original._dna.personality.openness = 0.9
original._dna.personality.neuroticism = 0.1
reborn = await Soul.reincarnate(original)
assert reborn.dna.personality.openness == pytest.approx(0.9)
```

DNA mutations made during a soul's life carry into the next incarnation. Without this test, an implementation could re-initialize DNA from defaults on reincarnation, erasing learned personality drift.

### Core Values and Archetype

Values like `["empathy", "creativity", "honesty"]` and archetype strings are immutable commitments set at birth. The tests confirm they survive the transition intact — these fields are not personality drift but identity anchors.

### Memory Transfer

Semantic memories stored with `soul.remember()` are recalled by keyword after reincarnation. This is the most critical continuity guarantee: a soul must remember what it learned across lives.

### Bond Preservation with Logarithmic Growth

Bond state — including the bonded DID and numeric bond strength — carries forward. The assertion uses a logarithmic formula: a strength of 20 applied to the default base of 50 produces `50 + 20*(50/100) = 60.0`. The comment in the test (`# Updated: phase1-ablation-fixes`) notes that the assertion was updated when the bond growth model was changed from linear to logarithmic, which shows this test caught a real behavioral change.

## Data Flow

```
Soul.reincarnate(original)
  └─ copies DNA, memories, values, archetype, bond from original
  └─ mints new DID (name + random suffix)
  └─ increments incarnation counter
  └─ appends old DID to previous_lives
  └─ returns new Soul instance with LifecycleState.ACTIVE
```

## Known Gaps

No known gaps are flagged in this file. The bond assertion was updated when growth math changed (`phase1-ablation-fixes`), indicating the test is actively maintained. There is no test for reincarnating a soul that has already been exported to a `.soul` file — the round-trip path (awaken then reincarnate) is not covered here.