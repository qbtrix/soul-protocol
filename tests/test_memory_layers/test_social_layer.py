# tests/test_memory_layers/test_social_layer.py — SocialStore + manager.layer("social").
# Created: 2026-04-29 (#41) — Verifies the SocialStore works as a stand-alone
# store and that MemoryManager.layer("social") routes correctly. Round-trip
# through to_dict/from_dict preserves social entries.

from __future__ import annotations

import pytest

from soul_protocol.runtime.memory import MemoryManager, SocialStore
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import (
    CoreMemory,
    MemoryEntry,
    MemorySettings,
    MemoryType,
)


@pytest.mark.asyncio
async def test_social_store_basic_add_and_get():
    store = SocialStore()
    entry = MemoryEntry(
        type=MemoryType.SEMANTIC,
        content="Alice prefers async messages",
        importance=7,
    )
    sid = await store.add(entry)
    assert sid
    got = await store.get(sid)
    assert got is not None
    assert got.content == "Alice prefers async messages"
    assert got.type == MemoryType.SOCIAL
    assert got.layer == "social"


@pytest.mark.asyncio
async def test_social_store_search_relevance_ranks_results():
    store = SocialStore()
    await store.add(
        MemoryEntry(type=MemoryType.SEMANTIC, content="Alice trusts the team", importance=8)
    )
    await store.add(
        MemoryEntry(type=MemoryType.SEMANTIC, content="Bob distrusts vendors", importance=6)
    )
    results = await store.search("Alice")
    assert results
    assert results[0].content.startswith("Alice")


@pytest.mark.asyncio
async def test_manager_layer_social_returns_layer_view():
    manager = MemoryManager(core=CoreMemory(), settings=MemorySettings())
    view = manager.layer("social")
    assert view.name == "social"

    sid = await view.store(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="Carol responds best to short questions",
            importance=7,
        )
    )
    got = await view.get(sid)
    assert got is not None
    assert got.layer == "social"


@pytest.mark.asyncio
async def test_social_layer_round_trips_through_to_dict():
    soul = await Soul.birth(name="Trip", archetype="social round trip")
    view = soul._memory.layer("social")
    await view.store(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="Dee prefers in-person meetings",
            importance=8,
        )
    )

    dump = soul._memory.to_dict()
    assert "social" in dump
    assert any(e["content"] == "Dee prefers in-person meetings" for e in dump["social"])

    # Rebuild a manager from the dump and confirm round-trip.
    rebuilt = MemoryManager.from_dict(dump, settings=MemorySettings())
    rebuilt_view = rebuilt.layer("social")
    entries = rebuilt_view.entries()
    assert any(e.content == "Dee prefers in-person meetings" for e in entries)


@pytest.mark.asyncio
async def test_social_layer_appears_in_known_layers_after_write():
    manager = MemoryManager(core=CoreMemory(), settings=MemorySettings())
    assert "social" not in manager.known_layers()
    await manager.layer("social").store(
        MemoryEntry(type=MemoryType.SEMANTIC, content="x", importance=5)
    )
    assert "social" in manager.known_layers()


@pytest.mark.asyncio
async def test_social_view_count_and_entries():
    manager = MemoryManager(core=CoreMemory(), settings=MemorySettings())
    view = manager.layer("social")
    for content in ["one", "two", "three"]:
        await view.store(MemoryEntry(type=MemoryType.SEMANTIC, content=content, importance=5))
    assert view.count() == 3
    contents = {e.content for e in view.entries()}
    assert contents == {"one", "two", "three"}
