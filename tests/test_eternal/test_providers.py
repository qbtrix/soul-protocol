# test_eternal/test_providers.py — Tests for each mock storage provider.
# Created: 2026-03-06 — Covers archive, retrieve, verify for
#   MockIPFS, MockArweave, MockBlockchain, and Local providers.

from __future__ import annotations

import pytest

from soul_protocol.runtime.eternal.providers import (
    LocalStorageProvider,
    MockArweaveProvider,
    MockBlockchainProvider,
    MockIPFSProvider,
)

SAMPLE_DATA = b"test-soul-data-bytes-1234567890"
SOUL_ID = "did:soul:test-soul-001"


class TestMockIPFSProvider:
    """Tests for the MockIPFSProvider."""

    @pytest.fixture
    def provider(self):
        return MockIPFSProvider()

    async def test_archive_returns_result(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert result.tier == "ipfs"
        assert result.reference.startswith("bafybeig")
        assert "ipfs.io" in result.url
        assert result.metadata["cid"] == result.reference
        assert result.metadata["size_bytes"] == len(SAMPLE_DATA)

    async def test_retrieve_after_archive(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        retrieved = await provider.retrieve(result.reference)
        assert retrieved == SAMPLE_DATA

    async def test_verify_after_archive(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert await provider.verify(result.reference) is True

    async def test_verify_missing(self, provider):
        assert await provider.verify("nonexistent-cid") is False

    async def test_retrieve_missing_raises(self, provider):
        with pytest.raises(KeyError, match="not found"):
            await provider.retrieve("nonexistent-cid")

    async def test_content_addressed(self, provider):
        """Same data should produce the same CID."""
        r1 = await provider.archive(SAMPLE_DATA, "soul-1")
        r2 = await provider.archive(SAMPLE_DATA, "soul-2")
        assert r1.reference == r2.reference

    async def test_different_data_different_cid(self, provider):
        r1 = await provider.archive(b"data-a", SOUL_ID)
        r2 = await provider.archive(b"data-b", SOUL_ID)
        assert r1.reference != r2.reference


class TestMockArweaveProvider:
    """Tests for the MockArweaveProvider."""

    @pytest.fixture
    def provider(self):
        return MockArweaveProvider()

    async def test_archive_returns_result(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert result.tier == "arweave"
        assert len(result.reference) == 43
        assert "arweave.net" in result.url
        assert result.permanent is True

    async def test_archive_has_cost(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert result.cost.startswith("$")
        cost_val = float(result.cost.replace("$", ""))
        assert cost_val > 0

    async def test_retrieve_after_archive(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        retrieved = await provider.retrieve(result.reference)
        assert retrieved == SAMPLE_DATA

    async def test_verify_after_archive(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert await provider.verify(result.reference) is True

    async def test_verify_missing(self, provider):
        assert await provider.verify("nonexistent-tx") is False

    async def test_retrieve_missing_raises(self, provider):
        with pytest.raises(KeyError, match="not found"):
            await provider.retrieve("nonexistent-tx")

    async def test_unique_tx_ids(self, provider):
        """Each archive should get a unique transaction ID."""
        r1 = await provider.archive(SAMPLE_DATA, SOUL_ID)
        r2 = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert r1.reference != r2.reference


class TestMockBlockchainProvider:
    """Tests for the MockBlockchainProvider."""

    @pytest.fixture
    def provider(self):
        return MockBlockchainProvider(chain_name="test-chain")

    async def test_archive_returns_result(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert result.tier == "blockchain"
        assert result.reference.startswith("0x")
        assert result.permanent is True
        assert result.metadata["chain"] == "test-chain"
        assert result.metadata["contract"] == "0xSOUL_REGISTRY"

    async def test_retrieve_after_archive(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        retrieved = await provider.retrieve(result.reference)
        assert retrieved == SAMPLE_DATA

    async def test_verify_after_archive(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert await provider.verify(result.reference) is True

    async def test_verify_missing(self, provider):
        assert await provider.verify("0xdeadbeef") is False

    async def test_retrieve_missing_raises(self, provider):
        with pytest.raises(KeyError, match="not found"):
            await provider.retrieve("0xdeadbeef")

    async def test_unique_token_ids(self, provider):
        r1 = await provider.archive(SAMPLE_DATA, SOUL_ID)
        r2 = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert r1.reference != r2.reference

    async def test_archive_has_cost(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        cost_val = float(result.cost.replace("$", ""))
        assert cost_val > 0


class TestLocalStorageProvider:
    """Tests for the LocalStorageProvider."""

    @pytest.fixture
    def provider(self, tmp_path):
        return LocalStorageProvider(base_dir=tmp_path / "eternal-local")

    async def test_archive_returns_result(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert result.tier == "local"
        assert result.reference.startswith("local:")
        assert result.url.startswith("file://")
        assert result.permanent is False

    async def test_retrieve_after_archive(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        retrieved = await provider.retrieve(result.reference)
        assert retrieved == SAMPLE_DATA

    async def test_verify_after_archive(self, provider):
        result = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert await provider.verify(result.reference) is True

    async def test_verify_missing(self, provider):
        assert await provider.verify("local:missing:ref") is False

    async def test_retrieve_missing_raises(self, provider):
        with pytest.raises(FileNotFoundError):
            await provider.retrieve("local:missing:ref")

    async def test_deterministic_reference(self, provider):
        """Same soul_id + same data should give same reference."""
        r1 = await provider.archive(SAMPLE_DATA, SOUL_ID)
        r2 = await provider.archive(SAMPLE_DATA, SOUL_ID)
        assert r1.reference == r2.reference
