# test_evolution.py — Tests for the evolution subsystem (EvolutionManager).
# Created: 2026-02-22 — Covers supervised/autonomous/disabled mode proposals,
# approve/reject, apply mutation, and immutable trait blocking.

from __future__ import annotations

import pytest

from soul_protocol.runtime.evolution.manager import EvolutionManager
from soul_protocol.runtime.types import DNA, Biorhythms, EvolutionConfig, EvolutionMode, Mutation


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


async def test_apply_pending_mutation_raises(dna: DNA, supervised_config: EvolutionConfig):
    """apply() must not accept a mutation that is still awaiting approval."""
    mgr = EvolutionManager(supervised_config)

    mutation = await mgr.propose(
        dna=dna,
        trait="communication.warmth",
        new_value="high",
        reason="Pending mutation",
    )

    with pytest.raises(ValueError, match="No approved mutation"):
        mgr.apply(dna, mutation.id)
    assert dna.communication.warmth == "moderate"


async def test_apply_rejected_mutation_raises(dna: DNA, supervised_config: EvolutionConfig):
    """apply() must not accept a rejected mutation."""
    mgr = EvolutionManager(supervised_config)

    mutation = await mgr.propose(
        dna=dna,
        trait="communication.warmth",
        new_value="high",
        reason="Rejected mutation",
    )
    await mgr.reject(mutation.id)

    with pytest.raises(ValueError, match="No approved mutation"):
        mgr.apply(dna, mutation.id)
    assert dna.communication.warmth == "moderate"


async def test_apply_nonexistent_mutation_raises(dna: DNA, supervised_config: EvolutionConfig):
    """apply() must fail clearly when the mutation id does not exist."""
    mgr = EvolutionManager(supervised_config)

    with pytest.raises(ValueError, match="No approved mutation"):
        mgr.apply(dna, "missing-mutation")
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


async def test_propose_invalid_trait_path_raises(dna: DNA, supervised_config: EvolutionConfig):
    """Invalid trait paths should be rejected before entering pending."""
    mgr = EvolutionManager(supervised_config)

    with pytest.raises(ValueError, match="Invalid trait path"):
        await mgr.propose(
            dna=dna,
            trait="communication.no_such_field",
            new_value="high",
            reason="Typoed trait",
        )
    assert mgr.pending == []
    assert mgr.history == []


async def test_propose_rejects_uncoercible_trait_value(
    dna: DNA, supervised_config: EvolutionConfig
):
    """Bad typed values should not become approved/pending mutations."""
    mgr = EvolutionManager(supervised_config)

    with pytest.raises(ValueError, match="cannot coerce"):
        await mgr.propose(
            dna=dna,
            trait="biorhythms.energy_regen_rate",
            new_value="not-a-float",
            reason="Bad typed value",
        )
    assert mgr.pending == []
    assert mgr.history == []


def test_apply_uncoercible_history_mutation_leaves_original_dna_unchanged(
    dna: DNA, supervised_config: EvolutionConfig
):
    """Even corrupted approved history must not partially mutate the input DNA."""
    mgr = EvolutionManager(supervised_config)
    supervised_config.history.append(
        Mutation(
            id="bad-value",
            trait="biorhythms.energy_regen_rate",
            old_value=str(dna.biorhythms.energy_regen_rate),
            new_value="not-a-float",
            reason="Corrupted history",
            approved=True,
        )
    )

    with pytest.raises(ValueError, match="cannot coerce"):
        mgr.apply(dna, "bad-value")
    assert dna.biorhythms.energy_regen_rate == Biorhythms().energy_regen_rate
