# test_eternal/test_manager.py — Tests for EternalStorageManager.
# Created: 2026-03-06 — Covers registration, archive, recover, verify_all.

from __future__ import annotations

import pytest

from soul_protocol.runtime.eternal.manager import EternalStorageManager
from soul_protocol.runtime.eternal.protocol import RecoverySource
from soul_protocol.runtime.eternal.providers import (
    MockArweaveProvider,
    MockBlockchainProvider,
    MockIPFSProvider,
)

SAMPLE_DATA = b"soul-archive-payload-for-manager-tests"
SOUL_ID = "did:soul:manager-test-001"


@pytest.fixture
def manager():
    """Create an EternalStorageManager with all mock providers registered."""
    mgr = EternalStorageManager()
    mgr.register(MockIPFSProvider())
    mgr.register(MockArweaveProvider())
    mgr.register(MockBlockchainProvider())
    return mgr


class TestRegistration:
    """Tests for provider registration."""

    def test_register_provider(self):
        mgr = EternalStorageManager()
        assert len(mgr.providers) == 0
        mgr.register(MockIPFSProvider())
        assert "ipfs" in mgr.providers
        assert len(mgr.providers) == 1

    def test_register_multiple(self, manager):
        assert len(manager.providers) == 3
        assert set(manager.providers.keys()) == {"ipfs", "arweave", "blockchain"}

    def test_unregister(self, manager):
        assert manager.unregister("ipfs") is True
        assert "ipfs" not in manager.providers

    def test_unregister_missing(self, manager):
        assert manager.unregister("nonexistent") is False


class TestArchive:
    """Tests for the archive method."""

    async def test_archive_all_tiers(self, manager):
        results = await manager.archive(SAMPLE_DATA, SOUL_ID)
        assert len(results) == 3
        tiers = {r.tier for r in results}
        assert tiers == {"ipfs", "arweave", "blockchain"}

    async def test_archive_specific_tiers(self, manager):
        results = await manager.archive(SAMPLE_DATA, SOUL_ID, tiers=["ipfs"])
        assert len(results) == 1
        assert results[0].tier == "ipfs"

    async def test_archive_unknown_tier_raises(self, manager):
        with pytest.raises(ValueError, match="No provider registered"):
            await manager.archive(SAMPLE_DATA, SOUL_ID, tiers=["s3"])

    async def test_archive_tracks_sources(self, manager):
        await manager.archive(SAMPLE_DATA, SOUL_ID)
        sources = await manager.get_recovery_sources(SOUL_ID)
        assert len(sources) == 3

    async def test_archive_multiple_times(self, manager):
        await manager.archive(SAMPLE_DATA, SOUL_ID, tiers=["ipfs"])
        await manager.archive(SAMPLE_DATA, SOUL_ID, tiers=["arweave"])
        sources = await manager.get_recovery_sources(SOUL_ID)
        assert len(sources) == 2


class TestRecover:
    """Tests for the recover method."""

    async def test_recover_from_ipfs(self, manager):
        results = await manager.archive(SAMPLE_DATA, SOUL_ID, tiers=["ipfs"])
        source = RecoverySource(tier="ipfs", reference=results[0].reference)
        recovered = await manager.recover([source])
        assert recovered == SAMPLE_DATA

    async def test_recover_from_arweave(self, manager):
        results = await manager.archive(SAMPLE_DATA, SOUL_ID, tiers=["arweave"])
        source = RecoverySource(tier="arweave", reference=results[0].reference)
        recovered = await manager.recover([source])
        assert recovered == SAMPLE_DATA

    async def test_recover_fallback(self, manager):
        """If first source fails, try the next one."""
        results = await manager.archive(SAMPLE_DATA, SOUL_ID, tiers=["arweave"])

        # First source is bad, second is good
        bad_source = RecoverySource(tier="ipfs", reference="nonexistent-cid")
        good_source = RecoverySource(tier="arweave", reference=results[0].reference)

        recovered = await manager.recover([bad_source, good_source])
        assert recovered == SAMPLE_DATA

    async def test_recover_skips_unavailable(self, manager):
        results = await manager.archive(SAMPLE_DATA, SOUL_ID, tiers=["arweave"])
        unavailable = RecoverySource(tier="arweave", reference="some-ref", available=False)
        good = RecoverySource(tier="arweave", reference=results[0].reference)
        recovered = await manager.recover([unavailable, good])
        assert recovered == SAMPLE_DATA

    async def test_recover_all_fail_raises(self, manager):
        bad1 = RecoverySource(tier="ipfs", reference="nonexistent")
        bad2 = RecoverySource(tier="arweave", reference="nonexistent")

        with pytest.raises(RuntimeError, match="Failed to recover"):
            await manager.recover([bad1, bad2])

    async def test_recover_no_provider_raises(self):
        mgr = EternalStorageManager()
        source = RecoverySource(tier="ipfs", reference="anything")
        with pytest.raises(RuntimeError, match="no provider registered"):
            await mgr.recover([source])


class TestVerifyAll:
    """Tests for the verify_all method."""

    async def test_verify_all_after_archive(self, manager):
        await manager.archive(SAMPLE_DATA, SOUL_ID)
        status = await manager.verify_all(SOUL_ID)
        assert all(status.values())
        assert len(status) == 3

    async def test_verify_all_unknown_soul(self, manager):
        status = await manager.verify_all("did:soul:unknown")
        assert status == {}

    async def test_verify_all_partial(self):
        """Verify works even when some providers are missing."""
        mgr = EternalStorageManager()
        ipfs = MockIPFSProvider()
        mgr.register(ipfs)

        results = await mgr.archive(SAMPLE_DATA, SOUL_ID, tiers=["ipfs"])
        assert len(results) == 1

        status = await mgr.verify_all(SOUL_ID)
        assert status == {"ipfs": True}


class TestContentAddressVerification:
    """Tests for #293: content-address hash verification on recover()."""

    async def test_recover_detects_tampered_ipfs_content(self):
        """A compromised IPFS gateway returning wrong data must be rejected."""
        mgr = EternalStorageManager()
        ipfs = MockIPFSProvider()
        mgr.register(ipfs)

        # Archive genuine data
        results = await mgr.archive(SAMPLE_DATA, SOUL_ID, tiers=["ipfs"])
        cid = results[0].reference

        # Tamper: overwrite the CID's stored data with different bytes
        ipfs._store[cid] = b"this-is-not-the-original-data"

        source = RecoverySource(tier="ipfs", reference=cid)
        with pytest.raises(RuntimeError, match="content-address mismatch"):
            await mgr.recover([source])

    async def test_recover_non_content_addressed_skips_check(self):
        """Arweave (non-content-addressed) should recover without hash check."""
        mgr = EternalStorageManager()
        arweave = MockArweaveProvider()
        mgr.register(arweave)

        results = await mgr.archive(SAMPLE_DATA, SOUL_ID, tiers=["arweave"])
        tx_id = results[0].reference

        # Even if we replace the stored data, Arweave is not content-addressed
        # so the manager should NOT reject it (no hash to verify against).
        arweave._store[tx_id] = b"different-payload"

        source = RecoverySource(tier="arweave", reference=tx_id)
        recovered = await mgr.recover([source])
        assert recovered == b"different-payload"

    async def test_content_addressed_property_on_providers(self):
        """All providers must report the correct content_addressed value."""
        assert MockIPFSProvider().content_addressed is True
        assert MockArweaveProvider().content_addressed is False
        assert MockBlockchainProvider().content_addressed is False

    async def test_tampered_ipfs_falls_back_to_arweave(self):
        """If IPFS is tampered, recover() should try the next source."""
        mgr = EternalStorageManager()
        ipfs = MockIPFSProvider()
        arweave = MockArweaveProvider()
        mgr.register(ipfs)
        mgr.register(arweave)

        ipfs_results = await mgr.archive(SAMPLE_DATA, SOUL_ID, tiers=["ipfs"])
        arweave_results = await mgr.archive(SAMPLE_DATA, SOUL_ID, tiers=["arweave"])

        # Tamper IPFS
        ipfs._store[ipfs_results[0].reference] = b"tampered"

        # Recovery should skip IPFS (mismatch) and succeed via Arweave
        sources = [
            RecoverySource(tier="ipfs", reference=ipfs_results[0].reference),
            RecoverySource(tier="arweave", reference=arweave_results[0].reference),
        ]
        recovered = await mgr.recover(sources)
        assert recovered == SAMPLE_DATA
