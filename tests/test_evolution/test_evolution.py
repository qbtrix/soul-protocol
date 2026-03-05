# test_evolution.py — Tests for the evolution subsystem (EvolutionManager).
# Created: 2026-02-22 — Covers supervised/autonomous/disabled mode proposals,
# approve/reject, apply mutation, and immutable trait blocking.

from __future__ import annotations

import pytest

from soul_protocol.evolution.manager import EvolutionManager
from soul_protocol.types import DNA, EvolutionConfig, EvolutionMode


@pytest.fixture
def dna() -> DNA:
    """Return a default DNA instance for mutation tests."""
    return DNA()


@pytest.fixture
def supervised_config() -> EvolutionConfig:
    """Return an EvolutionConfig in supervised mode."""
    return EvolutionConfig(mode=EvolutionMode.SUPERVISED)


@pytest.fixture
def autonomous_config() -> EvolutionConfig:
    """Return an EvolutionConfig in autonomous mode."""
    return EvolutionConfig(mode=EvolutionMode.AUTONOMOUS)


@pytest.fixture
def disabled_config() -> EvolutionConfig:
    """Return an EvolutionConfig in disabled mode."""
    return EvolutionConfig(mode=EvolutionMode.DISABLED)


async def test_propose_supervised_creates_pending(dna: DNA, supervised_config: EvolutionConfig):
    """In supervised mode, proposals go to pending (approved=None)."""
    mgr = EvolutionManager(supervised_config)

    mutation = await mgr.propose(
        dna=dna,
        trait="communication.warmth",
        new_value="high",
        reason="User prefers warm interactions",
    )

    assert mutation.id
    assert mutation.trait == "communication.warmth"
    assert mutation.new_value == "high"
    assert mutation.approved is None
    assert len(mgr.pending) == 1


async def test_propose_autonomous_auto_approves(dna: DNA, autonomous_config: EvolutionConfig):
    """In autonomous mode, proposals are auto-approved immediately."""
    mgr = EvolutionManager(autonomous_config)

    mutation = await mgr.propose(
        dna=dna,
        trait="communication.warmth",
        new_value="high",
        reason="Autonomous evolution",
    )

    assert mutation.approved is True
    assert mutation.approved_at is not None
    assert len(mgr.pending) == 0
    assert len(mgr.history) == 1


async def test_propose_disabled_raises(dna: DNA, disabled_config: EvolutionConfig):
    """In disabled mode, proposals raise ValueError."""
    mgr = EvolutionManager(disabled_config)

    with pytest.raises(ValueError, match="disabled"):
        await mgr.propose(
            dna=dna,
            trait="communication.warmth",
            new_value="high",
            reason="Should fail",
        )


async def test_approve_mutation(dna: DNA, supervised_config: EvolutionConfig):
    """approve() marks a pending mutation as approved."""
    mgr = EvolutionManager(supervised_config)

    mutation = await mgr.propose(
        dna=dna,
        trait="communication.warmth",
        new_value="high",
        reason="User feedback",
    )

    result = await mgr.approve(mutation.id)
    assert result is True
    assert len(mgr.pending) == 0
    assert len(mgr.history) == 1
    assert mgr.history[0].approved is True


async def test_reject_mutation(dna: DNA, supervised_config: EvolutionConfig):
    """reject() marks a pending mutation as rejected."""
    mgr = EvolutionManager(supervised_config)

    mutation = await mgr.propose(
        dna=dna,
        trait="communication.warmth",
        new_value="high",
        reason="Testing rejection",
    )

    result = await mgr.reject(mutation.id)
    assert result is True
    assert len(mgr.pending) == 0
    assert len(mgr.history) == 1
    assert mgr.history[0].approved is False


async def test_apply_mutation_changes_dna(dna: DNA, supervised_config: EvolutionConfig):
    """apply() modifies DNA with the mutation's new value."""
    mgr = EvolutionManager(supervised_config)

    mutation = await mgr.propose(
        dna=dna,
        trait="communication.warmth",
        new_value="high",
        reason="Apply test",
    )
    await mgr.approve(mutation.id)

    new_dna = mgr.apply(dna, mutation.id)
    assert new_dna.communication.warmth == "high"

    # Original DNA should be unchanged (deep copy)
    assert dna.communication.warmth == "moderate"


async def test_immutable_trait_blocked(dna: DNA, supervised_config: EvolutionConfig):
    """Proposing a mutation on an immutable trait raises ValueError."""
    mgr = EvolutionManager(supervised_config)

    # 'personality' is in immutable_traits by default
    with pytest.raises(ValueError, match="immutable"):
        await mgr.propose(
            dna=dna,
            trait="personality.openness",
            new_value="0.9",
            reason="Should be blocked",
        )
