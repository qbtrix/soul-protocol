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
    soul = await Soul.birth(name="Skilled", archetype="Test")
    soul._skills.add(Skill(id="negotiation", name="Negotiation"))
    soul._skills.add(Skill(id="empathy", name="Empathy"))

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
    soul._skills.add(Skill(id="negotiation", name="Negotiation"))
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
    soul._skills.add(Skill(id="coding", name="Coding"))
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

    # Find any entity-derived skills that were created.
    # Even if the heuristic extractor didn't fire for this input, any
    # auto-created skill must NOT be tagged MANUAL.
    # Any auto-created skill must NOT be MANUAL
    for sk in soul._skills.skills:
        if sk.id not in ("negotiation", "empathy"):  # not pre-registered
            assert sk.source != SkillSource.MANUAL or sk.id in (
                "negotiation",
                "empathy",
            ), f"Skill '{sk.name}' was auto-created but tagged as MANUAL"

