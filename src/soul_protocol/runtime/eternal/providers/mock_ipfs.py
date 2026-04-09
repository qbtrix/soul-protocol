# eternal/providers/mock_ipfs.py — In-memory mock IPFS storage provider.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Created: 2026-03-06 — Simulates IPFS CID generation and content-addressed
#   storage without any external dependencies.

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from soul_protocol.runtime.eternal.protocol import ArchiveResult


class MockIPFSProvider:
    """Mock IPFS provider for testing.

    Stores data in memory and generates deterministic CID-like
    references based on content hashing. No real IPFS node required.
    """

    def __init__(self) -> None:
        # In-memory store: CID -> bytes
        self._store: dict[str, bytes] = {}

    @property
    def tier_name(self) -> str:
        return "ipfs"

    def _generate_cid(self, data: bytes) -> str:
        """Generate a mock CID from content hash (content-addressed)."""
        digest = hashlib.sha256(data).hexdigest()
        # Mimic CIDv1 base32 format prefix
        return f"bafybeig{digest[:48]}"

    async def archive(self, soul_data: bytes, soul_id: str, **kwargs: Any) -> ArchiveResult:
        """Archive soul data to mock IPFS."""
        cid = self._generate_cid(soul_data)
        self._store[cid] = soul_data

        return ArchiveResult(
            tier="ipfs",
            reference=cid,
            url=f"https://ipfs.io/ipfs/{cid}",
            cost="$0.00",
            permanent=False,  # IPFS requires pinning for permanence
            archived_at=datetime.now(),
            metadata={
                "cid": cid,
                "size_bytes": len(soul_data),
                "pinned": True,
                "soul_id": soul_id,
            },
        )

    async def retrieve(self, reference: str, **kwargs: Any) -> bytes:
        """Retrieve soul data from mock IPFS by CID."""
        data = self._store.get(reference)
        if data is None:
            raise KeyError(f"CID '{reference}' not found in mock IPFS store")
        return data

    async def verify(self, reference: str) -> bool:
        """Verify that a CID exists in mock IPFS."""
        return reference in self._store
