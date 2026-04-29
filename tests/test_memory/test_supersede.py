# test_supersede.py — Tests for user-driven memory update primitives.
# Created: 2026-04-27 — Covers manager.forget_by_id (audited single-id delete),
#   manager.supersede (writes new memory + sets old.superseded_by + audit
#   entry), Soul.forget_one and Soul.supersede delegates, and the
#   supersede_audit property.

from __future__ import annotations

import pytest

from soul_protocol.runtime.memory.manager import MemoryManager
from soul_protocol.runtime.types import (
    CoreMemory,
    MemoryEntry,
    MemorySettings,
    MemoryType,
)


@pytest.fixture
def manager() -> MemoryManager:
    return MemoryManager(core=CoreMemory(), settings=MemorySettings())


# ---- manager.forget_by_id (audited) ----


@pytest.mark.asyncio
async def test_forget_by_id_returns_audited_dict_for_semantic(manager):
    """Audited single-id deletion returns a dict in forget()'s shape."""
    mem_id = await manager.add(
        MemoryEntry(type=MemoryType.SEMANTIC, content="user dislikes spam", importance=5)
    )
    result = await manager.forget_by_id(mem_id)

    assert result["found"] is True
    assert result["tier"] == "semantic"
    assert result["total"] == 1
    assert result["semantic"] == [mem_id]
    assert result["episodic"] == []
    assert result["procedural"] == []

    # And the audit trail picked it up.
    assert any(
        entry["reason"] == f"forget_by_id(memory_id='{mem_id}')" for entry in manager.deletion_audit
    )


@pytest.mark.asyncio
async def test_forget_by_id_returns_not_found_for_unknown_id(manager):
    """Unknown id yields found=False and writes no audit."""
    audit_before = len(manager.deletion_audit)
    result = await manager.forget_by_id("does-not-exist")
    assert result["found"] is False
    assert result["total"] == 0
    assert result["tier"] is None
    assert len(manager.deletion_audit) == audit_before


@pytest.mark.asyncio
async def test_forget_by_id_routes_to_episodic_tier(manager):
    """Episodic memories are deleted from the episodic tier and tagged."""
    entry = MemoryEntry(
        type=MemoryType.EPISODIC,
        content="shipped v0.3 to production",
        importance=7,
    )
    mem_id = await manager.add(entry)

    result = await manager.forget_by_id(mem_id)
    assert result["found"] is True
    assert result["tier"] == "episodic"
    assert result["episodic"] == [mem_id]


# ---- manager.supersede ----


@pytest.mark.asyncio
async def test_supersede_writes_new_memory_and_links_old(manager):
    """supersede() writes the new memory and sets old.superseded_by."""
    old_id = await manager.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="paw-enterprise has no workspace switcher",
            importance=8,
        )
    )

    result = await manager.supersede(
        old_id,
        "paw-enterprise has a workspace switcher in UserMenu.svelte",
        reason="verified against current code",
        importance=8,
    )

    assert result["found"] is True
    assert result["old_id"] == old_id
    assert result["new_id"] is not None
    assert result["new_id"] != old_id
    assert result["tier"] == "semantic"
    assert result["reason"] == "verified against current code"

    # Old entry now has superseded_by set; semantic store filters it out of
    # search by default.
    old_entry = await manager._semantic.get(old_id)
    assert old_entry is not None
    assert old_entry.superseded_by == result["new_id"]

    # The new entry is searchable; the old is not (filtered).
    hits = await manager._semantic.search("workspace switcher", limit=10)
    hit_ids = {h.id for h in hits}
    assert result["new_id"] in hit_ids
    assert old_id not in hit_ids


@pytest.mark.asyncio
async def test_supersede_returns_not_found_for_unknown_id(manager):
    """No new memory is written when old_id does not resolve."""
    audit_before = len(manager.supersede_audit)
    result = await manager.supersede(
        "does-not-exist",
        "this should not be written",
        reason="wrong",
    )
    assert result["found"] is False
    assert result["new_id"] is None
    assert len(manager.supersede_audit) == audit_before


@pytest.mark.asyncio
async def test_supersede_audit_records_user_intent(manager):
    """supersede_audit captures old_id, new_id, tier, reason."""
    old_id = await manager.add(
        MemoryEntry(type=MemoryType.SEMANTIC, content="X is missing", importance=5)
    )

    result = await manager.supersede(old_id, "X shipped on 2026-04-21", reason="PR #112")

    audit = manager.supersede_audit
    assert len(audit) == 1
    entry = audit[0]
    assert entry["old_id"] == old_id
    assert entry["new_id"] == result["new_id"]
    assert entry["tier"] == "semantic"
    assert entry["reason"] == "PR #112"
    assert "superseded_at" in entry


@pytest.mark.asyncio
async def test_supersede_audit_excludes_internal_supersession(manager):
    """Internal contradiction-resolution sets superseded_by but does not
    pollute the user-driven supersede_audit trail."""
    # Directly mark an entry's superseded_by as if dream/contradiction did it.
    old_id = await manager.add(
        MemoryEntry(type=MemoryType.SEMANTIC, content="user lives in NYC", importance=6)
    )
    new_id = await manager.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="user lives in Berlin",
            importance=6,
        )
    )
    old_entry = await manager._semantic.get(old_id)
    assert old_entry is not None
    old_entry.superseded_by = new_id

    # No user supersede() call → audit stays empty.
    assert manager.supersede_audit == []


@pytest.mark.asyncio
async def test_supersede_inherits_old_tier_by_default(manager):
    """When memory_type is None, the new entry uses the old entry's tier."""
    old_id = await manager.add(
        MemoryEntry(
            type=MemoryType.PROCEDURAL,
            content="to deploy: run ./deploy.sh",
            importance=6,
        )
    )

    result = await manager.supersede(
        old_id,
        "to deploy: run ./deploy.sh --env prod",
        reason="environment flag is now required",
    )

    assert result["tier"] == "procedural"
    new_entry = await manager._procedural.get(result["new_id"])
    assert new_entry is not None
    assert new_entry.type == MemoryType.PROCEDURAL


# ---- Soul-level delegates ----


@pytest.mark.asyncio
async def test_soul_forget_one_delegates_with_audit(tmp_path):
    """Soul.forget_one returns the audited dict and updates deletion_audit."""
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth("DelegateBot")
    mem_id = await soul.remember("temporary fact", importance=3)

    result = await soul.forget_one(mem_id)
    assert result["found"] is True
    assert result["total"] == 1
    assert any(entry["reason"].startswith("forget_by_id") for entry in soul.deletion_audit)


@pytest.mark.asyncio
async def test_soul_supersede_writes_audit_via_property():
    """Soul.supersede records to supersede_audit accessible via the property."""
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth("SupersedeBot")
    old_id = await soul.remember("FilesPanel is mock-only", importance=8)

    result = await soul.supersede(
        old_id,
        "FilesPanel hits the unified /files endpoint",
        reason="cluster-E sub-PR 4",
    )

    assert result["found"] is True
    audit = soul.supersede_audit
    assert len(audit) == 1
    assert audit[0]["old_id"] == old_id
    assert audit[0]["new_id"] == result["new_id"]
    assert audit[0]["reason"] == "cluster-E sub-PR 4"


@pytest.mark.asyncio
async def test_soul_forget_by_id_bool_signature_unchanged():
    """The legacy bool-returning forget_by_id still works (back-compat)."""
    from soul_protocol.runtime.soul import Soul

    soul = await Soul.birth("LegacyBot")
    mem_id = await soul.remember("legacy fact", importance=3)

    deleted = await soul.forget_by_id(mem_id)
    assert deleted is True

    deleted_again = await soul.forget_by_id(mem_id)
    assert deleted_again is False
