# eternal/providers/local.py — File-based local eternal storage provider.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Created: 2026-03-06 — Stores soul archives as files on the local filesystem.
# Updated: 2026-03-06 — Lazy directory creation: mkdir moved from __init__ to archive().

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from soul_protocol.runtime.eternal.protocol import ArchiveResult


class LocalStorageProvider:
    """Local filesystem storage provider for soul archives.

    Stores archives as files in a configurable directory, using a
    hash-based filename to avoid collisions.
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir is None:
            self._base_dir = Path.home() / ".soul" / "eternal" / "local"
        else:
            self._base_dir = Path(base_dir)

    @property
    def tier_name(self) -> str:
        return "local"

    def _ref_for(self, soul_data: bytes, soul_id: str) -> str:
        """Generate a deterministic reference from soul_id + content hash."""
        content_hash = hashlib.sha256(soul_data).hexdigest()[:16]
        return f"local:{soul_id}:{content_hash}"

    def _path_for(self, reference: str) -> Path:
        """Convert a reference to a filesystem path."""
        safe_name = reference.replace(":", "_").replace("/", "_")
        return self._base_dir / f"{safe_name}.soul"

    async def archive(self, soul_data: bytes, soul_id: str, **kwargs: Any) -> ArchiveResult:
        """Archive soul data to local filesystem."""
        self._base_dir.mkdir(parents=True, exist_ok=True)
        ref = self._ref_for(soul_data, soul_id)
        path = self._path_for(ref)
        path.write_bytes(soul_data)

        return ArchiveResult(
            tier="local",
            reference=ref,
            url=f"file://{path}",
            cost="$0.00",
            permanent=False,
            archived_at=datetime.now(),
            metadata={"path": str(path), "size_bytes": len(soul_data)},
        )

    async def retrieve(self, reference: str, **kwargs: Any) -> bytes:
        """Retrieve soul data from local filesystem."""
        path = self._path_for(reference)
        if not path.exists():
            raise FileNotFoundError(f"No local archive found at {path} for reference '{reference}'")
        return path.read_bytes()

    async def verify(self, reference: str) -> bool:
        """Verify that a local archive still exists."""
        path = self._path_for(reference)
        return path.exists() and path.is_file()
