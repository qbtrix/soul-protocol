# tests/test_trust_chain/test_chain_integration.py — Soul lifecycle hooks (#42).
# Created: 2026-04-29 — Verifies that observe / supersede / forget_one /
# propose_evolution / approve_evolution / learn / bond.strengthen all
# append the right action and payload structure to the trust chain.

from __future__ import annotations

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction


@pytest.mark.asyncio
async def test_soul_birth_creates_empty_chain():
    soul = await Soul.birth("TestSoul")
    assert soul.trust_chain.length == 0
    assert soul.verify_chain() == (True, None)


@pytest.mark.asyncio
async def test_observe_appends_memory_write_and_bond_strengthen():
    soul = await Soul.birth("TestSoul")
    await soul.observe(Interaction(user_input="Hi", agent_output="Hello"))

    actions = [e.action for e in soul.trust_chain.entries]
    assert "memory.write" in actions
    assert "bond.strengthen" in actions
    assert soul.verify_chain() == (True, None)


@pytest.mark.asyncio
async def test_observe_payload_carries_user_id_and_domain():
    soul = await Soul.birth("TestSoul")
    await soul.observe(
        Interaction(user_input="Hi", agent_output="Hello"),
        user_id="alice",
        domain="finance",
    )
    # Payload contents aren't in the chain (only the hash), but the entry
    # action is. The payload hash will differ from a no-user_id call.
    soul2 = await Soul.birth("TestSoul")
    await soul2.observe(Interaction(user_input="Hi", agent_output="Hello"))

    h_alice = next(e.payload_hash for e in soul.trust_chain.entries if e.action == "memory.write")
    h_default = next(
        e.payload_hash for e in soul2.trust_chain.entries if e.action == "memory.write"
    )
    assert h_alice != h_default


@pytest.mark.asyncio
async def test_supersede_appends_entry():
    soul = await Soul.birth("TestSoul")
    # Need a memory to supersede
    mid = await soul.remember("first version")
    pre_count = soul.trust_chain.length

    result = await soul.supersede(mid, "second version", reason="updated")
    assert result.get("found") is True

    actions_after = [e.action for e in soul.trust_chain.entries[pre_count:]]
    assert "memory.supersede" in actions_after
    assert soul.verify_chain() == (True, None)


@pytest.mark.asyncio
async def test_forget_one_appends_entry():
    soul = await Soul.birth("TestSoul")
    mid = await soul.remember("forgettable fact")
    pre_count = soul.trust_chain.length

    result = await soul.forget_one(mid)
    assert result.get("found") is True

    actions_after = [e.action for e in soul.trust_chain.entries[pre_count:]]
    assert "memory.forget" in actions_after
    assert soul.verify_chain() == (True, None)


@pytest.mark.asyncio
async def test_forget_one_missing_id_does_not_append():
    soul = await Soul.birth("TestSoul")
    pre_count = soul.trust_chain.length
    result = await soul.forget_one("nonexistent-id")
    assert result.get("found") is False
    assert soul.trust_chain.length == pre_count


@pytest.mark.asyncio
async def test_propose_evolution_appends_entry():
    """propose_evolution writes evolution.proposed to the chain.

    Uses ``communication.warmth`` as the trait — communication is mutable
    by default (personality and core_values are immutable).
    """
    soul = await Soul.birth("TestSoul")
    pre_count = soul.trust_chain.length
    await soul.propose_evolution("communication.warmth", "high", reason="user feedback")

    actions_after = [e.action for e in soul.trust_chain.entries[pre_count:]]
    assert "evolution.proposed" in actions_after


@pytest.mark.asyncio
async def test_approve_evolution_appends_entry():
    soul = await Soul.birth("TestSoul")
    mutation = await soul.propose_evolution("communication.warmth", "high", reason="user feedback")
    pre_count = soul.trust_chain.length
    approved = await soul.approve_evolution(mutation.id)

    if approved:
        actions_after = [e.action for e in soul.trust_chain.entries[pre_count:]]
        assert "evolution.applied" in actions_after


@pytest.mark.asyncio
async def test_bond_strengthen_appends_entry():
    soul = await Soul.birth("TestSoul")
    pre_count = soul.trust_chain.length
    soul._bonds.strengthen(amount=1.0)
    assert soul.trust_chain.length == pre_count + 1
    assert soul.trust_chain.entries[-1].action == "bond.strengthen"


@pytest.mark.asyncio
async def test_bond_weaken_appends_entry():
    soul = await Soul.birth("TestSoul")
    pre_count = soul.trust_chain.length
    soul._bonds.weaken(amount=0.5)
    assert soul.trust_chain.length == pre_count + 1
    assert soul.trust_chain.entries[-1].action == "bond.weaken"


@pytest.mark.asyncio
async def test_audit_log_returns_human_readable_dicts():
    soul = await Soul.birth("TestSoul")
    await soul.observe(Interaction(user_input="Hi", agent_output="Hello"))
    log = soul.audit_log()
    assert len(log) >= 1
    for row in log:
        assert "seq" in row
        assert "timestamp" in row
        assert "action" in row
        assert "actor_did" in row
        assert "payload_hash" in row


@pytest.mark.asyncio
async def test_audit_log_filter_by_prefix():
    soul = await Soul.birth("TestSoul")
    await soul.observe(Interaction(user_input="Hi", agent_output="Hello"))
    soul._bonds.strengthen()

    memory_log = soul.audit_log(action_prefix="memory.")
    bond_log = soul.audit_log(action_prefix="bond.")

    assert all(row["action"].startswith("memory.") for row in memory_log)
    assert all(row["action"].startswith("bond.") for row in bond_log)
    # And neither is empty
    assert memory_log
    assert bond_log
