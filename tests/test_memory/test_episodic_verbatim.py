# test_episodic_verbatim.py — Regression tests for issue #234 and its sibling.
# Created: 2026-05-29 — Asserts that episodic writes via Soul.remember/Soul.note
#   store content VERBATIM (no "User: ...\nAgent: " envelope), preserve the
#   caller's importance (not hardcoded to 5), and keep emotion/entities/user_id.
#   Includes regression guards proving semantic stays verbatim and that the
#   observe pipeline STILL produces the intentional "User: ...\nAgent: ..."
#   envelope from a real user/agent interaction.

from __future__ import annotations

import pytest

from soul_protocol.runtime.memory.manager import MemoryManager
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import (
    CoreMemory,
    Interaction,
    MemorySettings,
    MemoryType,
)


@pytest.fixture
async def soul() -> Soul:
    """A freshly birthed soul for exercising the public memory API."""
    return await Soul.birth("Aria", archetype="The Compassionate Creator")


def _episodic_entries(soul: Soul) -> list:
    """Return all stored episodic MemoryEntry objects from the soul."""
    return soul._memory._episodic.entries()


# ---------------------------------------------------------------------------
# Bug #234 — episodic remember must store content VERBATIM (no envelope)
# ---------------------------------------------------------------------------


async def test_episodic_remember_stores_content_verbatim(soul: Soul):
    """An episodic remember stores the input string exactly, with no
    "User: " prefix and no trailing "\\nAgent: " suffix (#234)."""
    text = "Shipped the verbatim-episodic fix today"
    mem_id = await soul.remember(text, type=MemoryType.EPISODIC, importance=8)

    entry = await soul._memory._episodic.get(mem_id)
    assert entry is not None
    assert entry.content == text
    assert "User: " not in entry.content
    assert "\nAgent: " not in entry.content


async def test_episodic_remember_preserves_importance(soul: Soul):
    """An episodic remember with importance=8 stores importance == 8,
    not the hardcoded 5 from EpisodicStore.add() (sibling bug)."""
    mem_id = await soul.remember("A high-importance event", type=MemoryType.EPISODIC, importance=8)

    entry = await soul._memory._episodic.get(mem_id)
    assert entry is not None
    assert entry.importance == 8


async def test_episodic_remember_preserves_emotion_entities_user_id(soul: Soul):
    """An episodic remember preserves emotion, entities, and user_id —
    all silently dropped by the Interaction round-trip today."""
    mem_id = await soul.remember(
        "Met Alice at the conference",
        type=MemoryType.EPISODIC,
        importance=7,
        emotion="joy",
        entities=["Alice", "conference"],
        user_id="user-42",
    )

    entry = await soul._memory._episodic.get(mem_id)
    assert entry is not None
    assert entry.emotion == "joy"
    assert entry.entities == ["Alice", "conference"]
    assert entry.user_id == "user-42"


async def test_episodic_note_stores_content_verbatim(soul: Soul):
    """Soul.note() for episodic shares the remember() path, so it must
    also store content verbatim with no envelope and the right importance."""
    text = "Logged a unique timestamped event"
    result = await soul.note(text, type=MemoryType.EPISODIC, importance=9)
    mem_id = result["id"]

    entry = await soul._memory._episodic.get(mem_id)
    assert entry is not None
    assert entry.content == text
    assert "User: " not in entry.content
    assert "\nAgent: " not in entry.content
    assert entry.importance == 9


# ---------------------------------------------------------------------------
# Regression guards — must stay green before AND after the fix
# ---------------------------------------------------------------------------


async def test_semantic_remember_stays_verbatim(soul: Soul):
    """Semantic remember already stores verbatim — guard against the fix
    accidentally regressing the non-episodic branches."""
    text = "User prefers Python over JavaScript"
    mem_id = await soul.remember(text, type=MemoryType.SEMANTIC, importance=8)

    entry = await soul._memory._semantic.get(mem_id)
    assert entry is not None
    assert entry.content == text
    assert entry.importance == 8


async def test_observe_still_builds_user_agent_envelope():
    """observe() intentionally wraps a real user/agent pair into the
    "User: ...\\nAgent: ..." envelope. The fix must NOT break this — only
    the blunt episodic remember() path should change.

    This drives the episodic store directly through add_with_psychology
    (the path observe uses) to assert the envelope is produced, with no
    LLM calls involved.
    """
    mgr = MemoryManager(core=CoreMemory(), settings=MemorySettings())
    interaction = Interaction(
        user_input="What is the weather?",
        agent_output="It's sunny today!",
    )
    mem_id = await mgr._episodic.add_with_psychology(interaction)

    entry = await mgr._episodic.get(mem_id)
    assert entry is not None
    assert entry.content == "User: What is the weather?\nAgent: It's sunny today!"
    assert entry.content.startswith("User: ")
    assert "\nAgent: " in entry.content


async def test_episodic_store_add_interaction_keeps_envelope():
    """EpisodicStore.add(interaction) is the legacy envelope builder used by
    add_episodic/observe. It must remain unchanged by the fix."""
    mgr = MemoryManager(core=CoreMemory(), settings=MemorySettings())
    mem_id = await mgr.add_episodic(
        Interaction(user_input="I need coffee", agent_output="Let me help!")
    )
    entry = await mgr._episodic.get(mem_id)
    assert entry is not None
    assert entry.content == "User: I need coffee\nAgent: Let me help!"
