# examples/test_pocketpaw_integration.py — Tests for the SoulProvider PocketPaw
# integration reference implementation.
#
# Moved from tests/test_integrations/test_pocketpaw.py.
# Covers system prompt generation, memory recall injection, interaction tracking,
# status reporting, factory constructors, and auto-save.
#
# Run with: uv run pytest examples/test_pocketpaw_integration.py -v

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure the examples directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pocketpaw_integration import SoulProvider

from soul_protocol import LifecycleState, MemoryType, Mood, Soul


@pytest.fixture
async def soul() -> Soul:
    """Birth a fresh soul for each test."""
    return await Soul.birth("Aria", archetype="The Compassionate Creator")


@pytest.fixture
async def provider(soul: Soul) -> SoulProvider:
    """Create a SoulProvider wrapping the test soul."""
    return SoulProvider(soul)


async def test_soul_provider_system_prompt(provider: SoulProvider):
    """get_system_prompt() returns a prompt containing the soul's name."""
    prompt = await provider.get_system_prompt()

    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "Aria" in prompt


async def test_soul_provider_with_query(provider: SoulProvider):
    """get_system_prompt() with a query includes relevant memories section
    when matching memories exist."""
    # First, teach the soul something it can recall
    await provider.soul.remember(
        "User loves hiking in the mountains",
        type=MemoryType.SEMANTIC,
        importance=7,
    )

    prompt = await provider.get_system_prompt(user_query="hiking")

    assert "## Relevant Memories" in prompt
    assert "hiking" in prompt


async def test_soul_provider_with_query_no_matches(provider: SoulProvider):
    """get_system_prompt() with a query but no matching memories omits the section."""
    prompt = await provider.get_system_prompt(user_query="quantum physics")

    # No memories stored, so no memories section
    assert "## Relevant Memories" not in prompt


async def test_soul_provider_on_interaction(provider: SoulProvider):
    """on_interaction() causes the soul's state to change (energy drain)."""
    initial_energy = provider.soul.state.energy
    initial_social = provider.soul.state.social_battery

    await provider.on_interaction(
        user_input="Hello there!",
        agent_output="Hi! Nice to meet you.",
        channel="test",
    )

    assert provider.soul.state.energy < initial_energy
    assert provider.soul.state.social_battery < initial_social
    assert provider._interaction_count == 1


async def test_soul_provider_status(provider: SoulProvider):
    """get_soul_status() returns a dict with all expected keys."""
    status = await provider.get_soul_status()

    expected_keys = {
        "name",
        "did",
        "mood",
        "energy",
        "focus",
        "social_battery",
        "lifecycle",
        "interaction_count",
        "core_memory",
    }
    assert set(status.keys()) == expected_keys

    assert status["name"] == "Aria"
    assert status["mood"] == Mood.NEUTRAL.value
    assert status["energy"] == 100.0
    assert status["lifecycle"] == LifecycleState.ACTIVE.value
    assert status["interaction_count"] == 0

    # Core memory should have persona and human keys
    assert "persona" in status["core_memory"]
    assert "human" in status["core_memory"]


async def test_soul_provider_from_name():
    """from_name() births a soul with the given name and wraps it."""
    provider = await SoulProvider.from_name("Buddy", archetype="The Helper")

    assert provider.soul.name == "Buddy"
    assert provider.soul.archetype == "The Helper"
    assert provider.soul.lifecycle == LifecycleState.ACTIVE

    prompt = await provider.get_system_prompt()
    assert "Buddy" in prompt


async def test_soul_provider_from_name_defaults():
    """from_name() uses 'The Companion' as the default archetype."""
    provider = await SoulProvider.from_name("Echo")

    assert provider.soul.archetype == "The Companion"


async def test_soul_provider_auto_save(provider: SoulProvider):
    """save() is called automatically every N interactions (default 10)."""
    provider._auto_save_interval = 3  # Lower for testing

    with patch.object(provider._soul, "save", new_callable=AsyncMock) as mock_save:
        # Interactions 1 and 2 — no save
        await provider.on_interaction("msg1", "reply1")
        await provider.on_interaction("msg2", "reply2")
        mock_save.assert_not_called()

        # Interaction 3 — triggers save
        await provider.on_interaction("msg3", "reply3")
        mock_save.assert_awaited_once()

        mock_save.reset_mock()

        # Interactions 4 and 5 — no save
        await provider.on_interaction("msg4", "reply4")
        await provider.on_interaction("msg5", "reply5")
        mock_save.assert_not_called()

        # Interaction 6 — triggers save again
        await provider.on_interaction("msg6", "reply6")
        mock_save.assert_awaited_once()


async def test_soul_provider_low_energy_note(provider: SoulProvider):
    """get_system_prompt() appends a low-energy note when energy < 30."""
    # Drain energy below 30
    provider.soul.feel(energy=-75)
    assert provider.soul.state.energy < 30

    prompt = await provider.get_system_prompt()

    assert "low on energy" in prompt
    assert "concise" in prompt


async def test_soul_provider_recall_limit():
    """memory_recall_limit parameter controls max recalled memories."""
    provider = await SoulProvider.from_name("Aria", memory_recall_limit=2)

    assert provider._recall_limit == 2


async def test_soul_provider_from_file(tmp_path):
    """from_file() loads a soul from a .soul file and creates a provider."""
    # Create and export a soul
    soul = await Soul.birth("FileSoul", archetype="The Archivist")
    soul_path = tmp_path / "test.soul"
    await soul.export(str(soul_path))

    # Load via from_file
    provider = await SoulProvider.from_file(str(soul_path))

    assert provider.soul.name == "FileSoul"
    assert provider.soul.archetype == "The Archivist"


async def test_soul_provider_soul_property(provider: SoulProvider):
    """The soul property exposes the underlying Soul instance."""
    assert provider.soul is provider._soul
    assert isinstance(provider.soul, Soul)
