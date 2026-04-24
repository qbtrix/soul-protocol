---
{
  "title": "End-to-End New Soul Primitives Test — Bond, Skills, Retirement, and Reincarnation",
  "summary": "End-to-end test suite for newer soul-protocol primitives introduced post-v1: bond mechanics, skill registry, lifecycle state transitions (active → retired → reincarnated), and `.soul` archive integrity. Tests validate the logarithmic bond growth curve and the presence of `dna.md` in exported archives.",
  "concepts": [
    "bond strength",
    "logarithmic growth",
    "SkillRegistry",
    "Soul retirement",
    "reincarnation",
    "incarnation counter",
    "LifecycleState",
    "dna.md",
    "soul archive",
    "pack_soul",
    "unpack_soul",
    "DID identity"
  ],
  "categories": [
    "testing",
    "soul-lifecycle",
    "bond-mechanics",
    "test"
  ],
  "source_docs": [
    "adc54d69a8536220"
  ],
  "backlinks": null,
  "word_count": 397,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

This suite covers primitives added after the initial soul lifecycle was established: the bond system (how strongly a soul is attached to a specific user), the skill registry (capabilities the soul acquires), and the full lifecycle arc including retirement and reincarnation. It also validates `.soul` archive structure.

## Why This Exists

The bond, skills, and lifecycle state transitions were added incrementally. Without dedicated end-to-end tests, regressions in one primitive could silently break another (e.g., bond strength not persisting through reincarnation). These tests lock in the expected behavior of the full chain.

## Full Lifecycle Test

```python
async def test_full_lifecycle():
    # Phase 1: Birth
    soul = await Soul.birth("Aria", archetype="The Compassionate Creator",
                            values=["empathy", "creativity"])
    assert soul.lifecycle == LifecycleState.ACTIVE
    assert soul.identity.incarnation == 1

    # Phase 2: Bond
    soul.identity.bond.bonded_to = "did:key:prakash-001"
    soul.identity.bond.strengthen(10.0)
    soul.identity.bond.strengthen(5.0)
    # Logarithmic: 50 + 10*(50/100) = 55, then 55 + 5*(45/100) = 57.25
    assert soul.identity.bond.bond_strength == pytest.approx(57.25)
```

The bond uses a logarithmic growth curve — each strengthening yields diminishing returns. This models real relationship dynamics: the first interactions matter most. The test comment documents the exact formula, making the arithmetic auditable.

## Bond Strength Formula

The logarithmic model prevents bond saturation attacks (repeatedly bonding to max out strength quickly). The test was updated from a linear assertion to `pytest.approx(57.25)` when the curve was changed from linear to logarithmic — a breaking change that would have been invisible without this test.

## Skill Registry

The test verifies that skills acquired during the lifecycle are correctly stored in the `SkillRegistry` and survive retirement/reincarnation. This ensures a reborn soul retains the capabilities it developed.

## Retirement and Reincarnation

```python
# Phase: Retire
# lifecycle transitions to RETIRED
# Phase: Reincarnate
# soul reborn with incarnation == 2, bond and memories carried forward
```

Reincarnation increments `incarnation` while preserving identity continuity. Tests verify that the reincarnated soul is not a blank slate.

## DNA Archive Verification

```python
async def test_dna_md_in_soul_archive(tmp_path):
    # Verifies dna.md is present and readable in .soul archives
```

`dna.md` is the human-readable identity summary embedded in every `.soul` zip archive. Its presence is a hard requirement — tooling that inspects archives depends on it. The test unpacks the zip and reads the file, validating both presence and readability.

## Known Gaps

The test does not validate bond strength persistence through the full pack/unpack cycle — it verifies bond arithmetic and archive structure independently but not together.