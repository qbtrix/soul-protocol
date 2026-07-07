# test_storage.py — Tests for storage backends (InMemoryStorage and FileStorage).
# Created: 2026-02-22 — Covers save/load/delete/list for both backends,
# using tmp_path for file-based tests.

from __future__ import annotations

from pathlib import Path

import pytest

from soul_protocol.runtime.storage import file as storage_file
from soul_protocol.runtime.storage.file import FileStorage
from soul_protocol.runtime.storage.memory_store import InMemoryStorage
from soul_protocol.runtime.types import Identity, SoulConfig


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


async def test_save_soul_full_restores_previous_directory_on_replace_failure(
    config: SoulConfig,
    tmp_path,
    monkeypatch,
):
    """A failed final replacement leaves the previous full save readable."""
    await storage_file.save_soul_full(config, {"core": {"persona": "old"}}, path=tmp_path)

    soul_dir = tmp_path / "did_soul_aria-abc123"
    sentinel = soul_dir / "sentinel.txt"
    sentinel.write_text("old copy", encoding="utf-8")

    real_replace = storage_file.os.replace

    def fail_final_replace(src, dst):
        if Path(dst) == soul_dir and Path(src).name == soul_dir.name:
            raise OSError("simulated replace failure")
        return real_replace(src, dst)

    monkeypatch.setattr(storage_file.os, "replace", fail_final_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        await storage_file.save_soul_full(config, {"core": {"persona": "new"}}, path=tmp_path)

    assert sentinel.read_text(encoding="utf-8") == "old copy"
    assert soul_dir.exists()
    assert not (tmp_path / "did_soul_aria-abc123.bak").exists()


async def test_save_soul_flat_restores_previous_directory_on_replace_failure(
    config: SoulConfig,
    tmp_path,
    monkeypatch,
):
    """A failed final replacement leaves the previous flat save readable."""
    soul_dir = tmp_path / ".soul"
    await storage_file.save_soul_flat(config, {"core": {"persona": "old"}}, soul_dir)

    sentinel = soul_dir / "sentinel.txt"
    sentinel.write_text("old copy", encoding="utf-8")

    real_replace = storage_file.os.replace

    def fail_final_replace(src, dst):
        if Path(dst) == soul_dir and Path(src).name == soul_dir.name:
            raise OSError("simulated replace failure")
        return real_replace(src, dst)

    monkeypatch.setattr(storage_file.os, "replace", fail_final_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        await storage_file.save_soul_flat(config, {"core": {"persona": "new"}}, soul_dir)

    assert sentinel.read_text(encoding="utf-8") == "old copy"
    assert soul_dir.exists()
    assert not (tmp_path / ".soul.bak").exists()


def test_write_bytes_atomic_cleans_temp_on_write_failure(tmp_path, monkeypatch):
    """If the write itself fails, no temp file is left behind."""
    target = tmp_path / "test.soul"

    def exploding_fdopen(fd, mode):
        # Close the fd so it doesn't leak, then raise
        storage_file.os.close(fd)
        raise OSError("simulated disk full")

    monkeypatch.setattr(storage_file.os, "fdopen", exploding_fdopen)

    with pytest.raises(OSError, match="simulated disk full"):
        storage_file.write_bytes_atomic(target, b"data")

    # No temp files should remain
    leftover = [p for p in tmp_path.iterdir() if ".tmp" in p.name]
    assert leftover == [], f"Temp files left behind: {leftover}"
    assert not target.exists()


async def test_save_soul_full_first_time_creates_no_backup(
    config: SoulConfig,
    tmp_path,
):
    """First-time save (no pre-existing target) creates the directory with no .bak."""
    await storage_file.save_soul_full(config, {"core": {"persona": "v1"}}, path=tmp_path)

    soul_dir = tmp_path / "did_soul_aria-abc123"
    assert soul_dir.exists()
    assert (soul_dir / "soul.json").exists()

    # No backup should exist on first save
    bak_dir = tmp_path / "did_soul_aria-abc123.bak"
    assert not bak_dir.exists()


def test_write_bytes_atomic_overwrites_stale_backup(tmp_path):
    """A stale .bak from a previous run is replaced on the next write."""
    target = tmp_path / "test.dat"
    bak = tmp_path / "test.dat.bak"

    # Simulate a stale backup from a previous crash
    bak.write_bytes(b"stale backup")
    target.write_bytes(b"current")

    storage_file.write_bytes_atomic(target, b"new data")

    assert target.read_bytes() == b"new data"
    # .bak should now contain the previous "current", not "stale backup"
    assert bak.read_bytes() == b"current"
