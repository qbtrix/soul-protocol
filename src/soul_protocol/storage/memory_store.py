# storage/memory_store.py — InMemoryStorage backend for testing and ephemeral use.
# Created: 2026-02-22 — Dict-backed implementation of StorageProtocol; no disk I/O.

from __future__ import annotations

from pathlib import Path

from soul_protocol.types import SoulConfig


class InMemoryStorage:
    """In-memory soul storage backend.

    Stores ``SoulConfig`` objects in a plain dict keyed by ``soul_id``.
    Useful for unit tests and short-lived processes that don't need persistence.
    """

    def __init__(self) -> None:
        self._store: dict[str, SoulConfig] = {}

    async def save(self, soul_id: str, config: SoulConfig, path: Path | None = None) -> None:
        """Store a soul config in memory."""
        self._store[soul_id] = config

    async def load(self, soul_id: str, path: Path | None = None) -> SoulConfig | None:
        """Retrieve a soul config from memory, or ``None`` if not found."""
        return self._store.get(soul_id)

    async def delete(self, soul_id: str) -> bool:
        """Remove a soul from memory. Returns ``True`` if it existed."""
        if soul_id in self._store:
            del self._store[soul_id]
            return True
        return False

    async def list_souls(self) -> list[str]:
        """Return all stored soul IDs."""
        return list(self._store.keys())
