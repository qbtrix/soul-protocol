# tests/test_multi_user/test_observe_recall.py — Tests for multi-user soul (#46)
# Created: 2026-04-29 (#46) — Covers user_id memory attribution + filtering,
#   per-user bond strength, export/awaken round-trip with user_ids preserved,
#   and the legacy soul auto-migration path.

from __future__ import annotations

from pathlib import Path

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import (
    Identity,
    Interaction,
    LifecycleState,
    MemoryEntry,
    MemoryType,
    SoulConfig,
)

# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def soul():
    """A bare soul with no engine — heuristic pipeline only."""
    return await Soul.birth(name="Aria", archetype="multi-user companion")


# ---------------------------------------------------------------------------
# Memory attribution + filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_id_filter_isolates_memories(soul):
    """3 alice memories + 2 bob memories — recall by user filters cleanly."""
    # Write 3 alice memories
    for content in ["alice loves apples", "alice has a dog", "alice plays piano"]:
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content=content,
            importance=8,
            user_id="alice",
        )
        await soul._memory.add(entry)

    # Write 2 bob memories
    for content in ["bob likes basketball", "bob lives in berlin"]:
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content=content,
            importance=8,
            user_id="bob",
        )
        await soul._memory.add(entry)

    # Recall scoped to alice — should never surface bob entries
    alice_results = await soul.recall(
        "alice OR bob OR loves OR likes",
        user_id="alice",
        limit=20,
    )
    alice_user_ids = {r.user_id for r in alice_results}
    assert "alice" in alice_user_ids
    assert "bob" not in alice_user_ids

    # Recall scoped to bob — should never surface alice entries
    bob_results = await soul.recall(
        "alice OR bob OR loves OR likes",
        user_id="bob",
        limit=20,
    )
    bob_user_ids = {r.user_id for r in bob_results}
    assert "bob" in bob_user_ids
    assert "alice" not in bob_user_ids


@pytest.mark.asyncio
async def test_user_id_none_returns_all(soul):
    """Recall without user_id returns the union — back-compat behaviour."""
    for uid, content in [
        ("alice", "alice loves apples"),
        ("alice", "alice has a dog"),
        ("bob", "bob likes basketball"),
        ("bob", "bob lives in berlin"),
    ]:
        await soul._memory.add(
            MemoryEntry(
                type=MemoryType.SEMANTIC,
                content=content,
                importance=8,
                user_id=uid,
            )
        )

    all_results = await soul.recall("alice OR bob", limit=20)
    user_ids_seen = {r.user_id for r in all_results}
    assert "alice" in user_ids_seen
    assert "bob" in user_ids_seen


@pytest.mark.asyncio
async def test_user_id_legacy_entries_visible_to_all(soul):
    """Entries with user_id=None (legacy/orphan) come back for any user_id query."""
    # One legacy orphan + one alice + one bob
    await soul._memory.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="the soul prefers tea over coffee",
            importance=8,
            user_id=None,
        )
    )
    await soul._memory.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="alice owns a dog named Rex",
            importance=8,
            user_id="alice",
        )
    )
    await soul._memory.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="bob owns a cat named Whiskers",
            importance=8,
            user_id="bob",
        )
    )

    alice_results = await soul.recall("tea OR Rex OR Whiskers", user_id="alice", limit=20)
    contents = [r.content for r in alice_results]
    # Legacy entry must appear
    assert any("tea over coffee" in c for c in contents)
    # Alice's own entry must appear
    assert any("Rex" in c for c in contents)
    # Bob's must not
    assert not any("Whiskers" in c for c in contents)

    bob_results = await soul.recall("tea OR Rex OR Whiskers", user_id="bob", limit=20)
    contents = [r.content for r in bob_results]
    assert any("tea over coffee" in c for c in contents)
    assert any("Whiskers" in c for c in contents)
    assert not any("Rex" in c for c in contents)


# ---------------------------------------------------------------------------
# Observe stamping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_observe_stamps_user_id(soul):
    """observe(... user_id=x) writes memories that come back with user_id=x."""
    interaction = Interaction(
        user_input="my name is Alice and I love python",
        agent_output="Nice to meet you Alice! Python is great.",
    )
    await soul.observe(interaction, user_id="alice")

    # Pull every stored entry — observe should have written at least one
    # semantic fact attributed to alice.
    alice_entries = [
        e
        for e in (
            list(soul._memory._episodic._memories.values())
            + list(soul._memory._semantic._facts.values())
            + list(soul._memory._procedural._procedures.values())
        )
        if e.user_id == "alice"
    ]
    assert alice_entries, (
        "observe(user_id='alice') should write at least one alice-attributed memory"
    )

    # And nothing should be attributed to a different user
    bob_entries = [
        e
        for e in (
            list(soul._memory._episodic._memories.values())
            + list(soul._memory._semantic._facts.values())
            + list(soul._memory._procedural._procedures.values())
        )
        if e.user_id == "bob"
    ]
    assert not bob_entries


# ---------------------------------------------------------------------------
# Per-user bond strength
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_user_bond_strength(soul):
    """strengthen(amount, user_id='alice') only bumps alice, never bob."""
    soul.bond.strengthen(10.0, user_id="alice")
    alice_strength = soul.bond_for("alice").bond_strength
    bob_strength = soul.bond_for("bob").bond_strength
    default_strength = soul.bond.default.bond_strength

    # Alice bumped from 50 → 50 + 10*(50/100) = 55.0
    assert alice_strength == pytest.approx(55.0)
    # Bob is fresh — still 50.0
    assert bob_strength == pytest.approx(50.0)
    # Default bond unchanged — only the per-user bond moved
    assert default_strength == pytest.approx(50.0)

    # Strengthen default (no user_id) — should not touch alice/bob
    soul.bond.strengthen(10.0)
    assert soul.bond.default.bond_strength == pytest.approx(55.0)
    # Alice still where we left it
    assert soul.bond_for("alice").bond_strength == pytest.approx(55.0)


@pytest.mark.asyncio
async def test_observe_strengthens_per_user_bond_when_user_id_given(soul):
    """observe(... user_id='alice') should bump alice's bond, not the default."""
    starting_default = soul.bond.default.bond_strength

    interaction = Interaction(
        user_input="hello, I love this conversation",
        agent_output="thanks, glad to be useful!",
    )
    await soul.observe(interaction, user_id="alice")

    # Alice's bond went up
    assert soul.bond_for("alice").bond_strength > 50.0
    # Default bond didn't move
    assert soul.bond.default.bond_strength == pytest.approx(starting_default)


# ---------------------------------------------------------------------------
# Export / awaken round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_round_trip_preserves_user_ids(tmp_path: Path, soul):
    """Memories' user_ids and per-user bond strengths survive export+awaken."""
    # Create a mix of memories tagged for two users
    await soul._memory.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="alice prefers oat milk",
            importance=7,
            user_id="alice",
        )
    )
    await soul._memory.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="bob takes his coffee black",
            importance=7,
            user_id="bob",
        )
    )

    # Touch both per-user bonds so they survive
    soul.bond.strengthen(10.0, user_id="alice")
    soul.bond.strengthen(5.0, user_id="bob")

    # Export → awaken
    out = tmp_path / "aria.soul"
    await soul.export(out)
    rebirth = await Soul.awaken(out)

    # Memory user_ids preserved
    facts = rebirth._memory._semantic.facts(include_superseded=True)
    by_user = {f.content: f.user_id for f in facts}
    assert by_user.get("alice prefers oat milk") == "alice"
    assert by_user.get("bob takes his coffee black") == "bob"

    # Per-user bonds preserved
    assert rebirth.bonded_users == sorted(rebirth.bonded_users)
    assert "alice" in rebirth.bonded_users
    assert "bob" in rebirth.bonded_users
    assert rebirth.bond_for("alice").bond_strength == pytest.approx(55.0)
    assert rebirth.bond_for("bob").bond_strength == pytest.approx(52.5)


# ---------------------------------------------------------------------------
# Legacy auto-migration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_soul_auto_migrates_bonds():
    """A soul loaded with only ``bonded_to`` set (no ``bonds``) populates ``bonds`` after awaken."""
    # Construct a config the way pre-multi-bond souls were stored:
    # bonded_to set, bonds list empty.
    identity = Identity(
        name="Legacy",
        bonded_to="did:key:legacy-user-001",
        bonds=[],
    )
    # Identity.model_post_init already auto-migrates — verify the runtime
    # path also covers the case where bonds was empty at construction time.
    config = SoulConfig(
        identity=identity,
        lifecycle=LifecycleState.ACTIVE,
    )
    s = Soul(config)

    # bonds should be populated either by Identity.model_post_init or our
    # migrate helper. Either path satisfies the contract.
    assert s.identity.bonds, "Legacy soul awaken should populate bonds"
    assert s.identity.bonds[0].id == "did:key:legacy-user-001"

    # Force the migration helper too — should be idempotent.
    info = s.migrate_to_multi_user()
    assert info["default_user_id"] == "did:key:legacy-user-001"


@pytest.mark.asyncio
async def test_migrate_stamps_legacy_memory_entries():
    """migrate_to_multi_user() stamps ``user_id`` on entries that lack one."""
    identity = Identity(name="Old", bonded_to="user-001")
    config = SoulConfig(identity=identity, lifecycle=LifecycleState.ACTIVE)
    s = Soul(config)

    # Drop a few orphan memories in (simulate pre-#46 storage)
    await s._memory.add(
        MemoryEntry(type=MemoryType.SEMANTIC, content="legacy fact 1", importance=5)
    )
    await s._memory.add(
        MemoryEntry(type=MemoryType.SEMANTIC, content="legacy fact 2", importance=5)
    )

    info = s.migrate_to_multi_user()
    assert info["memory_entries_stamped"] >= 2

    facts = s._memory._semantic.facts(include_superseded=True)
    for f in facts:
        assert f.user_id == "user-001"


# ---------------------------------------------------------------------------
# Misc back-compat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bond_proxy_back_compat(soul):
    """soul.bond.bond_strength etc. still works through the registry proxy."""
    # Reading still works
    assert soul.bond.bond_strength == 50.0
    assert soul.bond.interaction_count == 0

    # Strengthen with no user_id mutates the default — proxy reflects it
    soul.bond.strengthen(10.0)
    assert soul.bond.bond_strength == pytest.approx(55.0)
    assert soul.bond.interaction_count == 1


@pytest.mark.asyncio
async def test_bond_for_creates_bonds_lazily(soul):
    """First call to bond_for(uid) creates a fresh Bond(strength=50)."""
    assert soul.bonded_users == []
    bond = soul.bond_for("first-time")
    assert bond.bond_strength == 50.0
    assert "first-time" in soul.bonded_users
