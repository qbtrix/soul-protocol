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

    Updated: 2026-08-04 (#293) — Added ``content_addressed`` property and
    ``compute_reference()`` method so ``EternalStorageManager.recover()``
    can verify retrieved bytes against the content-addressed reference.
    """

    @property
    def tier_name(self) -> str:
        """Name of this storage tier (e.g., 'ipfs', 'arweave')."""
        ...

    @property
    def content_addressed(self) -> bool:
        """Whether this tier uses content-addressing.

        Content-addressed tiers derive the reference (e.g. CID) from a hash
        of the archived bytes.  ``recover()`` verifies retrieved data against
        the reference for these tiers, rejecting substitution attacks (#293).
        """
        ...

    def compute_reference(self, data: bytes) -> str:
        """Compute the canonical reference for *data*.

        Only meaningful when ``content_addressed`` is True.  The manager
        calls this after retrieval and compares the result to the stored
        reference.  Non-content-addressed tiers must raise
        ``NotImplementedError``.
        """
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
