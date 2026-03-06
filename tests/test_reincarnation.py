# test_reincarnation.py — Tests for Soul.reincarnate() lifecycle
# Created: 2026-03-06 — Reincarnation, memory preservation, incarnation counter

from __future__ import annotations

import pytest

from soul_protocol.soul import Soul
from soul_protocol.types import LifecycleState, MemoryType


async def test_basic_reincarnation():
    """Reincarnate creates a new soul with a new DID."""
    original = await Soul.birth("Aria", archetype="The Creator")
    reborn = await Soul.reincarnate(original)

    assert reborn.name == "Aria"
    assert reborn.did != original.did
    assert reborn.did.startswith("did:soul:aria-")
    assert reborn.lifecycle == LifecycleState.ACTIVE


async def test_reincarnation_with_new_name():
    """Reincarnate with a new name changes the soul's name."""
    original = await Soul.birth("Aria", archetype="The Creator")
    reborn = await Soul.reincarnate(original, name="Nova")

    assert reborn.name == "Nova"
    assert reborn.did.startswith("did:soul:nova-")


async def test_incarnation_counter():
    """Each reincarnation increments the incarnation counter."""
    soul = await Soul.birth("Aria")
    assert soul.identity.incarnation == 1

    soul2 = await Soul.reincarnate(soul)
    assert soul2.identity.incarnation == 2

    soul3 = await Soul.reincarnate(soul2)
    assert soul3.identity.incarnation == 3


async def test_previous_lives_tracking():
    """Previous lives list tracks old DIDs."""
    soul = await Soul.birth("Aria")
    original_did = soul.did

    soul2 = await Soul.reincarnate(soul)
    assert original_did in soul2.identity.previous_lives
    assert len(soul2.identity.previous_lives) == 1

    soul3 = await Soul.reincarnate(soul2)
    assert original_did in soul3.identity.previous_lives
    assert soul2.did in soul3.identity.previous_lives
    assert len(soul3.identity.previous_lives) == 2


async def test_personality_preserved():
    """DNA personality traits carry over through reincarnation."""
    original = await Soul.birth("Aria", archetype="The Creator")
    # Modify DNA to verify it carries
    original._dna.personality.openness = 0.9
    original._dna.personality.neuroticism = 0.1

    reborn = await Soul.reincarnate(original)

    assert reborn.dna.personality.openness == pytest.approx(0.9)
    assert reborn.dna.personality.neuroticism == pytest.approx(0.1)


async def test_core_values_preserved():
    """Core values carry over through reincarnation."""
    original = await Soul.birth(
        "Aria",
        values=["empathy", "creativity", "honesty"],
    )
    reborn = await Soul.reincarnate(original)

    assert reborn.identity.core_values == ["empathy", "creativity", "honesty"]


async def test_memories_preserved():
    """Memories carry over through reincarnation."""
    original = await Soul.birth("Aria")
    await original.remember(
        "User loves Python programming",
        type=MemoryType.SEMANTIC,
        importance=8,
    )

    reborn = await Soul.reincarnate(original)
    results = await reborn.recall("Python programming")
    assert any("Python" in r.content for r in results)


async def test_archetype_preserved():
    """Archetype carries over through reincarnation."""
    original = await Soul.birth("Aria", archetype="The Compassionate Creator")
    reborn = await Soul.reincarnate(original)
    assert reborn.archetype == "The Compassionate Creator"


async def test_bond_preserved():
    """Bond state carries over through reincarnation."""
    original = await Soul.birth("Aria")
    original.identity.bond.bonded_to = "did:key:user-123"
    original.identity.bond.strengthen(20.0)

    reborn = await Soul.reincarnate(original)
    assert reborn.identity.bond.bonded_to == "did:key:user-123"
    assert reborn.identity.bond.bond_strength == 70.0
