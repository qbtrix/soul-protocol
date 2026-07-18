# tests/test_observe/test_entity_extraction_independence.py
# Created: 2026-04-30 (#220) — Regression tests proving entity extraction
# runs on low-significance interactions (so the graph keeps growing under
# daily chitchat) while the self-model update stays gated. Discovered by
# the graph-traversal agent during PR #219 implementation: with the v0.4.x
# behaviour the graph plateaus quickly because every chitchat dropped
# entity extraction along with the self-model update.

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction, MemorySettings


def _interaction(text: str) -> Interaction:
    return Interaction(
        user_input=text,
        agent_output="ok",
        timestamp=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_entity_extraction_runs_on_low_significance_by_default():
    """#220: trivial chitchat that mentions an entity should still grow the graph.

    Uses heuristic extraction (no engine) — the heuristic recognizes
    capitalized proper nouns. Without the #220 fix, low-significance
    interactions short-circuit before extraction and the entity never
    lands in the graph.
    """
    soul = await Soul.birth("Test", archetype="t")

    # Trivial chitchat (won't pass the LIDA significance gate) that mentions
    # a capitalized proper noun the heuristic extractor will pick up.
    for _ in range(3):
        await soul.observe(_interaction("hi, how is Alice doing?"))

    # Default behaviour (always_extract_entities=True) — Alice should be
    # in the graph despite the interactions being below the significance gate.
    nodes = soul.graph.nodes()
    names = {n.name for n in nodes}
    assert "Alice" in names, (
        f"Expected 'Alice' in graph after low-significance chitchat, got {names}"
    )


@pytest.mark.asyncio
async def test_always_extract_entities_field_present_on_settings():
    """The new MemorySettings flag exists and defaults to True.

    The end-to-end "legacy plateau" assertion is hard to write deterministically
    because fact-based promotion in step 4b can flip ``significant`` to True
    even on chitchat that mentions a name. This test pins down the field
    contract instead.
    """
    settings = MemorySettings()
    assert settings.always_extract_entities is True

    settings_off = MemorySettings(always_extract_entities=False)
    assert settings_off.always_extract_entities is False


@pytest.mark.asyncio
async def test_entity_extraction_independent_of_self_model_gate():
    """Both gates are independent — turning the significance short-circuit
    off entirely lets entity extraction AND self-model run unconditionally.
    """
    soul = await Soul.birth(
        "Test",
        archetype="t",
        memory_settings=MemorySettings(skip_deep_processing_on_low_significance=False),
    )

    for _ in range(2):
        await soul.observe(_interaction("hi, how is Bob doing?"))

    nodes = soul.graph.nodes()
    names = {n.name for n in nodes}
    assert "Bob" in names
