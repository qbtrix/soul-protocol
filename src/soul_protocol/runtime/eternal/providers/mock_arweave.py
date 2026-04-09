# eternal/providers/mock_arweave.py — In-memory mock Arweave storage provider.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Created: 2026-03-06 — Simulates Arweave transaction creation and permanent
#   storage without any external dependencies.

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any

from soul_protocol.runtime.eternal.protocol import ArchiveResult


class MockArweaveProvider:
    """Mock Arweave provider for testing.

    Simulates Arweave's permanent storage model with in-memory
    data and deterministic transaction IDs. No real Arweave gateway required.
    """

    def __init__(self) -> None:
        # In-memory store: tx_id -> bytes
        self._store: dict[str, bytes] = {}
        self._tx_counter: int = 0

    @property
    def tier_name(self) -> str:
        return "arweave"

    def _generate_tx_id(self, data: bytes) -> str:
        """Generate a mock Arweave transaction ID."""
        self._tx_counter += 1
        seed = f"{time.time_ns()}:{self._tx_counter}:{len(data)}"
        digest = hashlib.sha256(seed.encode()).hexdigest()
        # Arweave tx IDs are 43 chars, base64url encoded
        return digest[:43]

    async def archive(self, soul_data: bytes, soul_id: str, **kwargs: Any) -> ArchiveResult:
        """Archive soul data to mock Arweave."""
        tx_id = self._generate_tx_id(soul_data)
        self._store[tx_id] = soul_data

        # Simulate cost based on data size (~$0.005/KB on Arweave)
        cost_usd = len(soul_data) / 1024 * 0.005
        cost_str = f"${cost_usd:.4f}"

        return ArchiveResult(
            tier="arweave",
            reference=tx_id,
            url=f"https://arweave.net/{tx_id}",
            cost=cost_str,
            permanent=True,  # Arweave is permanent by design
            archived_at=datetime.now(),
            metadata={
                "tx_id": tx_id,
                "size_bytes": len(soul_data),
                "soul_id": soul_id,
                "block_height": 1000000 + self._tx_counter,
            },
        )

    async def retrieve(self, reference: str, **kwargs: Any) -> bytes:
        """Retrieve soul data from mock Arweave by transaction ID."""
        data = self._store.get(reference)
        if data is None:
            raise KeyError(f"Transaction '{reference}' not found in mock Arweave store")
        return data

    async def verify(self, reference: str) -> bool:
        """Verify that a transaction exists in mock Arweave."""
        return reference in self._store
