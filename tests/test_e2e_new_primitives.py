# test_e2e_new_primitives.py — End-to-end lifecycle test for new soul primitives
# Updated: phase1-ablation-fixes — Updated bond assertions for logarithmic growth curve.
# Created: 2026-03-06 — Full lifecycle: birth, bond, skills, retire, reincarnate

from __future__ import annotations

import io
import zipfile

import pytest

from soul_protocol.runtime.export.pack import pack_soul
from soul_protocol.runtime.export.unpack import unpack_soul
from soul_protocol.runtime.skills import Skill, SkillRegistry
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import (
    Interaction,
    LifecycleState,
    MemoryType,
)


async def test_full_lifecycle():
    """Birth -> interact -> bond -> skills -> retire -> reincarnate -> verify."""

    # === Phase 1: Birth ===
    soul = await Soul.birth(
        "Aria",
        archetype="The Compassionate Creator",
        values=["empathy", "creativity"],
    )
    assert soul.lifecycle == LifecycleState.ACTIVE
    assert soul.identity.incarnation == 1

    # === Phase 2: Bond ===
    soul.identity.bond.bonded_to = "did:key:prakash-001"
    soul.identity.bond.strengthen(10.0)
    soul.identity.bond.strengthen(5.0)
    # Logarithmic: 50 + 10*(50/100) = 55, then 55 + 5*(45/100) = 57.25
    assert soul.identity.bond.bond_strength == pytest.approx(57.25)
    assert soul.identity.bond.interaction_count == 2

    # === Phase 3: Interact and remember ===
    await soul.remember(
        "User loves building AI companions",
        type=MemoryType.SEMANTIC,
        importance=9,
    )

    interaction = Interaction(
        user_input="I've been working on soul-protocol all day",
        agent_output="That sounds like meaningful work!",
        channel="test",
    )
    await soul.observe(interaction)

    # Verify memory is there
    results = await soul.recall("AI companions")
    assert any("AI companions" in r.content for r in results)

    # === Phase 4: Skills ===
    registry = SkillRegistry()
    registry.add(Skill(id="empathy", name="Empathy"))
    registry.add(Skill(id="coding", name="Coding"))

    # Grant XP to empathy
    registry.grant_xp("empathy", 50)
    registry.grant_xp("coding", 100)  # Should level up

    assert registry.get("empathy").xp == 50
    assert registry.get("empathy").level == 1
    assert registry.get("coding").level == 2

    # === Phase 5: Export and verify dna.md ===
    config = soul.serialize()
    memory_data = soul._memory.to_dict()
    packed = await pack_soul(config, memory_data=memory_data)

    buf = io.BytesIO(packed)
    with zipfile.ZipFile(buf, "r") as zf:
        assert "dna.md" in zf.namelist()
        dna_content = zf.read("dna.md").decode("utf-8")
        assert "Aria" in dna_content
        assert "Personality (OCEAN)" in dna_content

    # Verify unpack reads dna.md
    restored_config, restored_memory = await unpack_soul(packed)
    assert "dna_md" in restored_memory
    assert "Aria" in restored_memory["dna_md"]

    # === Phase 6: Save original DID, then reincarnate ===
    original_did = soul.did
    original_bond_strength = soul.identity.bond.bond_strength

    reborn = await Soul.reincarnate(soul, name="Aria Nova")

    # === Phase 7: Verify reincarnation ===
    assert reborn.name == "Aria Nova"
    assert reborn.did != original_did
    assert reborn.identity.incarnation == 2
    assert original_did in reborn.identity.previous_lives
    assert reborn.lifecycle == LifecycleState.ACTIVE

    # Personality preserved
    assert reborn.dna.personality.openness == soul.dna.personality.openness

    # Core values preserved
    assert reborn.identity.core_values == ["empathy", "creativity"]

    # Bond preserved
    assert reborn.identity.bond.bond_strength == original_bond_strength
    assert reborn.identity.bond.bonded_to == "did:key:prakash-001"

    # Memories preserved
    results = await reborn.recall("AI companions")
    assert any("AI companions" in r.content for r in results)


async def test_dna_md_in_soul_archive(tmp_path):
    """Verify dna.md is present and readable in .soul archives."""
    soul = await Soul.birth(
        "Mira",
        archetype="The Seeker",
        personality="Curious and methodical",
    )

    soul_path = tmp_path / "mira.soul"
    await soul.export(str(soul_path))

    # Read the archive
    with zipfile.ZipFile(str(soul_path), "r") as zf:
        assert "dna.md" in zf.namelist()
        content = zf.read("dna.md").decode("utf-8")
        assert "Mira" in content
        assert "Personality (OCEAN)" in content

    # Round-trip via unpack
    packed_bytes = soul_path.read_bytes()
    _, memory_data = await unpack_soul(packed_bytes)
    assert "dna_md" in memory_data
    assert "Mira" in memory_data["dna_md"]
