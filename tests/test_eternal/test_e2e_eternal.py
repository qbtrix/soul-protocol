# test_eternal/test_e2e_eternal.py — End-to-end tests for eternal storage.
# Created: 2026-03-06 — Full lifecycle: birth -> archive -> verify -> recover -> compare.

from __future__ import annotations

import pytest

from soul_protocol.runtime.eternal.manager import EternalStorageManager
from soul_protocol.runtime.eternal.protocol import RecoverySource
from soul_protocol.runtime.eternal.providers import (
    LocalStorageProvider,
    MockArweaveProvider,
    MockBlockchainProvider,
    MockIPFSProvider,
)
from soul_protocol.runtime.soul import Soul


class TestEternalE2E:
    """End-to-end eternal storage test: birth, archive, verify, recover."""

    @pytest.fixture
    def manager(self, tmp_path):
        mgr = EternalStorageManager()
        mgr.register(MockIPFSProvider())
        mgr.register(MockArweaveProvider())
        mgr.register(MockBlockchainProvider())
        mgr.register(LocalStorageProvider(base_dir=tmp_path / "local"))
        return mgr

    async def test_full_lifecycle(self, manager, tmp_path):
        """Birth a soul, archive to all tiers, verify, recover, compare."""
        # 1. Birth a soul
        soul = await Soul.birth("EternalTestSoul", archetype="The Immortal")
        soul_path = tmp_path / "eternal.soul"
        await soul.export(str(soul_path))
        original_data = soul_path.read_bytes()

        # 2. Archive to all mock tiers
        results = await manager.archive(original_data, soul.did)
        assert len(results) == 4  # ipfs, arweave, blockchain, local

        # Check each result has expected fields
        for r in results:
            assert r.reference
            assert r.tier in ("ipfs", "arweave", "blockchain", "local")
            assert r.archived_at is not None

        # 3. Verify archives exist
        status = await manager.verify_all(soul.did)
        assert all(status.values()), f"Some tiers failed verification: {status}"
        assert len(status) == 4

        # 4. Recover from each tier individually
        sources = await manager.get_recovery_sources(soul.did)
        assert len(sources) == 4

        for source in sources:
            recovered_data = await manager.recover([source])
            assert recovered_data == original_data, f"Data mismatch recovering from {source.tier}"

        # 5. Recover using fallback chain (all sources)
        recovered = await manager.recover(sources)
        assert recovered == original_data

    async def test_recover_awakens_valid_soul(self, manager, tmp_path):
        """Recovered .soul data can be awakened into a valid Soul."""
        soul = await Soul.birth("RecoverableSoul", archetype="The Phoenix")
        soul_path = tmp_path / "recoverable.soul"
        await soul.export(str(soul_path))
        original_data = soul_path.read_bytes()

        # Archive and recover
        results = await manager.archive(original_data, soul.did, tiers=["ipfs"])
        source = RecoverySource(tier="ipfs", reference=results[0].reference)
        recovered_data = await manager.recover([source])

        # Write recovered data and awaken
        recovered_path = tmp_path / "recovered.soul"
        recovered_path.write_bytes(recovered_data)
        recovered_soul = await Soul.awaken(str(recovered_path))

        # Verify identity matches
        assert recovered_soul.name == soul.name
        assert recovered_soul.did == soul.did
        assert recovered_soul.archetype == soul.archetype

    async def test_archive_then_verify_after_removal(self, tmp_path):
        """If data is removed from a provider, verify returns False."""
        ipfs = MockIPFSProvider()
        mgr = EternalStorageManager()
        mgr.register(ipfs)

        soul = await Soul.birth("MortalSoul")
        soul_path = tmp_path / "mortal.soul"
        await soul.export(str(soul_path))
        data = soul_path.read_bytes()

        await mgr.archive(data, soul.did, tiers=["ipfs"])

        # Verify passes
        status = await mgr.verify_all(soul.did)
        assert status["ipfs"] is True

        # Simulate data loss by clearing the mock store
        ipfs._store.clear()

        # Verify now fails
        status = await mgr.verify_all(soul.did)
        assert status["ipfs"] is False

    async def test_multi_tier_recovery_fallback(self, manager, tmp_path):
        """If primary tier fails, manager falls back to next available tier."""
        soul = await Soul.birth("FallbackSoul")
        soul_path = tmp_path / "fallback.soul"
        await soul.export(str(soul_path))
        data = soul_path.read_bytes()

        await manager.archive(data, soul.did)

        # Get sources and mark some as broken
        sources = await manager.get_recovery_sources(soul.did)

        # Make the first source unavailable
        bad_source = RecoverySource(
            tier=sources[0].tier,
            reference="corrupted-reference",
        )
        good_sources = sources[1:]

        # Should fall back to remaining sources
        recovered = await manager.recover([bad_source] + good_sources)
        assert recovered == data
