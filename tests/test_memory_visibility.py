# test_memory_visibility.py — Tests for memory visibility tiers (#97).
# Created: feat/memory-visibility-templates — Validates that PRIVATE memories
#   don't leak to unbonded requesters, BONDED memories require bond threshold,
#   PUBLIC memories are always accessible, and backward compat is preserved.

from __future__ import annotations

import pytest

from soul_protocol.runtime.memory.recall import (
    DEFAULT_BOND_THRESHOLD,
    filter_by_visibility,
)
from soul_protocol.runtime.types import (
    MemoryEntry,
    MemoryType,
    MemoryVisibility,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    content: str,
    visibility: MemoryVisibility = MemoryVisibility.BONDED,
    mem_type: MemoryType = MemoryType.SEMANTIC,
) -> MemoryEntry:
    return MemoryEntry(
        type=mem_type,
        content=content,
        visibility=visibility,
    )


# ---------------------------------------------------------------------------
# MemoryVisibility enum
# ---------------------------------------------------------------------------


class TestMemoryVisibilityEnum:
    def test_values(self):
        assert MemoryVisibility.PUBLIC == "public"
        assert MemoryVisibility.BONDED == "bonded"
        assert MemoryVisibility.PRIVATE == "private"

    def test_members(self):
        assert set(MemoryVisibility) == {
            MemoryVisibility.PUBLIC,
            MemoryVisibility.BONDED,
            MemoryVisibility.PRIVATE,
        }

    def test_string_coercion(self):
        assert str(MemoryVisibility.PUBLIC) == "public"


# ---------------------------------------------------------------------------
# MemoryEntry visibility field
# ---------------------------------------------------------------------------


class TestMemoryEntryVisibility:
    def test_default_visibility_is_bonded(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test")
        assert entry.visibility == MemoryVisibility.BONDED

    def test_set_public(self):
        entry = _make_entry("public note", MemoryVisibility.PUBLIC)
        assert entry.visibility == MemoryVisibility.PUBLIC

    def test_set_private(self):
        entry = _make_entry("secret", MemoryVisibility.PRIVATE)
        assert entry.visibility == MemoryVisibility.PRIVATE

    def test_serialization_roundtrip(self):
        entry = _make_entry("test", MemoryVisibility.PRIVATE)
        data = entry.model_dump()
        assert data["visibility"] == "private"
        restored = MemoryEntry.model_validate(data)
        assert restored.visibility == MemoryVisibility.PRIVATE

    def test_backward_compat_no_visibility_field(self):
        """Old data without visibility field should default to BONDED."""
        data = {
            "type": "semantic",
            "content": "legacy memory",
            "importance": 5,
        }
        entry = MemoryEntry.model_validate(data)
        assert entry.visibility == MemoryVisibility.BONDED


# ---------------------------------------------------------------------------
# filter_by_visibility()
# ---------------------------------------------------------------------------


class TestFilterByVisibility:
    def test_system_context_sees_everything(self):
        """requester_id=None means soul/system — full access."""
        entries = [
            _make_entry("pub", MemoryVisibility.PUBLIC),
            _make_entry("bonded", MemoryVisibility.BONDED),
            _make_entry("secret", MemoryVisibility.PRIVATE),
        ]
        result = filter_by_visibility(entries, requester_id=None, bond_strength=0.0)
        assert len(result) == 3

    def test_public_always_visible(self):
        entries = [_make_entry("pub", MemoryVisibility.PUBLIC)]
        result = filter_by_visibility(entries, requester_id="stranger", bond_strength=0.0)
        assert len(result) == 1

    def test_private_never_visible_to_external(self):
        entries = [_make_entry("secret", MemoryVisibility.PRIVATE)]
        # Even with max bond strength, PRIVATE is hidden from external
        result = filter_by_visibility(entries, requester_id="bonded_user", bond_strength=100.0)
        assert len(result) == 0

    def test_bonded_visible_above_threshold(self):
        entries = [_make_entry("bonded note", MemoryVisibility.BONDED)]
        result = filter_by_visibility(
            entries, requester_id="user1", bond_strength=50.0, bond_threshold=30.0
        )
        assert len(result) == 1

    def test_bonded_hidden_below_threshold(self):
        entries = [_make_entry("bonded note", MemoryVisibility.BONDED)]
        result = filter_by_visibility(
            entries, requester_id="user1", bond_strength=10.0, bond_threshold=30.0
        )
        assert len(result) == 0

    def test_bonded_exact_threshold(self):
        """Bond strength exactly at threshold should allow access."""
        entries = [_make_entry("bonded", MemoryVisibility.BONDED)]
        result = filter_by_visibility(
            entries, requester_id="user1", bond_strength=30.0, bond_threshold=30.0
        )
        assert len(result) == 1

    def test_mixed_visibility_filtering(self):
        entries = [
            _make_entry("pub1", MemoryVisibility.PUBLIC),
            _make_entry("bonded1", MemoryVisibility.BONDED),
            _make_entry("secret1", MemoryVisibility.PRIVATE),
            _make_entry("pub2", MemoryVisibility.PUBLIC),
            _make_entry("bonded2", MemoryVisibility.BONDED),
        ]
        # Low bond — only PUBLIC visible
        result = filter_by_visibility(
            entries, requester_id="stranger", bond_strength=5.0, bond_threshold=30.0
        )
        assert len(result) == 2
        assert all(e.visibility == MemoryVisibility.PUBLIC for e in result)

    def test_high_bond_sees_public_and_bonded(self):
        entries = [
            _make_entry("pub", MemoryVisibility.PUBLIC),
            _make_entry("bonded", MemoryVisibility.BONDED),
            _make_entry("secret", MemoryVisibility.PRIVATE),
        ]
        result = filter_by_visibility(
            entries, requester_id="trusted", bond_strength=80.0, bond_threshold=30.0
        )
        assert len(result) == 2
        visibilities = {e.visibility for e in result}
        assert MemoryVisibility.PRIVATE not in visibilities

    def test_empty_entries(self):
        result = filter_by_visibility([], requester_id="user", bond_strength=50.0)
        assert result == []

    def test_default_threshold(self):
        assert DEFAULT_BOND_THRESHOLD == 30.0

    def test_zero_bond_threshold(self):
        """Zero threshold means any bond gets BONDED access."""
        entries = [_make_entry("bonded", MemoryVisibility.BONDED)]
        result = filter_by_visibility(
            entries, requester_id="user", bond_strength=0.0, bond_threshold=0.0
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Soul.recall() with visibility (integration)
# ---------------------------------------------------------------------------


class TestSoulRecallVisibility:
    @pytest.mark.asyncio
    async def test_default_recall_sees_all(self):
        """Without requester_id, all visibility tiers are returned."""
        from soul_protocol import MemoryVisibility, Soul

        soul = await Soul.birth("VisTest")
        await soul.remember("public fact", visibility=MemoryVisibility.PUBLIC)
        await soul.remember("bonded fact", visibility=MemoryVisibility.BONDED)
        await soul.remember("private fact", visibility=MemoryVisibility.PRIVATE)

        results = await soul.recall("fact")
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_external_requester_filtered(self):
        from soul_protocol import MemoryVisibility, Soul

        soul = await Soul.birth("VisTest2")
        await soul.remember("public info", visibility=MemoryVisibility.PUBLIC)
        await soul.remember("bonded info", visibility=MemoryVisibility.BONDED)
        await soul.remember("private info", visibility=MemoryVisibility.PRIVATE)

        # External requester with high bond
        results = await soul.recall("info", requester_id="user-123", bond_strength=80.0)
        vis_set = {r.visibility for r in results}
        assert MemoryVisibility.PUBLIC in vis_set
        assert MemoryVisibility.BONDED in vis_set
        assert MemoryVisibility.PRIVATE not in vis_set

    @pytest.mark.asyncio
    async def test_low_bond_only_public(self):
        from soul_protocol import MemoryVisibility, Soul

        soul = await Soul.birth("VisTest3")
        await soul.remember("public note", visibility=MemoryVisibility.PUBLIC)
        await soul.remember("bonded note", visibility=MemoryVisibility.BONDED)

        results = await soul.recall("note", requester_id="stranger", bond_strength=5.0)
        assert len(results) == 1
        assert results[0].visibility == MemoryVisibility.PUBLIC

    @pytest.mark.asyncio
    async def test_recall_uses_soul_bond_by_default(self):
        """When bond_strength is None, uses the soul's own bond."""
        from soul_protocol import MemoryVisibility, Soul

        soul = await Soul.birth("VisTest4")
        # Default bond starts at 50 > 30 threshold
        await soul.remember("bonded data", visibility=MemoryVisibility.BONDED)
        results = await soul.recall("data", requester_id="user-456")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_remember_default_visibility(self):
        """remember() defaults to BONDED visibility."""
        from soul_protocol import MemoryVisibility, Soul

        soul = await Soul.birth("VisTest5")
        await soul.remember("some fact")
        results = await soul.recall("fact")
        assert results[0].visibility == MemoryVisibility.BONDED

    @pytest.mark.asyncio
    async def test_remember_explicit_visibility(self):
        from soul_protocol import MemoryVisibility, Soul

        soul = await Soul.birth("VisTest6")
        await soul.remember("open fact", visibility=MemoryVisibility.PUBLIC)
        results = await soul.recall("fact")
        assert results[0].visibility == MemoryVisibility.PUBLIC


# ---------------------------------------------------------------------------
# Spec-level MemoryVisibility
# ---------------------------------------------------------------------------


class TestSpecMemoryVisibility:
    def test_spec_memory_entry_has_visibility(self):
        from soul_protocol.spec.memory import MemoryEntry as SpecEntry
        from soul_protocol.spec.memory import MemoryVisibility as SpecVis

        entry = SpecEntry(content="test")
        assert entry.visibility == SpecVis.BONDED

    def test_spec_visibility_values(self):
        from soul_protocol.spec.memory import MemoryVisibility as SpecVis

        assert SpecVis.PUBLIC == "public"
        assert SpecVis.BONDED == "bonded"
        assert SpecVis.PRIVATE == "private"
