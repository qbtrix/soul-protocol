# tests/test_memory_layers/test_auto_observe_middleware.py — Auto-capture turns.
# Created: 2026-05 — Verifies AutoObserveMiddleware wraps a Soul so a single
# turn() call performs optional auto-recall plus mandatory auto-observe,
# without the caller remembering to call Soul.observe() themselves.
# Updated: 2026-10 (#320 review) — Tests use the public Soul API
# (remember/recall) instead of soul._memory. Added coverage that user_id and
# domain reach both the recall and the observe half of turn(), and that
# memory_to_dict() is the shape turn() returns.

from __future__ import annotations

import pytest

from soul_protocol.runtime.middleware import AutoObserveMiddleware, memory_to_dict
from soul_protocol.runtime.soul import Soul


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
    await soul.remember("The user's favorite language is Python", importance=8)
    mw = AutoObserveMiddleware(soul)
    result = await mw.turn(
        "What's my favorite language?", "You like Python.", query="favorite language"
    )
    assert result["recalled"] >= 1
    assert result["recalled"] == len(result["memories"])
    assert any("language" in m["content"].lower() for m in result["memories"])


@pytest.mark.asyncio
async def test_turn_memories_use_shared_shape(soul):
    await soul.remember("The user's favorite language is Python", importance=8)
    expected = [memory_to_dict(r) for r in await soul.recall("favorite language", limit=5)]
    result = await AutoObserveMiddleware(soul).turn(
        "What's my favorite language?", query="favorite language"
    )
    assert result["memories"] == expected


@pytest.mark.asyncio
async def test_turn_writes_a_memory(soul):
    mw = AutoObserveMiddleware(soul)
    # "my name is X" hits a deterministic heuristic FACT_PATTERN, avoiding
    # any dependency on LLM-driven extraction in this unit test.
    await mw.turn("my name is Alex", "Hi Alex.")
    assert await soul.recall("Alex", limit=10), "expected observe to store a memory"


@pytest.mark.asyncio
async def test_turn_user_id_and_domain_scope_recall(soul):
    await soul.remember("alice finance tea budget", user_id="alice", domain="finance")
    await soul.remember("bob finance tea budget", user_id="bob", domain="finance")
    await soul.remember("alice legal tea contract", user_id="alice", domain="legal")

    result = await AutoObserveMiddleware(soul).turn(
        "tea?", query="tea", user_id="alice", domain="finance"
    )

    assert result["user_id"] == "alice"
    assert result["recalled"] >= 1
    for m in result["memories"]:
        assert m["user_id"] == "alice"
        assert m["domain"] == "finance"
    assert any("alice finance tea" in m["content"] for m in result["memories"])


@pytest.mark.asyncio
async def test_turn_user_id_and_domain_scope_observe(soul):
    await AutoObserveMiddleware(soul).turn(
        "my name is Alex", "Hi Alex.", user_id="alice", domain="finance"
    )

    written = await soul.recall("Alex", limit=10, user_id="alice", domain="finance")
    assert written, "observed turn should be stored under user_id=alice, domain=finance"
    for r in written:
        assert r.user_id == "alice"
        assert r.domain == "finance"

    # Nothing from the turn leaked into the default domain.
    assert await soul.recall("Alex", limit=10, domain="default") == []


@pytest.mark.asyncio
async def test_turn_without_domain_stores_in_default(soul):
    await AutoObserveMiddleware(soul).turn("my name is Alex", "Hi Alex.")
    written = await soul.recall("Alex", limit=10, domain="default")
    assert written
    assert all((r.domain or "default") == "default" for r in written)
