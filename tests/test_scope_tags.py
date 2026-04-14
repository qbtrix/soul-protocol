"""Tests for scope tags + the match_scope helper (Move 5 PR-A).

Created: 2026-04-13 — Hierarchical RBAC/ABAC matching, MemoryEntry shape
preservation across export/awaken, and Soul.recall scope-filter semantics.
Updated: 2026-04-14 — match_scope is now bidirectional containment, so
a caller scope that sits inside a memory's glob scope (and vice versa)
matches. Tests cover both directions plus the strict one-way variant.
"""

from __future__ import annotations

import pytest

from soul_protocol import Soul
from soul_protocol.runtime.types import MemoryType
from soul_protocol.spec.memory import MemoryEntry
from soul_protocol.spec.scope import match_scope, match_scope_strict, normalise_scopes

# ---------------------------------------------------------------------------
# match_scope
# ---------------------------------------------------------------------------


class TestMatchScope:
    def test_exact_match_grants(self) -> None:
        assert match_scope(["org:sales:leads"], ["org:sales:leads"])

    def test_no_overlap_denies(self) -> None:
        assert not match_scope(["org:finance:reports"], ["org:sales:*"])

    def test_glob_matches_exact_prefix(self) -> None:
        assert match_scope(["org:sales:leads"], ["org:sales:*"])
        assert match_scope(["org:sales:deals"], ["org:sales:*"])
        # The bare prefix itself is included.
        assert match_scope(["org:sales"], ["org:sales:*"])

    def test_glob_does_not_cross_segment_boundary(self) -> None:
        # "org:sales*" is NOT a valid glob — only "*:" wildcarding is supported.
        assert not match_scope(["org:salesforce"], ["org:sales:*"])

    def test_star_matches_everything(self) -> None:
        assert match_scope(["org:hr:payroll"], ["*"])

    def test_empty_entity_scopes_visible_to_anyone(self) -> None:
        """No scope tag = no scope check. Pre-scope memories stay visible."""
        assert match_scope([], ["org:sales:*"])
        assert match_scope(None, ["org:sales:*"])

    def test_empty_allowed_scopes_passes_through(self) -> None:
        """Caller without a scope filter sees everything."""
        assert match_scope(["org:sales:leads"], [])
        assert match_scope(["org:sales:leads"], None)

    def test_at_least_one_match_grants(self) -> None:
        # Entity has multiple scopes; granted if ANY allowed grants ANY of them.
        assert match_scope(
            ["org:sales:leads", "org:marketing:content"],
            ["org:marketing:*"],
        )

    def test_unknown_pattern_does_not_grant(self) -> None:
        # Patterns must be exact or end with `:*`; arbitrary substrings don't.
        assert not match_scope(["org:sales:leads"], ["sales"])

    # ---- bidirectional containment (v0.3.1 follow-up to #163) ----------

    def test_concrete_caller_matches_glob_entity(self) -> None:
        """A caller with scope `org:sales:leads` sees memories tagged
        `org:sales:*`. This is the bundled-archetype use case."""
        assert match_scope(["org:sales:*"], ["org:sales:leads"])

    def test_glob_entity_matches_broader_glob_caller(self) -> None:
        """A broader-glob caller sees a nested-glob entity."""
        assert match_scope(["org:sales:*"], ["org:*"])
        assert match_scope(["org:*"], ["org:sales:*"])

    def test_sibling_subtrees_do_not_match(self) -> None:
        assert not match_scope(["org:sales:leads"], ["org:support:*"])
        assert not match_scope(["org:sales:*"], ["org:support:leads"])

    def test_star_caller_sees_everything(self) -> None:
        assert match_scope(["org:anything:deep:here"], ["*"])
        assert match_scope(["*"], ["org:anything:deep:here"])

    def test_empty_edges(self) -> None:
        # Either empty side → permissive pass-through.
        assert match_scope([], [])
        assert match_scope(None, None)
        assert match_scope(["org:sales:*"], [])
        assert match_scope([], ["org:sales:*"])


class TestMatchScopeStrict:
    """The one-directional variant preserves the pre-v0.3.1 behaviour for
    callers that genuinely need `allowed_scopes` to contain `entity_scopes`."""

    def test_asymmetric_direction(self) -> None:
        # Caller's glob grants the memory's concrete scope.
        assert match_scope_strict(["org:sales:leads"], ["org:sales:*"])
        # Memory's glob is NOT granted by a narrower caller under the old rule.
        assert not match_scope_strict(["org:sales:*"], ["org:sales:leads"])

    def test_exact_and_star(self) -> None:
        assert match_scope_strict(["org:sales:leads"], ["org:sales:leads"])
        assert match_scope_strict(["org:sales:leads"], ["*"])

    def test_empty_pass_through(self) -> None:
        assert match_scope_strict([], ["org:sales:*"])
        assert match_scope_strict(["org:sales:*"], [])


class TestNormaliseScopes:
    def test_lowercases_strips_dedupes(self) -> None:
        cleaned = normalise_scopes(["Org:Sales:*", "  org:sales:*  ", "org:finance:read"])
        assert cleaned == ["org:sales:*", "org:finance:read"]

    def test_drops_empty_and_non_string(self) -> None:
        cleaned = normalise_scopes(["", " ", None, 42, "org:sales"])  # type: ignore[list-item]
        assert cleaned == ["org:sales"]

    def test_none_returns_empty(self) -> None:
        assert normalise_scopes(None) == []


# ---------------------------------------------------------------------------
# MemoryEntry shape
# ---------------------------------------------------------------------------


class TestMemoryEntryScopeField:
    def test_default_is_empty_list(self) -> None:
        entry = MemoryEntry(content="hi")
        assert entry.scope == []

    def test_round_trip_preserves_scope(self) -> None:
        entry = MemoryEntry(content="hi", scope=["org:sales:*", "org:marketing:read"])
        restored = MemoryEntry.model_validate(entry.model_dump())
        assert restored.scope == entry.scope


# ---------------------------------------------------------------------------
# Soul.recall scope filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_without_scopes_kwarg_returns_all() -> None:
    soul = await Soul.birth(name="Echo", archetype="Test")
    await soul.remember("coffee is part of the morning routine")
    await soul.remember("the team prefers light roast coffee")

    results = await soul.recall("coffee")
    # Default behaviour preserved — no scope filter applied.
    assert len(results) >= 2


@pytest.mark.asyncio
async def test_recall_with_scopes_filters_unscoped_memories_in() -> None:
    """Memories without scope are visible to any scoped caller — back-compat."""
    soul = await Soul.birth(name="Echo", archetype="Test")
    await soul.remember("the renewal policy caps discount at twenty percent")

    results = await soul.recall("renewal policy discount", scopes=["org:sales:*"])
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_recall_with_scopes_filters_disallowed_memories_out() -> None:
    soul = await Soul.birth(name="Echo", archetype="Test")
    await soul.remember("internal salary band data confidential")

    semantic = soul._memory._semantic._facts  # type: ignore[attr-defined]
    assert len(semantic) >= 1
    for entry in semantic.values():
        entry.scope = ["org:finance:reports"]

    sales_caller = await soul.recall("salary band", scopes=["org:sales:*"])
    assert sales_caller == []

    finance_caller = await soul.recall("salary band", scopes=["org:finance:*"])
    assert len(finance_caller) >= 1


@pytest.mark.asyncio
async def test_runtime_memory_entry_carries_scope() -> None:
    """The runtime MemoryEntry has the field too — so producers can attach it."""
    from soul_protocol.runtime.types import MemoryEntry as RuntimeMemoryEntry

    entry = RuntimeMemoryEntry(
        type=MemoryType.SEMANTIC,
        content="hi",
        scope=["org:sales:*"],
    )
    assert entry.scope == ["org:sales:*"]
