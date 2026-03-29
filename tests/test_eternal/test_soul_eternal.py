# tests/test_eternal/test_soul_eternal.py — Tests for Soul + eternal storage (F4)
# Created: 2026-03-29 — Verifies Soul.archive(), with_mocks() factory,
#   eternal= param on birth/awaken, and export(archive=True).

import pytest

from soul_protocol.runtime.eternal.manager import EternalStorageManager
from soul_protocol.runtime.soul import Soul


@pytest.mark.asyncio
async def test_with_mocks_factory():
    """with_mocks() should register ipfs and arweave providers."""
    mgr = EternalStorageManager.with_mocks()
    assert "ipfs" in mgr._providers
    assert "arweave" in mgr._providers


@pytest.mark.asyncio
async def test_soul_archive_works():
    """Soul.archive() should succeed with mock eternal storage."""
    eternal = EternalStorageManager.with_mocks()
    soul = await Soul.birth("TestSoul", eternal=eternal)
    await soul.remember("test memory", importance=5)
    results = await soul.archive(tiers=["ipfs"])
    assert len(results) == 1
    assert results[0].tier == "ipfs"
    assert results[0].reference


@pytest.mark.asyncio
async def test_soul_archive_without_eternal_raises():
    """Soul.archive() without eternal storage should raise RuntimeError."""
    soul = await Soul.birth("TestSoul")
    with pytest.raises(RuntimeError, match="No eternal storage configured"):
        await soul.archive()


@pytest.mark.asyncio
async def test_export_with_archive_flag(tmp_path):
    """export(archive=True) should trigger archival after export."""
    eternal = EternalStorageManager.with_mocks()
    soul = await Soul.birth("TestSoul", eternal=eternal)
    await soul.remember("test memory", importance=5)
    path = tmp_path / "test.soul"
    await soul.export(str(path), archive=True, archive_tiers=["ipfs"])
    assert path.exists()


@pytest.mark.asyncio
async def test_awaken_with_eternal(tmp_path):
    """Awaken should accept eternal= parameter."""
    soul = await Soul.birth("TestSoul")
    path = tmp_path / "test.soul"
    await soul.export(str(path))

    eternal = EternalStorageManager.with_mocks()
    restored = await Soul.awaken(str(path), eternal=eternal)
    assert restored._eternal is eternal
    # Should be able to archive now
    results = await restored.archive(tiers=["ipfs"])
    assert len(results) == 1
