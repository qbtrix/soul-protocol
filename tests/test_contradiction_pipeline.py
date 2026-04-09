# tests/test_contradiction_pipeline.py — End-to-end contradiction detection across observe() sessions.
# Created: fix/contradiction-pipeline — Tests that reproduce the bug where contradiction detection
#   fires in isolation but does NOT fire during observe() when a new session fact contradicts a
#   semantic fact stored in a previous session (e.g., location or employer changes).

"""Tests for end-to-end contradiction detection across observe() sessions."""

import pytest

from soul_protocol.runtime.types import Interaction


@pytest.mark.asyncio
async def test_location_contradiction_across_sessions(tmp_path):
    """NYC → Amsterdam: moving should supersede the old location fact."""
    from soul_protocol import Soul

    soul = await Soul.birth(name="TestSoul", soul_dir=str(tmp_path))

    # Session 1: establish location
    await soul.observe(
        Interaction(
            user_input="I live in NYC. I work at a startup called TechCorp.",
            agent_output="Great! NYC is exciting.",
        )
    )

    # Session 2: update location
    await soul.observe(
        Interaction(
            user_input="I moved to Amsterdam last week. Starting at Stripe.",
            agent_output="Amsterdam is wonderful!",
        )
    )

    # SemanticStore.facts(include_superseded=True) exposes all facts including
    # superseded ones so we can assert the old fact was properly retired.
    semantics = soul._memory._semantic.facts(include_superseded=True)
    nyc_facts = [
        f for f in semantics if "nyc" in f.content.lower() and "lives" in f.content.lower()
    ]
    amsterdam_facts = [f for f in semantics if "amsterdam" in f.content.lower()]

    # Amsterdam should exist
    assert len(amsterdam_facts) > 0, "Amsterdam location not stored at all"

    # NYC fact should be superseded (superseded_by set to the new fact's id)
    active_nyc = [f for f in nyc_facts if f.superseded_by is None and not f.superseded]
    assert len(active_nyc) == 0, (
        f"Old NYC location still active after move to Amsterdam. "
        f"Active NYC facts: {[f.content for f in active_nyc]}"
    )


@pytest.mark.asyncio
async def test_employer_contradiction_across_sessions(tmp_path):
    """TechCorp → Stripe: job change should supersede old employer fact."""
    from soul_protocol import Soul

    soul = await Soul.birth(name="TestSoul", soul_dir=str(tmp_path))

    await soul.observe(
        Interaction(
            user_input="I work at TechCorp as a backend engineer.",
            agent_output="Cool!",
        )
    )
    await soul.observe(
        Interaction(
            user_input="I just joined Stripe! Starting next week.",
            agent_output="Congrats!",
        )
    )

    semantics = soul._memory._semantic.facts(include_superseded=True)
    techcorp_facts = [f for f in semantics if "techcorp" in f.content.lower()]
    stripe_facts = [f for f in semantics if "stripe" in f.content.lower()]

    assert len(stripe_facts) > 0, "Stripe employer not stored"
    active_techcorp = [f for f in techcorp_facts if f.superseded_by is None and not f.superseded]
    assert len(active_techcorp) == 0, (
        f"Old TechCorp employer still active. Facts: {[f.content for f in active_techcorp]}"
    )


@pytest.mark.asyncio
async def test_contradiction_detection_returns_results(tmp_path):
    """ContradictionDetector.detect_heuristic() should return results for verb-fact conflicts."""
    import uuid

    from soul_protocol.runtime.memory.contradiction import ContradictionDetector
    from soul_protocol.runtime.types import MemoryEntry, MemoryType

    detector = ContradictionDetector()
    existing = [
        MemoryEntry(
            id=str(uuid.uuid4()),
            type=MemoryType.SEMANTIC,
            content="User lives in NYC",
            importance=8,
        )
    ]

    results = await detector.detect_heuristic("User moved to Amsterdam", existing)
    assert len(results) > 0, (
        "Verb-fact contradiction 'lives in NYC' vs 'moved to Amsterdam' not detected"
    )
    assert results[0].is_contradiction


@pytest.mark.asyncio
async def test_non_contradiction_not_flagged(tmp_path):
    """Unrelated facts should not be flagged as contradictions."""
    import uuid

    from soul_protocol.runtime.memory.contradiction import ContradictionDetector
    from soul_protocol.runtime.types import MemoryEntry, MemoryType

    detector = ContradictionDetector()
    existing = [
        MemoryEntry(
            id=str(uuid.uuid4()),
            type=MemoryType.SEMANTIC,
            content="User likes Python",
            importance=6,
        )
    ]

    results = await detector.detect_heuristic("User moved to Amsterdam", existing)
    assert len(results) == 0, "Unrelated facts incorrectly flagged as contradiction"
