# test_episodic_verbatim.py — Regression tests for #234.
#
# Plain episodic writes via Soul.remember / Soul.note must store content
# verbatim. The User:/Agent: envelope is reserved for soul.observe() with
# real Interaction inputs.
#
# Created: 2026-05-13 (#234).

import pytest

from soul_protocol.runtime.memory.episodic import EpisodicStore
from soul_protocol.runtime.memory.manager import MemoryManager
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import (
    CoreMemory,
    Interaction,
    MemoryEntry,
    MemorySettings,
    MemoryType,
)


@pytest.mark.asyncio
async def test_soul_remember_episodic_stores_content_verbatim():
    """Soul.remember(plain_text, type=EPISODIC) must not wrap in User:/Agent:."""
    soul = await Soul.birth("Test")
    new_id = await soul.remember("TEST: plain text", type=MemoryType.EPISODIC)

    entry = soul._memory._episodic._memories[new_id]
    assert entry.content == "TEST: plain text"
    assert "User:" not in entry.content
    assert "Agent:" not in entry.content


@pytest.mark.asyncio
async def test_soul_note_episodic_stores_content_verbatim():
    """Soul.note(plain_text, type=EPISODIC) must not wrap in User:/Agent:.

    Episodic bypasses dedup and falls through to remember(), which now
    stores verbatim via EpisodicStore.add_entry().
    """
    soul = await Soul.birth("Test")
    result = await soul.note("TEST: plain text", type=MemoryType.EPISODIC)

    assert result["action"] == "CREATE"
    entry = soul._memory._episodic._memories[result["id"]]
    assert entry.content == "TEST: plain text"
    assert "User:" not in entry.content
    assert "Agent:" not in entry.content


@pytest.mark.asyncio
async def test_episodic_store_add_via_interaction_still_uses_envelope():
    """EpisodicStore.add(Interaction) — the observe pipeline's write path —
    must keep producing the User:/Agent: envelope. The envelope is correct
    when the caller actually has user_input and agent_output to record."""
    store = EpisodicStore()
    new_id = await store.add(
        Interaction(user_input="hello there", agent_output="hi back"),
    )

    assert store._memories[new_id].content == "User: hello there\nAgent: hi back"


@pytest.mark.asyncio
async def test_episodic_store_add_entry_preserves_id_and_content():
    """EpisodicStore.add_entry stores a pre-formed entry verbatim and
    preserves an explicit id if the caller provided one."""
    store = EpisodicStore()
    entry = MemoryEntry(
        id="abc123",
        type=MemoryType.EPISODIC,
        content="plain payload, no envelope",
        importance=7,
    )

    new_id = await store.add_entry(entry)

    assert new_id == "abc123"
    assert store._memories["abc123"].content == "plain payload, no envelope"
    assert store._memories["abc123"].importance == 7


@pytest.mark.asyncio
async def test_episodic_store_add_entry_assigns_id_if_missing():
    """EpisodicStore.add_entry generates an id when entry.id is falsy."""
    store = EpisodicStore()
    entry = MemoryEntry(
        id="",
        type=MemoryType.EPISODIC,
        content="payload",
    )

    new_id = await store.add_entry(entry)

    assert new_id
    assert len(new_id) == 12  # uuid4().hex[:12]
    assert store._memories[new_id].content == "payload"


@pytest.mark.asyncio
async def test_memory_manager_add_episodic_propagates_domain():
    """MemoryManager.add() routes episodic entries through add_entry()
    and the entry's domain field survives the write."""
    manager = MemoryManager(core=CoreMemory(), settings=MemorySettings())
    entry = MemoryEntry(
        id="",
        type=MemoryType.EPISODIC,
        content="domain-scoped event",
        domain="finance",
    )

    new_id = await manager.add(entry)

    stored = manager._episodic._memories[new_id]
    assert stored.content == "domain-scoped event"
    assert stored.domain == "finance"
