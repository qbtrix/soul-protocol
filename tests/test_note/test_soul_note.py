# tests/test_note/test_soul_note.py
# Created: 2026-05-06 (#231) — Runtime coverage for Soul.note(), the
# fact-shaped writer that routes through reconcile_fact() before storing.
# Verifies the four return-shape keys (action, id, existing_id, similarity)
# and the SKIP / MERGE / CREATE branches across semantic, procedural, and
# episodic tiers, plus the dedup=False opt-out and per-domain isolation.
# Implementation lives at src/soul_protocol/runtime/soul.py:Soul.note().

from __future__ import annotations

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryType

# --- Helpers -----------------------------------------------------------------


def _semantic_count(soul: Soul, *, include_superseded: bool = False) -> int:
    """Count semantic facts in the soul's store."""
    return len(soul._memory._semantic.facts(include_superseded=include_superseded))


def _procedural_count(soul: Soul) -> int:
    """Count procedural entries in the soul's store."""
    return len(soul._memory._procedural.entries())


# --- Return-shape contract ---------------------------------------------------


@pytest.mark.asyncio
async def test_note_returns_four_keys_on_create():
    """The return dict always carries action, id, existing_id, similarity."""
    soul = await Soul.birth("Aria", archetype="t")

    result = await soul.note("brand new fact about the project")

    assert set(result.keys()) == {"action", "id", "existing_id", "similarity"}
    assert result["action"] == "CREATE"
    assert isinstance(result["id"], str) and len(result["id"]) > 0
    assert result["existing_id"] is None
    assert result["similarity"] is None


# --- CREATE path -------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_path_stores_memory_and_returns_id():
    """First call against an empty semantic store returns CREATE and stores."""
    soul = await Soul.birth("Aria", archetype="t")
    assert _semantic_count(soul) == 0

    result = await soul.note("brand new fact about the project")

    assert result["action"] == "CREATE"
    assert result["id"] is not None
    assert result["existing_id"] is None
    assert result["similarity"] is None
    assert _semantic_count(soul) == 1


# --- SKIP path ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_path_returns_existing_id_and_does_not_store():
    """Two identical notes: second returns SKIP, count stays at 1."""
    soul = await Soul.birth("Aria", archetype="t")

    first = await soul.note("user prefers dark mode in the editor")
    assert first["action"] == "CREATE"
    assert _semantic_count(soul) == 1

    second = await soul.note("user prefers dark mode in the editor")

    assert second["action"] == "SKIP"
    assert second["id"] is None
    assert second["existing_id"] == first["id"]
    assert second["similarity"] is not None and second["similarity"] > 0.85
    # The second note was rejected as a near-duplicate; the store stays at 1.
    assert _semantic_count(soul) == 1


# --- MERGE path --------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_path_supersedes_old_memory():
    """Enriched superset content lands in the MERGE band (0.6-0.85)."""
    soul = await Soul.birth("Aria", archetype="t")

    first = await soul.note("Aria likes Python")
    assert first["action"] == "CREATE"
    old_id = first["id"]

    second = await soul.note("Aria likes Python and async code")

    assert second["action"] == "MERGE"
    assert second["id"] is not None
    assert second["id"] != old_id
    assert second["existing_id"] == old_id
    sim = second["similarity"]
    assert sim is not None and 0.6 <= sim <= 0.85, f"Expected MERGE band similarity, got {sim}"

    # The old memory should be marked as superseded by the new one.
    all_facts = soul._memory._semantic.facts(include_superseded=True)
    old_entry = next(f for f in all_facts if f.id == old_id)
    assert old_entry.superseded_by == second["id"]

    # Default facts() filter excludes superseded — only the new entry shows.
    visible = soul._memory._semantic.facts()
    assert len(visible) == 1
    assert visible[0].id == second["id"]


# --- dedup=False opt-out -----------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_false_writes_both_copies():
    """dedup=False bypasses reconcile_fact; both notes land as CREATE."""
    soul = await Soul.birth("Aria", archetype="t")

    first = await soul.note("identical fact text", dedup=False)
    second = await soul.note("identical fact text", dedup=False)

    assert first["action"] == "CREATE"
    assert second["action"] == "CREATE"
    assert first["id"] != second["id"]
    assert _semantic_count(soul) == 2


# --- Episodic skips dedup ----------------------------------------------------


@pytest.mark.asyncio
async def test_episodic_always_creates_even_with_default_dedup():
    """Episodic memories are unique by time; dedup never applies."""
    soul = await Soul.birth("Aria", archetype="t")

    first = await soul.note("event happened", type=MemoryType.EPISODIC)
    second = await soul.note("event happened", type=MemoryType.EPISODIC)

    assert first["action"] == "CREATE"
    assert second["action"] == "CREATE"
    assert first["id"] != second["id"]
    # Both episodic entries land in the episodic store.
    assert len(soul._memory._episodic.entries()) == 2


# --- Domain isolation in dedup -----------------------------------------------


@pytest.mark.asyncio
async def test_dedup_is_scoped_per_domain_when_non_default():
    """Non-default domains dedup against entries in the same domain only."""
    soul = await Soul.birth("Aria", archetype="t")

    work = await soul.note("identical fact text", domain="work")
    personal = await soul.note("identical fact text", domain="personal")

    assert work["action"] == "CREATE"
    assert personal["action"] == "CREATE"
    assert work["id"] != personal["id"]
    # Both stored — different domains do not collide.
    assert _semantic_count(soul) == 2


@pytest.mark.asyncio
async def test_dedup_within_same_non_default_domain_still_skips():
    """Non-default domain still dedups within itself."""
    soul = await Soul.birth("Aria", archetype="t")

    first = await soul.note("identical fact text", domain="work")
    second = await soul.note("identical fact text", domain="work")

    assert first["action"] == "CREATE"
    assert second["action"] == "SKIP"
    assert second["existing_id"] == first["id"]
    assert _semantic_count(soul) == 1


# --- Procedural tier dedup ---------------------------------------------------


@pytest.mark.asyncio
async def test_procedural_tier_dedup_works():
    """Procedural store goes through the same SKIP path as semantic."""
    soul = await Soul.birth("Aria", archetype="t")

    first = await soul.note("to deploy run make deploy and verify", type=MemoryType.PROCEDURAL)
    second = await soul.note("to deploy run make deploy and verify", type=MemoryType.PROCEDURAL)

    assert first["action"] == "CREATE"
    assert second["action"] == "SKIP"
    assert second["existing_id"] == first["id"]
    assert _procedural_count(soul) == 1


# --- Return-shape contract across paths --------------------------------------


@pytest.mark.asyncio
async def test_return_shape_complete_across_all_paths():
    """All four keys present and correctly populated on CREATE / SKIP / MERGE."""
    soul = await Soul.birth("Aria", archetype="t")

    create_result = await soul.note("Aria enjoys playing guitar")
    skip_result = await soul.note("Aria enjoys playing guitar")
    merge_result = await soul.note("Bob writes essays about typography")
    merge_result_2 = await soul.note("Bob writes essays about typography and design")

    for result in (create_result, skip_result, merge_result, merge_result_2):
        assert set(result.keys()) == {"action", "id", "existing_id", "similarity"}

    # CREATE — id present, existing_id and similarity None.
    assert create_result["action"] == "CREATE"
    assert create_result["id"] is not None
    assert create_result["existing_id"] is None
    assert create_result["similarity"] is None

    # SKIP — id None, existing_id present, similarity > 0.85.
    assert skip_result["action"] == "SKIP"
    assert skip_result["id"] is None
    assert skip_result["existing_id"] == create_result["id"]
    assert skip_result["similarity"] is not None
    assert skip_result["similarity"] > 0.85

    # MERGE — id present (the new entry), existing_id present (the old one),
    # similarity in the MERGE band.
    assert merge_result_2["action"] == "MERGE"
    assert merge_result_2["id"] is not None
    assert merge_result_2["existing_id"] == merge_result["id"]
    assert merge_result_2["similarity"] is not None
    assert 0.6 <= merge_result_2["similarity"] <= 0.85
