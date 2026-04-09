# test_eternal/test_protocol.py — Protocol compliance tests for EternalStorageProvider.
# Created: 2026-03-06 — Verifies that all mock providers satisfy the
#   EternalStorageProvider protocol at runtime.

from __future__ import annotations

from soul_protocol.runtime.eternal.protocol import (
    ArchiveResult,
    EternalStorageProvider,
    RecoverySource,
)
from soul_protocol.runtime.eternal.providers import (
    LocalStorageProvider,
    MockArweaveProvider,
    MockBlockchainProvider,
    MockIPFSProvider,
)


class TestArchiveResultModel:
    """Tests for the ArchiveResult Pydantic model."""

    def test_create_minimal(self):
        result = ArchiveResult(tier="ipfs", reference="bafytest123")
        assert result.tier == "ipfs"
        assert result.reference == "bafytest123"
        assert result.cost == "$0.00"
        assert result.permanent is False
        assert result.url == ""
        assert result.metadata == {}

    def test_create_full(self):
        result = ArchiveResult(
            tier="arweave",
            reference="tx_abc123",
            url="https://arweave.net/tx_abc123",
            cost="$0.0050",
            permanent=True,
            metadata={"block_height": 100},
        )
        assert result.permanent is True
        assert result.cost == "$0.0050"
        assert result.metadata["block_height"] == 100

    def test_serialization_roundtrip(self):
        result = ArchiveResult(tier="blockchain", reference="0xdeadbeef")
        data = result.model_dump()
        restored = ArchiveResult.model_validate(data)
        assert restored.tier == result.tier
        assert restored.reference == result.reference


class TestRecoverySourceModel:
    """Tests for the RecoverySource Pydantic model."""

    def test_create_default(self):
        source = RecoverySource(tier="ipfs", reference="bafytest")
        assert source.available is True

    def test_create_unavailable(self):
        source = RecoverySource(tier="arweave", reference="tx_123", available=False)
        assert source.available is False


class TestProtocolCompliance:
    """Verify all providers implement EternalStorageProvider."""

    def test_mock_ipfs_is_provider(self):
        provider = MockIPFSProvider()
        assert isinstance(provider, EternalStorageProvider)

    def test_mock_arweave_is_provider(self):
        provider = MockArweaveProvider()
        assert isinstance(provider, EternalStorageProvider)

    def test_mock_blockchain_is_provider(self):
        provider = MockBlockchainProvider()
        assert isinstance(provider, EternalStorageProvider)

    def test_local_is_provider(self, tmp_path):
        provider = LocalStorageProvider(base_dir=tmp_path / "local")
        assert isinstance(provider, EternalStorageProvider)

    def test_tier_names(self, tmp_path):
        assert MockIPFSProvider().tier_name == "ipfs"
        assert MockArweaveProvider().tier_name == "arweave"
        assert MockBlockchainProvider().tier_name == "blockchain"
        assert LocalStorageProvider(base_dir=tmp_path / "local").tier_name == "local"
