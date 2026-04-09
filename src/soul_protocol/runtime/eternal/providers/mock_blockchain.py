# eternal/providers/mock_blockchain.py — In-memory mock blockchain registry.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Created: 2026-03-06 — Simulates an on-chain soul registry (NFT-like)
#   without any external dependencies.

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any

from soul_protocol.runtime.eternal.protocol import ArchiveResult


class MockBlockchainProvider:
    """Mock blockchain provider for testing.

    Simulates an on-chain soul registry where each soul gets a
    unique token ID. The chain stores a hash/pointer to the data,
    and the data itself is stored in-memory. No real chain required.
    """

    def __init__(self, chain_name: str = "mock-chain") -> None:
        self._chain_name = chain_name
        # In-memory stores
        self._registry: dict[str, bytes] = {}  # token_id -> data
        self._soul_tokens: dict[str, str] = {}  # soul_id -> token_id
        self._token_counter: int = 0

    @property
    def tier_name(self) -> str:
        return "blockchain"

    def _mint_token_id(self, soul_id: str) -> str:
        """Generate a mock token ID for a soul."""
        self._token_counter += 1
        seed = f"{self._chain_name}:{soul_id}:{self._token_counter}:{time.time_ns()}"
        digest = hashlib.sha256(seed.encode()).hexdigest()[:16]
        return f"0x{digest}"

    async def archive(self, soul_data: bytes, soul_id: str, **kwargs: Any) -> ArchiveResult:
        """Archive soul data to mock blockchain registry."""
        token_id = self._mint_token_id(soul_id)
        self._registry[token_id] = soul_data
        self._soul_tokens[soul_id] = token_id

        # Simulate gas cost
        gas_cost = 0.002 + (len(soul_data) / 1024) * 0.001
        cost_str = f"${gas_cost:.4f}"

        return ArchiveResult(
            tier="blockchain",
            reference=token_id,
            url=f"https://{self._chain_name}.explorer/token/{token_id}",
            cost=cost_str,
            permanent=True,  # Blockchain is permanent
            archived_at=datetime.now(),
            metadata={
                "token_id": token_id,
                "chain": self._chain_name,
                "contract": "0xSOUL_REGISTRY",
                "soul_id": soul_id,
                "data_hash": hashlib.sha256(soul_data).hexdigest(),
                "size_bytes": len(soul_data),
            },
        )

    async def retrieve(self, reference: str, **kwargs: Any) -> bytes:
        """Retrieve soul data from mock blockchain by token ID."""
        data = self._registry.get(reference)
        if data is None:
            raise KeyError(f"Token '{reference}' not found in mock blockchain registry")
        return data

    async def verify(self, reference: str) -> bool:
        """Verify that a token exists in the mock blockchain."""
        return reference in self._registry
