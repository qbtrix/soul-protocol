# test_storage.py — Tests for storage backends (InMemoryStorage and FileStorage).
# Created: 2026-02-22 — Covers save/load/delete/list for both backends,
# using tmp_path for file-based tests.

from __future__ import annotations

import pytest

from soul_protocol.storage.file import FileStorage
from soul_protocol.storage.memory_store import InMemoryStorage
from soul_protocol.types import Identity, SoulConfig


@pytest.fixture
def config() -> SoulConfig:
    """Return a minimal SoulConfig for storage tests."""
    return SoulConfig(
        identity=Identity(name="Aria", did="did:soul:aria-abc123"),
    )


# ============ InMemoryStorage ============


async def test_in_memory_save_and_load(config: SoulConfig):
    """InMemoryStorage saves and loads a soul config."""
    store = InMemoryStorage()

    await store.save("aria", config)
    loaded = await store.load("aria")

    assert loaded is not None
    assert loaded.identity.name == "Aria"
    assert loaded.identity.did == "did:soul:aria-abc123"


async def test_in_memory_delete(config: SoulConfig):
    """InMemoryStorage delete removes a soul and returns True."""
    store = InMemoryStorage()

    await store.save("aria", config)
    result = await store.delete("aria")
    assert result is True

    loaded = await store.load("aria")
    assert loaded is None

    # Deleting non-existent returns False
    result2 = await store.delete("aria")
    assert result2 is False


async def test_in_memory_list(config: SoulConfig):
    """InMemoryStorage list_souls returns all saved IDs."""
    store = InMemoryStorage()

    await store.save("aria", config)

    config2 = SoulConfig(
        identity=Identity(name="Nova", did="did:soul:nova-xyz789"),
    )
    await store.save("nova", config2)

    souls = await store.list_souls()
    assert set(souls) == {"aria", "nova"}


# ============ FileStorage ============


async def test_file_storage_save_and_load(config: SoulConfig, tmp_path):
    """FileStorage saves files to disk and loads them back."""
    store = FileStorage(base_dir=tmp_path)

    await store.save("aria", config)

    # Verify directory structure
    soul_dir = tmp_path / "aria"
    assert soul_dir.exists()
    assert (soul_dir / "soul.json").exists()
    assert (soul_dir / "dna.md").exists()
    assert (soul_dir / "state.json").exists()

    loaded = await store.load("aria")
    assert loaded is not None
    assert loaded.identity.name == "Aria"
    assert loaded.identity.did == "did:soul:aria-abc123"


async def test_file_storage_delete(config: SoulConfig, tmp_path):
    """FileStorage delete removes the soul directory."""
    store = FileStorage(base_dir=tmp_path)

    await store.save("aria", config)
    result = await store.delete("aria")
    assert result is True
    assert not (tmp_path / "aria").exists()

    # Deleting non-existent returns False
    result2 = await store.delete("aria")
    assert result2 is False


async def test_file_storage_list(config: SoulConfig, tmp_path):
    """FileStorage list_souls returns all soul IDs on disk."""
    store = FileStorage(base_dir=tmp_path)

    await store.save("aria", config)

    config2 = SoulConfig(
        identity=Identity(name="Nova", did="did:soul:nova-xyz789"),
    )
    await store.save("nova", config2)

    souls = await store.list_souls()
    assert set(souls) == {"aria", "nova"}

    # Loading from non-existent returns None
    missing = await store.load("missing-soul")
    assert missing is None
