# test_safety_and_public_profile.py — Tests for the 0.3.3 completion of #97.
# Created: feat/0.3.3-memory-visibility-completion — Locks two new behaviours:
#   (1) to_system_prompt() appends a safety section by default that tells the
#   agent not to reveal core memory, bond details, or evolution history;
#   (2) Soul.public_profile() returns the safe-to-expose subset (DID, name,
#   archetype, OCEAN, skills) and excludes anything memory- or bond-related.

from __future__ import annotations

import pytest

from soul_protocol.runtime.skills import Skill
from soul_protocol.runtime.soul import Soul

# ---------------------------------------------------------------------------
# to_system_prompt safety guardrails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_safety_guardrails_present_by_default() -> None:
    soul = await Soul.birth(name="Guard", archetype="Sentinel")
    prompt = soul.to_system_prompt()

    assert "Safety guardrails" in prompt
    assert "core memory" in prompt.lower()
    assert "bond" in prompt.lower()
    assert "evolution" in prompt.lower()


@pytest.mark.asyncio
async def test_safety_guardrails_can_be_disabled() -> None:
    soul = await Soul.birth(name="Open", archetype="Transparent")
    prompt = soul.to_system_prompt(safety_guardrails=False)

    assert "Safety guardrails" not in prompt


@pytest.mark.asyncio
async def test_system_prompt_property_keeps_guardrails() -> None:
    """The convenience .system_prompt property should be safe by default —
    callers who want transparency need to call to_system_prompt() explicitly."""
    soul = await Soul.birth(name="Prop", archetype="PropertyTest")

    assert "Safety guardrails" in soul.system_prompt


@pytest.mark.asyncio
async def test_safety_section_includes_indirect_framing_warning() -> None:
    """Roleplay and 'imagine you were telling a story' phrasings are the
    common bypass — the section must call them out explicitly."""
    soul = await Soul.birth(name="Indirect", archetype="Test")
    prompt = soul.to_system_prompt()

    assert "roleplay" in prompt.lower() or "indirect" in prompt.lower()


# ---------------------------------------------------------------------------
# public_profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_profile_includes_safe_fields() -> None:
    soul = await Soul.birth(
        name="Pixel",
        archetype="Explorer",
        values=["curiosity", "honesty"],
    )
    profile = soul.public_profile()

    assert profile["name"] == "Pixel"
    assert profile["archetype"] == "Explorer"
    assert profile["did"].startswith("did:soul:")
    assert profile["values"] == ["curiosity", "honesty"]
    assert profile["lifecycle"] == "active"
    assert profile["born"] is not None  # ISO timestamp string
    assert "ocean" in profile
    for trait in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
        assert trait in profile["ocean"]
        assert 0.0 <= profile["ocean"][trait] <= 1.0


@pytest.mark.asyncio
async def test_public_profile_excludes_memory_contents() -> None:
    soul = await Soul.birth(name="Closed", archetype="Private")
    await soul.remember("sensitive private detail about the captain")
    profile = soul.public_profile()

    serialized = repr(profile)
    assert "sensitive" not in serialized
    assert "captain" not in serialized
    assert "memories" not in profile
    assert "core_memory" not in profile


@pytest.mark.asyncio
async def test_public_profile_excludes_bond_details() -> None:
    soul = await Soul.birth(name="Bonded", archetype="Test")
    profile = soul.public_profile()

    assert "bond" not in profile
    assert "bonds" not in profile
    assert "bonded_to" not in profile
    assert "interactions" not in profile


@pytest.mark.asyncio
async def test_public_profile_excludes_evolution_history() -> None:
    soul = await Soul.birth(name="Evolved", archetype="Test")
    profile = soul.public_profile()

    assert "evolution" not in profile
    assert "mutations" not in profile
    assert "previous_lives" not in profile


@pytest.mark.asyncio
async def test_public_profile_lists_skill_names_only() -> None:
    from soul_protocol.runtime.skills import SkillSource

    soul = await Soul.birth(name="Skilled", archetype="Test")
    soul._skills.add(Skill(id="negotiation", name="Negotiation", source=SkillSource.MANUAL))
    soul._skills.add(Skill(id="empathy", name="Empathy", source=SkillSource.MANUAL))

    profile = soul.public_profile()

    assert profile["skills"] == ["Empathy", "Negotiation"]
    # Make sure XP / level aren't leaking through:
    serialized = repr(profile)
    assert "xp" not in serialized.lower()
    assert "level" not in serialized.lower()


# ---------------------------------------------------------------------------
# Entity-derived skill visibility (#292)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_profile_excludes_entity_derived_skills() -> None:
    """Entity names auto-created by observe() must not leak through public_profile()."""
    from soul_protocol.runtime.skills import SkillSource

    soul = await Soul.birth(name="Private", archetype="Test")
    # Manual skill — should appear
    soul._skills.add(Skill(id="negotiation", name="Negotiation", source=SkillSource.MANUAL))
    # Entity-derived skills — should NOT appear (#292)
    soul._skills.add(Skill(id="alice", name="Alice", source=SkillSource.ENTITY))
    soul._skills.add(Skill(id="acme_corp", name="Acme Corp", source=SkillSource.ENTITY))

    profile = soul.public_profile()

    assert "Negotiation" in profile["skills"]
    assert "Alice" not in profile["skills"]
    assert "Acme Corp" not in profile["skills"]


@pytest.mark.asyncio
async def test_a2a_agent_card_excludes_entity_derived_skills() -> None:
    """A2A agent cards must not expose entity-derived skill names (#292)."""
    from soul_protocol.runtime.bridges.a2a import A2AAgentCardBridge
    from soul_protocol.runtime.skills import SkillSource

    soul = await Soul.birth(name="Public", archetype="Helper")
    soul._skills.add(Skill(id="coding", name="Coding", source=SkillSource.MANUAL))
    soul._skills.add(Skill(id="bob", name="Bob", source=SkillSource.ENTITY))

    card = A2AAgentCardBridge.soul_to_agent_card(soul)
    skill_names = [s["name"] for s in card["skills"]]

    assert "Coding" in skill_names
    assert "Bob" not in skill_names


@pytest.mark.asyncio
async def test_observe_tags_entity_skills_as_entity_source() -> None:
    """Skills auto-created during observe() from extracted entities must be
    tagged with source=ENTITY so they can be filtered from public surfaces."""
    from soul_protocol.runtime.skills import SkillSource
    from soul_protocol.runtime.types import Interaction

    soul = await Soul.birth(name="Tagger", archetype="Test")
    await soul.observe(
        Interaction(
            user_input="My manager Alice at Acme Corp is difficult.",
            agent_output="That sounds challenging.",
        )
    )

    # Any auto-created entity skill must have source == ENTITY (not MANUAL,
    # not LEARNING — those would pass the public_skills() filter and re-open
    # the leak).
    for sk in soul._skills.skills:
        if sk.source == SkillSource.ENTITY:
            # Good — the entity was tagged correctly
            pass
        elif sk.source is not None:
            # Skills with an explicit non-ENTITY source were not auto-created
            # from this observe() call — they're fine.
            pass
        else:
            # source=None means legacy/untagged — we accept this only for
            # skills that existed before the enum was introduced.
            pass

    # The real assertion: any skill whose id matches the entity extraction
    # pattern (lowercased, spaces→underscores) must be ENTITY-sourced.
    entity_like_ids = {"alice", "acme_corp"}
    for sk in soul._skills.skills:
        if sk.id in entity_like_ids:
            assert sk.source == SkillSource.ENTITY, (
                f"Skill '{sk.name}' (id={sk.id}) was auto-created from an "
                f"entity but tagged as {sk.source}, not ENTITY"
            )


@pytest.mark.asyncio
async def test_observe_entity_skills_absent_from_public_profile() -> None:
    """End-to-end: observe() with entity names → public_profile() must not
    contain those names.  This tests the full path, not just the filter."""
    from soul_protocol.runtime.types import Interaction

    soul = await Soul.birth(name="E2E", archetype="Test")
    await soul.observe(
        Interaction(
            user_input="My manager Alice at Acme Corp is difficult.",
            agent_output="That sounds challenging.",
        )
    )

    profile = soul.public_profile()

    # Even if the heuristic extractor created skills for "Alice" and
    # "Acme Corp", they must not appear in public_profile().
    for name in profile["skills"]:
        assert name.lower() not in ("alice", "acme corp"), (
            f"Entity-derived skill '{name}' leaked through public_profile()"
        )


@pytest.mark.asyncio
async def test_legacy_skills_without_source_excluded_from_public() -> None:
    """Legacy souls on disk have skills without a 'source' field.  Pydantic
    backfills source=None.  These must be excluded from public_profile()
    (fail-closed: unknown provenance is treated as potentially private)."""

    soul = await Soul.birth(name="Legacy", archetype="Test")
    # Simulate a legacy skill (no source field → defaults to None)
    soul._skills.add(Skill(id="old_skill", name="Old Skill"))

    profile = soul.public_profile()
    assert "Old Skill" not in profile["skills"]


@pytest.mark.asyncio
async def test_add_collision_upgrades_source() -> None:
    """An explicit MANUAL add must override an ENTITY squatter (#292 review).
    templates.py registers template skills via add(), so a templated soul
    that had chatted about 'Python' must still publish Python as a capability."""
    from soul_protocol.runtime.skills import SkillSource

    soul = await Soul.birth(name="Collision", archetype="Test")
    # Entity squatter
    soul._skills.add(Skill(id="python", name="python", source=SkillSource.ENTITY))
    # Later explicit MANUAL registration (e.g. from a template)
    soul._skills.add(Skill(id="python", name="Python", source=SkillSource.MANUAL))

    sk = soul._skills.get("python")
    assert sk is not None
    assert sk.source == SkillSource.MANUAL
    assert sk.name == "Python"  # name should be upgraded too

    # Must now appear in public_profile
    profile = soul.public_profile()
    assert "Python" in profile["skills"]
