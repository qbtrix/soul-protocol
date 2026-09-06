# test_fork.py — Tests for Soul.fork() reproduction with lineage
# Created: 2026-09-07 (terrarium) — Lineage fields, OCEAN drift and clamping,
#   tier inheritance (episodic never), immutable-trait guard, backward compat
#   for pre-lineage souls, and the `soul fork` CLI end to end.

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.runtime.soul import OCEAN_TRAITS, Soul
from soul_protocol.runtime.types import MemoryType, SoulConfig


async def _drifting_parent(name: str = "Root", **kwargs) -> Soul:
    """Birth a parent whose OCEAN is allowed to drift on fork.

    The default ``EvolutionConfig.immutable_traits`` contains ``"personality"``,
    which freezes all five OCEAN traits. Tests that want to observe drift have
    to opt out of that first.
    """
    soul = await Soul.birth(name, **kwargs)
    config = soul.serialize()
    config.evolution.immutable_traits = ["core_values"]
    return Soul(config)


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


async def test_fork_sets_lineage():
    """A child gets a new DID, the parent's DID, and generation + 1."""
    parent = await Soul.birth("Aria", archetype="The Founder")
    child = await parent.fork("Vale")

    assert child.did != parent.did
    assert child.did.startswith("did:soul:vale-")
    assert child.identity.parent_did == parent.did
    assert child.identity.generation == parent.identity.generation + 1
    assert parent.identity.generation == 1


async def test_generation_stacks_across_forks():
    """Each fork advances the generation counter by one."""
    gen1 = await Soul.birth("Aria")
    gen2 = await gen1.fork("Vale")
    gen3 = await gen2.fork("Wren")

    assert [s.identity.generation for s in (gen1, gen2, gen3)] == [1, 2, 3]
    assert gen3.identity.parent_did == gen2.did
    assert gen2.identity.parent_did == gen1.did
    assert gen1.identity.parent_did is None


async def test_fork_is_not_reincarnation():
    """Lineage and rebirth are separate axes and must not bleed into each other."""
    parent = await Soul.birth("Aria")
    child = await parent.fork("Vale")

    assert child.identity.incarnation == 1
    assert child.identity.previous_lives == []

    reborn = await Soul.reincarnate(parent)
    assert reborn.identity.parent_did is None
    assert reborn.identity.generation == 1


async def test_fork_inherits_archetype_and_values():
    parent = await Soul.birth("Aria", archetype="The Founder", values=["water", "truth"])
    child = await parent.fork("Vale")

    assert child.archetype == "The Founder"
    assert child.identity.core_values == ["water", "truth"]
    # A copy, not a shared list.
    child.identity.core_values.append("noise")
    assert parent.identity.core_values == ["water", "truth"]


# ---------------------------------------------------------------------------
# OCEAN drift
# ---------------------------------------------------------------------------


async def test_drift_stays_within_width_and_bounds():
    """Every trait lands within +/- drift of the parent and inside 0..1."""
    parent = await _drifting_parent(
        "Root",
        ocean={
            "openness": 0.99,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.01,
        },
    )
    p = parent.dna.personality
    width = 0.5
    clamped = False

    for _ in range(200):
        child = await parent.fork("Vale", drift=width)
        c = child.dna.personality
        for trait in OCEAN_TRAITS:
            parent_value = getattr(p, trait)
            child_value = getattr(c, trait)
            assert 0.0 <= child_value <= 1.0
            lower = max(0.0, parent_value - width)
            upper = min(1.0, parent_value + width)
            assert lower <= child_value <= upper
            if child_value in (0.0, 1.0):
                clamped = True

    assert clamped, "expected at least one trait to hit a 0.0/1.0 clamp"


async def test_drift_actually_moves_traits():
    """A non-zero drift on a mutable soul does not produce a clone."""
    parent = await _drifting_parent("Root")
    child = await parent.fork("Vale", drift=0.2)

    p, c = parent.dna.personality, child.dna.personality
    assert any(getattr(p, t) != getattr(c, t) for t in OCEAN_TRAITS)


async def test_drift_zero_reproduces_parent_ocean():
    parent = await _drifting_parent("Root", ocean={"openness": 0.73, "neuroticism": 0.21})
    child = await parent.fork("Vale", drift=0)

    p, c = parent.dna.personality, child.dna.personality
    assert all(getattr(p, t) == getattr(c, t) for t in OCEAN_TRAITS)


async def test_drift_defaults_to_mutation_rate():
    """The drift default is the parent's EvolutionConfig.mutation_rate."""
    parent = await _drifting_parent("Root")
    config = parent.serialize()
    config.evolution.mutation_rate = 0.0
    parent = Soul(config)

    child = await parent.fork("Vale")
    p, c = parent.dna.personality, child.dna.personality
    assert all(getattr(p, t) == getattr(c, t) for t in OCEAN_TRAITS)


async def test_immutable_traits_are_never_drifted():
    """The default config freezes 'personality', so OCEAN copies verbatim."""
    parent = await Soul.birth("Root", ocean={"openness": 0.42, "agreeableness": 0.66})
    assert "personality" in parent.serialize().evolution.immutable_traits

    child = await parent.fork("Vale", drift=0.9)
    p, c = parent.dna.personality, child.dna.personality
    assert all(getattr(p, t) == getattr(c, t) for t in OCEAN_TRAITS)


async def test_negative_drift_rejected():
    parent = await Soul.birth("Root")
    with pytest.raises(ValueError, match="drift must be >= 0"):
        await parent.fork("Vale", drift=-0.1)


# ---------------------------------------------------------------------------
# Memory inheritance
# ---------------------------------------------------------------------------


async def test_episodic_never_inherited_even_when_requested():
    """Episodic is dropped from inherit; procedural still passes down."""
    parent = await Soul.birth("Root")
    await parent.remember("dug the well at dawn", type=MemoryType.EPISODIC)
    await parent.remember("to find water, follow the reeds", type=MemoryType.PROCEDURAL)

    child = await parent.fork("Vale", inherit=["core", "procedural", "episodic"])

    assert child.memory.episodic_entries() == []
    procedures = [e.content for e in child.memory.procedural_entries()]
    assert procedures == ["to find water, follow the reeds"]


async def test_semantic_only_when_asked():
    parent = await Soul.birth("Root")
    await parent.remember("the spring runs dry in summer", type=MemoryType.SEMANTIC)

    default_child = await parent.fork("Vale")
    assert default_child.memory.semantic_facts() == []

    asking_child = await parent.fork("Wren", inherit=["core", "procedural", "semantic"])
    assert len(asking_child.memory.semantic_facts()) == 1


async def test_unknown_tier_rejected():
    parent = await Soul.birth("Root")
    with pytest.raises(ValueError, match="Unknown memory tier"):
        await parent.fork("Vale", inherit=["core", "dreams"])


async def test_charter_lands_in_core_memory_attributed_to_parent():
    parent = await Soul.birth("Aria")
    child = await parent.fork("Vale", charter="Keep the well open to everyone.")

    persona = child.get_core_memory().persona
    assert "Keep the well open to everyone." in persona
    assert "Aria" in persona
    assert parent.did in persona
    # The parent's own core memory is untouched.
    assert "Keep the well open" not in parent.get_core_memory().persona


async def test_child_does_not_inherit_the_mutation_log():
    parent = await Soul.birth("Aria")
    await parent.propose_evolution("communication.warmth", "high", "user prefers warmth")
    assert parent.pending_mutations

    child = await parent.fork("Vale")
    assert child.pending_mutations == []
    assert child.evolution_history == []


# ---------------------------------------------------------------------------
# Persistence + backward compatibility
# ---------------------------------------------------------------------------


async def test_child_saves_and_round_trips(tmp_path):
    """A forked child is a fully valid soul; lineage survives save + awaken."""
    parent = await Soul.birth("Aria")
    child = await parent.fork("Vale", charter="Keep the well open.")

    target = tmp_path / "vale"
    await child.save_local(target)
    restored = await Soul.awaken(target)

    assert restored.identity.parent_did == parent.did
    assert restored.identity.generation == 2
    assert "Keep the well open." in restored.get_core_memory().persona


async def test_exported_child_round_trips(tmp_path):
    parent = await Soul.birth("Aria")
    child = await parent.fork("Vale")

    target = tmp_path / "vale.soul"
    await child.export(target, include_keys=True)
    restored = await Soul.awaken(target)

    assert restored.identity.parent_did == parent.did
    assert restored.identity.generation == 2


async def test_pre_lineage_soul_still_loads():
    """A soul serialized before lineage existed loads with defaults."""
    soul = await Soul.birth("Legacy")
    raw = soul.serialize().model_dump(mode="json")
    raw["identity"].pop("parent_did")
    raw["identity"].pop("generation")

    restored = SoulConfig.model_validate(raw)

    assert restored.identity.parent_did is None
    assert restored.identity.generation == 1


async def test_public_profile_carries_lineage():
    parent = await Soul.birth("Aria")
    child = await parent.fork("Vale")

    assert parent.public_profile()["parent_did"] is None
    assert parent.public_profile()["generation"] == 1
    assert child.public_profile()["parent_did"] == parent.did
    assert child.public_profile()["generation"] == 2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_fork_cli_end_to_end(tmp_path):
    runner = CliRunner()
    parent_path = str(tmp_path / "aria.soul")
    child_path = str(tmp_path / "vale.soul")

    assert runner.invoke(cli, ["birth", "Aria", "-o", parent_path]).exit_code == 0

    result = runner.invoke(
        cli,
        [
            "fork",
            parent_path,
            "--child",
            "Vale",
            "--charter",
            "Keep the well open",
            "-o",
            child_path,
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Forked" in result.output
    assert "Vale" in result.output

    inspected = runner.invoke(cli, ["inspect", child_path])
    assert inspected.exit_code == 0
    assert "Generation 2" in inspected.output


def test_fork_cli_json_is_machine_readable(tmp_path):
    runner = CliRunner()
    parent_path = str(tmp_path / "aria.soul")
    child_path = str(tmp_path / "vale.soul")

    runner.invoke(cli, ["birth", "Aria", "-o", parent_path])
    result = runner.invoke(
        cli,
        [
            "fork",
            parent_path,
            "--child",
            "Vale",
            "--drift",
            "0.1",
            "--inherit",
            "core,procedural",
            "-o",
            child_path,
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert payload["child"] == "Vale"
    assert payload["generation"] == 2
    assert payload["parent_did"].startswith("did:soul:aria-")
    assert payload["drift"] == 0.1
    assert payload["inherited"] == ["core", "procedural"]
    # Default config freezes personality, so the CLI must say so.
    assert payload["frozen_traits"] == list(OCEAN_TRAITS)
    assert set(payload["ocean"]) == set(OCEAN_TRAITS)


def test_fork_cli_rejects_unknown_tier(tmp_path):
    runner = CliRunner()
    parent_path = str(tmp_path / "aria.soul")

    runner.invoke(cli, ["birth", "Aria", "-o", parent_path])
    result = runner.invoke(
        cli, ["fork", parent_path, "--child", "Vale", "--inherit", "core,dreams"]
    )

    assert result.exit_code == 1
    assert "Unknown memory tier" in result.output
