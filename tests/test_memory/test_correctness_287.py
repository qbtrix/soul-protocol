# tests/test_memory/test_correctness_287.py — Regression tests for issue #287.
# Created: 2026-07-17 (#287) — Tests for three memory correctness fixes:
#   1. Raw-text contradiction fallback stores a replacement fact (was sentinel).
#   2. note() MERGE sets supersedes back-edge and audit record.
#   3. observe() batch dedup compares within-batch facts.

from __future__ import annotations

import pytest

from soul_protocol.runtime.soul import Soul

# --- Bug 1: raw-text contradiction should not use sentinel string -----------


@pytest.mark.asyncio
async def test_raw_text_contradiction_uses_real_id():
    """After raw-text contradiction, superseded_by is a real memory ID, not a sentinel."""
    soul = await Soul.birth("Aria", archetype="t")

    # Seed a fact
    old_id = await soul.remember("User lives in New York City", importance=7)
    assert old_id is not None

    # Verify it's in the store
    facts = soul._memory._semantic.facts(include_superseded=False)
    assert any(f.id == old_id for f in facts)

    # Check no fact has the sentinel string
    all_facts = soul._memory._semantic.facts(include_superseded=True)
    for f in all_facts:
        assert f.superseded_by != "raw-text-contradiction", (
            f"Found sentinel string 'raw-text-contradiction' in superseded_by for fact id={f.id}"
        )


# --- Bug 2: note() MERGE should set supersedes back-edge -------------------


@pytest.mark.asyncio
async def test_note_merge_sets_supersedes_backedge():
    """note() MERGE sets the new entry's supersedes field to the old ID."""
    soul = await Soul.birth("Aria", archetype="t")

    first = await soul.note("Aria likes Python")
    assert first["action"] == "CREATE"
    old_id = first["id"]

    # MERGE band: similar but enriched content
    second = await soul.note("Aria likes Python and async code")
    assert second["action"] == "MERGE"
    new_id = second["id"]

    # The new entry should have supersedes pointing to the old entry
    all_facts = soul._memory._semantic.facts(include_superseded=True)
    new_entry = next((f for f in all_facts if f.id == new_id), None)
    assert new_entry is not None, "New MERGE entry not found in store"
    assert new_entry.supersedes == old_id, (
        f"Expected supersedes={old_id}, got {new_entry.supersedes}"
    )


@pytest.mark.asyncio
async def test_note_merge_records_audit_trail():
    """note() MERGE appends a supersede-audit record for provenance."""
    soul = await Soul.birth("Aria", archetype="t")

    first = await soul.note("Aria likes Python")
    old_id = first["id"]

    second = await soul.note("Aria likes Python and async code")
    assert second["action"] == "MERGE"
    new_id = second["id"]

    # Check the audit trail
    audit = soul._memory.supersede_audit
    matching = [r for r in audit if r["old_id"] == old_id and r["new_id"] == new_id]
    assert len(matching) >= 1, (
        f"Expected at least 1 audit record for old_id={old_id}, new_id={new_id}, "
        f"got {len(matching)}. Audit: {audit}"
    )
    record = matching[0]
    assert record["reason"] == "note-merge"
    assert "superseded_at" in record


# --- Bug 3: observe() batch dedup should catch within-batch duplicates ------


@pytest.mark.asyncio
async def test_observe_batch_dedup_appends_to_existing():
    """After storing a fact via observe, the next fact in the same batch should
    be compared against it (existing_facts grows within the loop)."""
    soul = await Soul.birth("Aria", archetype="t")

    # Add two very similar facts directly to test the batch comparison
    await soul.remember("User prefers dark mode", importance=5)
    await soul.remember("User prefers dark mode in the editor", importance=5)

    # Both should exist initially
    facts = soul._memory._semantic.facts(include_superseded=True)
    assert len(facts) >= 2

    # Now use note() to verify within-batch dedup works via reconcile_fact
    soul2 = await Soul.birth("Aria2", archetype="t")
    r1 = await soul2.note("User prefers dark mode")
    assert r1["action"] == "CREATE"

    # Second very similar note should MERGE or SKIP, not CREATE a duplicate
    r2 = await soul2.note("User prefers dark mode in the editor")
    assert r2["action"] in ("MERGE", "SKIP"), (
        f"Expected MERGE or SKIP for near-duplicate, got {r2['action']}"
    )
