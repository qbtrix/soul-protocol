# tests/test_memory_layers/test_auto_observe_middleware.py — Auto-capture turns.
# Created: 2026-05 — Verifies AutoObserveMiddleware wraps a Soul so a single
# turn() call performs optional auto-recall plus mandatory auto-observe,
# without the caller remembering to call Soul.observe() themselves.

from __future__ import annotations

import pytest

from soul_protocol.runtime.middleware import AutoObserveMiddleware
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryEntry, MemoryType


@pytest.fixture
async def soul() -> Soul:
    return await Soul.birth(name="Auto", archetype="auto observe test")


@pytest.mark.asyncio
async def test_turn_observes_without_query(soul):
    mw = AutoObserveMiddleware(soul)
    result = await mw.turn("I love Python", "Python is great!")
    assert result["soul"] == "Auto"
    assert result["recalled"] == 0
    assert result["memories"] == []
    assert "mood" in result
    assert "energy" in result


@pytest.mark.asyncio
async def test_turn_recalls_when_query_provided(soul):
    await soul._memory.add(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="The user's favorite language is Python",
            importance=8,
            domain="default",
        )
    )
    mw = AutoObserveMiddleware(soul)
    result = await mw.turn(
        "What's my favorite language?", "You like Python.", query="favorite language"
    )
    assert result["recalled"] >= 1
    assert isinstance(result["memories"], list)
    assert any("language" in m["content"].lower() for m in result["memories"])


@pytest.mark.asyncio
async def test_turn_writes_a_memory(soul):
    mw = AutoObserveMiddleware(soul)
    # "my name is X" hits a deterministic heuristic FACT_PATTERN, avoiding
    # any dependency on LLM-driven extraction in this unit test.
    await mw.turn("my name is Alex", "Hi Alex.")
    facts = soul._memory._semantic.facts()
    epi = soul._memory._episodic.entries()
    assert facts or epi, "expected observe to store at least one memory"
