# test_bug_15_core_memory.py — Regression test for Bug #15: edit_core_memory
# appends instead of replacing. Verifies that editing core memory replaces
# the value rather than appending to it.

from __future__ import annotations

import pytest

from soul_protocol.soul import Soul


@pytest.mark.asyncio
async def test_edit_core_memory_replaces_persona():
    """Bug #15: edit_core_memory should replace, not append."""
    soul = await Soul.birth("TestSoul", personality="I am helpful")

    # Core memory persona should be the initial value
    assert soul.get_core_memory().persona == "I am helpful"

    # Edit the persona — this should REPLACE, not append
    await soul.edit_core_memory(persona="I am creative")

    assert soul.get_core_memory().persona == "I am creative"


@pytest.mark.asyncio
async def test_edit_core_memory_replaces_human():
    """Bug #15: edit_core_memory should replace human field too."""
    soul = await Soul.birth("TestSoul")

    await soul.edit_core_memory(human="Alice, a developer")
    assert soul.get_core_memory().human == "Alice, a developer"

    await soul.edit_core_memory(human="Bob, a designer")
    assert soul.get_core_memory().human == "Bob, a designer"


@pytest.mark.asyncio
async def test_edit_core_memory_partial_update():
    """Editing only persona should not touch human, and vice versa."""
    soul = await Soul.birth("TestSoul", personality="I am helpful")
    await soul.edit_core_memory(human="Alice")

    # Edit only persona
    await soul.edit_core_memory(persona="I am creative")
    assert soul.get_core_memory().persona == "I am creative"
    assert soul.get_core_memory().human == "Alice"

    # Edit only human
    await soul.edit_core_memory(human="Bob")
    assert soul.get_core_memory().persona == "I am creative"
    assert soul.get_core_memory().human == "Bob"


@pytest.mark.asyncio
async def test_edit_core_memory_does_not_append():
    """Explicitly verify the old append behavior is gone."""
    soul = await Soul.birth("TestSoul", personality="First")

    await soul.edit_core_memory(persona="Second")

    # Must NOT contain the old value concatenated
    assert "First" not in soul.get_core_memory().persona
    assert soul.get_core_memory().persona == "Second"
