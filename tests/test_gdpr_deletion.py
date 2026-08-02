# test_gdpr_deletion.py — Tests for GDPR-compliant memory deletion.
# Created: 2026-03-10 — Comprehensive tests for forget(), forget_entity(),
#   forget_before(), cascade deletion, and audit trail.

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction, MemoryEntry, MemoryType, MemoryProvenance


@pytest.fixture
async def soul():
    """Create a fresh soul with some memories for testing deletion."""
    s = await Soul.birth(
        name="TestSoul",
        personality="A test soul for deletion testing.",
        values=["privacy", "trust"],
    )
    return s


@pytest.fixture
async def soul_with_memories(soul):
    """Soul pre-loaded with diverse memories across tiers."""
    # Add episodic memories via observe
    interactions = [
        Interaction(
            user_input="My name is Alice and I live in Berlin",
            agent_output="Nice to meet you, Alice! Berlin is a great city.",
            timestamp=datetime.now() - timedelta(days=5),
        ),
        Interaction(
            user_input="I use Python and FastAPI for my projects",
            agent_output="Those are excellent tools for web development.",
            timestamp=datetime.now() - timedelta(days=3),
        ),
        Interaction(
            user_input="I work at Acme Corp with Bob on the dashboard project",
            agent_output="The dashboard project sounds interesting!",
            timestamp=datetime.now() - timedelta(days=1),
        ),
    ]
    for interaction in interactions:
        await soul.observe(interaction)

    # Add a procedural memory directly
    await soul.remember(
        "To deploy the Alice dashboard, run deploy.sh",
        type=MemoryType.PROCEDURAL,
        importance=7,
    )

    return soul


class TestForgetQuery:
    """Tests for soul.forget(query) — search-based deletion."""

    @pytest.mark.asyncio
    async def test_forget_removes_matching_memories(self, soul_with_memories):
        """forget() should remove memories that match the query."""
        soul = soul_with_memories

        # Verify Alice-related memories exist
        results = await soul.recall("Alice")
        assert len(results) > 0, "Should have Alice memories before deletion"

        # Forget Alice
        result = await soul.forget("Alice")
        assert result["total"] > 0, "Should have deleted something"

        # Verify Alice memories are gone
        results_after = await soul.recall("Alice")
        assert len(results_after) == 0, "Alice memories should be gone after forget"

    @pytest.mark.asyncio
    async def test_forget_preserves_unrelated_memories(self, soul_with_memories):
        """forget() should not touch memories that don't match."""
        soul = soul_with_memories

        # Forget Alice
        await soul.forget("Alice")

        # Python/FastAPI memories should still exist
        results = await soul.recall("Python")
        assert len(results) > 0, "Unrelated memories should survive"

    @pytest.mark.asyncio
    async def test_forget_returns_per_tier_breakdown(self, soul_with_memories):
        """forget() should return deletion counts per tier."""
        soul = soul_with_memories
        result = await soul.forget("Alice")

        assert "episodic" in result
        assert "semantic" in result
        assert "procedural" in result
        assert "social" in result
        assert "total" in result
        assert isinstance(result["episodic"], list)
        assert isinstance(result["total"], int)

    @pytest.mark.asyncio
    async def test_forget_no_matches_returns_zero(self, soul):
        """forget() with no matches should return total=0."""
        result = await soul.forget("nonexistent_query_xyz")
        assert result["total"] == 0


class TestForgetEntity:
    """Tests for soul.forget_entity(entity) — entity-based deletion."""

    @pytest.mark.asyncio
    async def test_forget_entity_removes_graph_node(self, soul_with_memories):
        """forget_entity() should remove the entity from the knowledge graph."""
        soul = soul_with_memories

        # Add entity to graph explicitly
        await soul._memory.update_graph(
            [
                {
                    "name": "TestEntity",
                    "entity_type": "person",
                    "relationships": [{"target": "user", "relation": "knows"}],
                }
            ]
        )

        # Verify entity exists
        entities = soul._memory._graph.entities()
        assert "TestEntity" in entities

        # Forget the entity
        result = await soul.forget_entity("TestEntity")
        assert result["edges_removed"] >= 1

        # Verify entity is gone
        entities_after = soul._memory._graph.entities()
        assert "TestEntity" not in entities_after

    @pytest.mark.asyncio
    async def test_forget_entity_removes_connected_edges(self, soul_with_memories):
        """forget_entity() should remove all edges connected to the entity."""
        soul = soul_with_memories

        # Add entities with relationships
        await soul._memory.update_graph(
            [
                {
                    "name": "Alice",
                    "entity_type": "person",
                    "relationships": [
                        {"target": "user", "relation": "friend"},
                        {"target": "Berlin", "relation": "lives_in"},
                    ],
                },
                {"name": "Berlin", "entity_type": "city", "relationships": []},
            ]
        )

        # Forget Alice
        await soul.forget_entity("Alice")

        # All Alice edges should be gone
        related = soul._memory._graph.get_related("Alice")
        assert len(related) == 0

    @pytest.mark.asyncio
    async def test_forget_entity_removes_related_memories(self, soul_with_memories):
        """forget_entity() should also delete memories mentioning the entity."""
        soul = soul_with_memories

        # Forget Alice — should remove memories mentioning Alice
        result = await soul.forget_entity("Alice")
        assert result["total"] > 0

        # Verify no Alice memories remain
        results = await soul.recall("Alice")
        assert len(results) == 0


class TestForgetBefore:
    """Tests for soul.forget_before(timestamp) — time-based deletion."""

    @pytest.mark.asyncio
    async def test_forget_before_removes_old_memories(self, soul_with_memories):
        """forget_before() should remove memories older than the cutoff."""
        soul = soul_with_memories

        # Delete memories older than 2 days
        cutoff = datetime.now() - timedelta(days=2)
        result = await soul.forget_before(cutoff)

        assert result["total"] > 0, "Should have deleted old memories"

    @pytest.mark.asyncio
    async def test_forget_before_preserves_recent_memories(self, soul_with_memories):
        """forget_before() should keep memories newer than the cutoff."""
        soul = soul_with_memories

        # Remember the count before
        count_before = soul.memory_count

        # Delete memories older than 10 days (nothing should match since our oldest is 5 days)
        cutoff = datetime.now() - timedelta(days=10)
        result = await soul.forget_before(cutoff)

        assert result["total"] == 0, "No memories should be that old"
        assert soul.memory_count == count_before

    @pytest.mark.asyncio
    async def test_forget_before_returns_per_tier_breakdown(self, soul_with_memories):
        """forget_before() should return per-tier deletion counts."""
        soul = soul_with_memories
        cutoff = datetime.now() - timedelta(days=2)
        result = await soul.forget_before(cutoff)

        assert "episodic" in result
        assert "semantic" in result
        assert "procedural" in result
        assert "social" in result
        assert "total" in result


class TestDeletionAuditTrail:
    """Tests for the deletion audit trail."""

    @pytest.mark.asyncio
    async def test_audit_trail_records_deletion(self, soul_with_memories):
        """Deletion should create an audit trail entry."""
        soul = soul_with_memories

        assert len(soul.deletion_audit) == 0, "No audits before deletion"

        await soul.forget("Alice")

        audit = soul.deletion_audit
        assert len(audit) >= 1, "Should have audit entry after deletion"

    @pytest.mark.asyncio
    async def test_audit_entry_has_required_fields(self, soul_with_memories):
        """Each audit entry should have deleted_at, count, reason."""
        soul = soul_with_memories
        await soul.forget("Alice")

        entry = soul.deletion_audit[0]
        assert "deleted_at" in entry
        assert "count" in entry
        assert "reason" in entry
        assert entry["count"] > 0

    @pytest.mark.asyncio
    async def test_audit_does_not_contain_deleted_content(self, soul_with_memories):
        """Audit trail must NOT contain the actual deleted content."""
        soul = soul_with_memories
        await soul.forget("Alice")

        audit_str = str(soul.deletion_audit)
        # The audit should not contain the actual memory content
        assert "Nice to meet you" not in audit_str
        assert "Berlin is a great city" not in audit_str

    @pytest.mark.asyncio
    async def test_audit_trail_accumulates(self, soul_with_memories):
        """Multiple deletions should accumulate audit entries."""
        soul = soul_with_memories

        await soul.forget("Alice")
        await soul.forget("Python")

        assert len(soul.deletion_audit) >= 2

    @pytest.mark.asyncio
    async def test_no_audit_when_nothing_deleted(self, soul):
        """No audit entry should be created when nothing is deleted."""
        result = await soul.forget("nonexistent_xyz")
        assert result["total"] == 0
        assert len(soul.deletion_audit) == 0

    @pytest.mark.asyncio
    async def test_forget_entity_creates_audit(self, soul_with_memories):
        """forget_entity() should also create audit entries."""
        soul = soul_with_memories
        await soul._memory.update_graph(
            [
                {
                    "name": "AuditTestEntity",
                    "entity_type": "person",
                    "relationships": [{"target": "user", "relation": "knows"}],
                }
            ]
        )
        await soul.forget_entity("AuditTestEntity")

        audit = soul.deletion_audit
        assert len(audit) >= 1
        assert "forget_entity" in audit[-1]["reason"]

    @pytest.mark.asyncio
    async def test_forget_before_creates_audit(self, soul_with_memories):
        """forget_before() should also create audit entries."""
        soul = soul_with_memories
        cutoff = datetime.now() - timedelta(days=2)
        await soul.forget_before(cutoff)

        audit = soul.deletion_audit
        assert any("forget_before" in entry["reason"] for entry in audit)


class TestDeletedMemoriesInvisible:
    """Tests that deleted memories don't appear in recall results."""

    @pytest.mark.asyncio
    async def test_deleted_memories_not_in_recall(self, soul_with_memories):
        """After forget(), matching memories should not appear in recall."""
        soul = soul_with_memories

        # Verify presence first
        before = await soul.recall("Alice Berlin")
        assert len(before) > 0

        # Delete
        await soul.forget("Alice Berlin")

        # Verify absence
        after = await soul.recall("Alice Berlin")
        assert len(after) == 0

    @pytest.mark.asyncio
    async def test_forget_by_id_still_works(self, soul_with_memories):
        """The renamed forget_by_id() should still work for single ID deletion."""
        soul = soul_with_memories

        # Remember something and get its ID
        mem_id = await soul.remember("temporary test memory", importance=3)

        # Verify it exists
        results = await soul.recall("temporary test memory")
        assert len(results) > 0

        # Delete by ID
        deleted = await soul.forget_by_id(mem_id)
        assert deleted is True

        # Verify gone
        results = await soul.recall("temporary test memory")
        assert len(results) == 0


class TestStoreLevel:
    """Tests for the store-level deletion methods directly."""

    @pytest.mark.asyncio
    async def test_episodic_search_and_delete(self):
        """EpisodicStore.search_and_delete() should work correctly."""
        from soul_protocol.runtime.memory.episodic import EpisodicStore

        store = EpisodicStore()
        interaction = Interaction(
            user_input="I like cats",
            agent_output="Cats are great!",
        )
        await store.add(interaction)

        deleted = await store.search_and_delete("cats")
        assert len(deleted) > 0
        assert len(store.entries()) == 0

    @pytest.mark.asyncio
    async def test_semantic_search_and_delete(self):
        """SemanticStore.search_and_delete() should work correctly."""
        from soul_protocol.runtime.memory.semantic import SemanticStore

        store = SemanticStore()
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="User likes cats", importance=5)
        await store.add(entry)

        deleted = await store.search_and_delete("cats")
        assert len(deleted) > 0
        assert len(store.facts()) == 0

    @pytest.mark.asyncio
    async def test_procedural_search_and_delete(self):
        """ProceduralStore.search_and_delete() should work correctly."""
        from soul_protocol.runtime.memory.procedural import ProceduralStore

        store = ProceduralStore()
        entry = MemoryEntry(
            type=MemoryType.PROCEDURAL, content="To feed cats, open can", importance=5
        )
        await store.add(entry)

        deleted = await store.search_and_delete("cats")
        assert len(deleted) > 0
        assert len(store.entries()) == 0

    @pytest.mark.asyncio
    async def test_episodic_delete_before(self):
        """EpisodicStore.delete_before() should remove old entries."""
        from soul_protocol.runtime.memory.episodic import EpisodicStore

        store = EpisodicStore()
        old_interaction = Interaction(
            user_input="old message",
            agent_output="old reply",
            timestamp=datetime.now() - timedelta(days=10),
        )
        new_interaction = Interaction(
            user_input="new message",
            agent_output="new reply",
            timestamp=datetime.now(),
        )
        await store.add(old_interaction)
        await store.add(new_interaction)

        cutoff = datetime.now() - timedelta(days=5)
        deleted = await store.delete_before(cutoff)
        assert len(deleted) == 1
        assert len(store.entries()) == 1

    @pytest.mark.asyncio
    async def test_graph_remove_entity(self):
        """KnowledgeGraph.remove_entity() should remove entity and edges."""
        from soul_protocol.runtime.memory.graph import KnowledgeGraph

        graph = KnowledgeGraph()
        graph.add_entity("Alice", "person")
        graph.add_entity("Bob", "person")
        graph.add_relationship("Alice", "Bob", "knows")
        graph.add_relationship("Bob", "Alice", "knows")

        edges_removed = graph.remove_entity("Alice")
        assert edges_removed == 2
        assert "Alice" not in graph.entities()
        assert "Bob" in graph.entities()
        assert len(graph.get_related("Bob")) == 0

    @pytest.mark.asyncio
    async def test_social_search_and_delete(self):
        """SocialStore.search_and_delete() should work correctly."""
        from soul_protocol.runtime.memory.social import SocialStore

        store = SocialStore()
        entry = MemoryEntry(
            type=MemoryType.SOCIAL, content="Alice is a trusted friend", importance=5
        )
        await store.add(entry)

        deleted = await store.search_and_delete("Alice")
        assert len(deleted) > 0
        assert len(store.entries()) == 0

    @pytest.mark.asyncio
    async def test_social_delete_before(self):
        """SocialStore.delete_before() should remove old entries."""
        from soul_protocol.runtime.memory.social import SocialStore

        store = SocialStore()
        old_entry = MemoryEntry(
            type=MemoryType.SOCIAL,
            content="old relationship data",
            importance=3,
        )
        old_entry.created_at = datetime.now() - timedelta(days=10)
        new_entry = MemoryEntry(
            type=MemoryType.SOCIAL,
            content="new relationship data",
            importance=3,
        )
        await store.add(old_entry)
        await store.add(new_entry)

        cutoff = datetime.now() - timedelta(days=5)
        deleted = await store.delete_before(cutoff)
        assert len(deleted) == 1
        assert len(store.entries()) == 1


# ---------------------------------------------------------------------------
# Social-tier deletion tests (#291)
# ---------------------------------------------------------------------------

@pytest.fixture
async def soul_with_social_memories(soul):
    """Soul pre-loaded with social memories for social-tier deletion tests."""
    # Add social memories directly to the social store
    soc1 = MemoryEntry(
        type=MemoryType.SOCIAL,
        content="Alice prefers email communication on weekdays",
        importance=6,
        domain="default",
    )
    soc2 = MemoryEntry(
        type=MemoryType.SOCIAL,
        content="Bob has high trust level from previous projects",
        importance=8,
        domain="default",
    )
    soc3 = MemoryEntry(
        type=MemoryType.SOCIAL,
        content="Charlie response time averages 2 hours",
        importance=4,
        domain="default",
    )
    # Set an old timestamp on soc3 for forget_before tests
    soc3.created_at = datetime.now() - timedelta(days=30)

    await soul._memory._social.add(soc1)
    await soul._memory._social.add(soc2)
    await soul._memory._social.add(soc3)

    # Also add an old non-social memory so forget_before has something to find
    old_ep = MemoryEntry(
        type=MemoryType.SEMANTIC,
        content="Old semantic fact about legacy system",
        importance=3,
    )
    old_ep.created_at = datetime.now() - timedelta(days=30)
    await soul._memory._semantic.add(old_ep)

    return soul


class TestSocialDeletion:
    """Tests that deletion operations cover the social memory tier (#291)."""

    @pytest.mark.asyncio
    async def test_find_entry_by_id_finds_social(self, soul_with_social_memories):
        """_find_entry_by_id should locate entries in the social tier."""
        soul = soul_with_social_memories
        social_entries = soul._memory._social.entries()
        assert len(social_entries) >= 3, "Should have social memories seeded"

        target = social_entries[0]
        entry, tier = await soul._memory._find_entry_by_id(target.id)
        assert entry is not None, "_find_entry_by_id should find the social entry"
        assert tier == "social", f"Expected 'social' tier, got {tier!r}"
        assert entry.id == target.id

    @pytest.mark.asyncio
    async def test_forget_deletes_social_memories(self, soul_with_social_memories):
        """forget() should weight-decay matching social memories."""
        soul = soul_with_social_memories
        social_before = len(soul._memory._social.entries())
        assert social_before >= 3

        # Forget memories mentioning Alice (v0.5.0: weight-decay, not hard delete)
        result = await soul.forget("Alice")
        assert result["total"] > 0, "forget should have matched something"
        assert "social" in result
        assert len(result["social"]) > 0, "should have matched social entries mentioning Alice"

        # Alice social memory should be weight-decayed (0.05) — still on disk,
        # but invisible to recall with default min_weight=0.1 floor.
        for entry in soul._memory._social.entries():
            if "Alice" in entry.content:
                assert entry.retrieval_weight == 0.05, (
                    f"Alice social entry should be weight-decayed, "
                    f"got weight={entry.retrieval_weight}"
                )

    @pytest.mark.asyncio
    async def test_forget_entity_deletes_social_memories(self, soul_with_social_memories):
        """forget_entity() should delete social memories mentioning the entity."""
        soul = soul_with_social_memories

        # Add entity to graph
        await soul._memory.update_graph(
            [{"name": "Bob", "entity_type": "person", "relationships": []}]
        )

        result = await soul.forget_entity("Bob")
        assert result["total"] > 0
        assert "social" in result

        # No social memory should mention Bob
        for entry in soul._memory._social.entries():
            assert "Bob" not in entry.content

    @pytest.mark.asyncio
    async def test_forget_before_deletes_social_memories(self, soul_with_social_memories):
        """forget_before() should delete old social memories."""
        soul = soul_with_social_memories
        social_before = len(soul._memory._social.entries())

        cutoff = datetime.now() - timedelta(days=7)
        result = await soul.forget_before(cutoff)
        assert result["total"] > 0
        assert "social" in result
        assert len(result["social"]) > 0, (
            "forget_before should have deleted old social entries"
        )

        social_after = len(soul._memory._social.entries())
        assert social_after < social_before, "Social store should have fewer entries"

    @pytest.mark.asyncio
    async def test_purge_by_id_deletes_social_memories(self, soul_with_social_memories):
        """purge_by_id() should hard-delete a social entry."""
        soul = soul_with_social_memories
        social_entries = soul._memory._social.entries()
        target = social_entries[0]

        result = await soul.purge(target.id)
        assert result["found"] is True
        assert result["tier"] == "social"
        assert "prior_payload_hash" in result

        # Verify it's gone
        entry, _ = await soul._memory.find_by_id(target.id)
        assert entry is None, "Purged social entry should not be findable"

    @pytest.mark.asyncio
    async def test_social_survives_save_awaken_recall_roundtrip(self, soul_with_social_memories):
        """Social memory should survive save → awaken → recall, and
        forget should persist through the round-trip."""
        import tempfile
        from pathlib import Path

        soul = soul_with_social_memories
        social_before = soul._memory._social.entries()
        assert len(social_before) >= 3

        with tempfile.TemporaryDirectory() as tmpdir:
            # save_local writes a flat directory that awaken() loads via load_soul_full()
            save_dir = Path(tmpdir) / "test-social"
            await soul.save_local(str(save_dir))

            # Awaken — social memories should still be there
            restored = await Soul.awaken(str(save_dir))
            restored_social = restored._memory._social.entries()
            assert len(restored_social) == len(social_before), (
                "All social memories should survive save → awaken"
            )

            # Forget Alice on the restored soul
            await restored.forget("Alice")
            restored_social_after = restored._memory._social.entries()
            for entry in restored_social_after:
                # v0.5.0: weight-decay keeps entries on disk; verify they
                # are still present but weight-decayed.
                if "Alice" in entry.content:
                    assert entry.retrieval_weight == 0.05, (
                        "Alice social entries should be weight-decayed"
                    )

            # Save again
            save2_dir = Path(tmpdir) / "test-social-forgotten"
            await restored.save_local(str(save2_dir))

            # Re-awaken — weight-decayed social memories survive the round-trip
            reawakened = await Soul.awaken(str(save2_dir))
            reawakened_social = reawakened._memory._social.entries()
            # All original entries should still exist (weight-decayed, not purged)
            assert len(reawakened_social) == len(social_before), (
                "All social memories should survive save → re-awaken"
            )

    @pytest.mark.asyncio
    async def test_forget_entity_audit_includes_social(self, soul_with_social_memories):
        """forget_entity audit should track social tier deletions."""
        soul = soul_with_social_memories
        await soul._memory.update_graph(
            [{"name": "Charlie", "entity_type": "person", "relationships": []}]
        )

        await soul.forget_entity("Charlie")
        audit = soul.deletion_audit
        assert len(audit) >= 1
        tiers = audit[-1].get("tiers", {})
        assert "social" in tiers, f"Audit tiers should include social, got {tiers}"

    @pytest.mark.asyncio
    async def test_forget_before_audit_includes_social(self, soul_with_social_memories):
        """forget_before audit should track social tier deletions."""
        soul = soul_with_social_memories
        cutoff = datetime.now() - timedelta(days=7)
        await soul.forget_before(cutoff)

        audit = soul.deletion_audit
        assert len(audit) >= 1
        tiers = audit[-1].get("tiers", {})
        assert "social" in tiers, f"Audit tiers should include social, got {tiers}"
