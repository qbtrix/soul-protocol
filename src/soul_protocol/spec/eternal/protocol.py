# spec/eternal/protocol.py — Canonical protocol definition for eternal storage backends.
# Created: v0.4.0 — Moved from eternal/protocol.py to spec/ layer.
# Defines EternalStorageProvider protocol, ArchiveResult model, and RecoverySource model.

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ArchiveResult(BaseModel):
    """Result of archiving a soul to eternal storage."""

    tier: str  # "ipfs", "arweave", "blockchain"
    reference: str  # CID, txId, etc.
    url: str = ""  # Human-readable URL
    cost: str = "$0.00"
    permanent: bool = False
    archived_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecoverySource(BaseModel):
    """A source from which a soul can be recovered."""

    tier: str
    reference: str
    available: bool = True
    last_verified: datetime = Field(default_factory=datetime.now)


@runtime_checkable
class EternalStorageProvider(Protocol):
    """Interface for any eternal storage backend.

    All backends must implement archive, retrieve, and verify.
    The tier_name property identifies which storage tier this
    provider represents (e.g., 'ipfs', 'arweave', 'blockchain', 'local').
    """

    @property
    def tier_name(self) -> str:
        """Name of this storage tier (e.g., 'ipfs', 'arweave')."""
        ...

    async def archive(self, soul_data: bytes, soul_id: str, **kwargs: Any) -> ArchiveResult:
        """Archive soul data. Returns an ArchiveResult."""
        ...

    async def retrieve(self, reference: str, **kwargs: Any) -> bytes:
        """Retrieve soul data by reference. Returns raw bytes."""
        ...

    async def verify(self, reference: str) -> bool:
        """Verify that archived data still exists and is accessible."""
        ...
