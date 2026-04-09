# eternal/__init__.py — Public API for the eternal storage subsystem.
# Created: 2026-03-06 — Exports protocol, models, manager, and mock providers.

from __future__ import annotations

from .manager import EternalStorageManager
from .protocol import ArchiveResult, EternalStorageProvider, RecoverySource

__all__ = [
    "ArchiveResult",
    "EternalStorageProvider",
    "EternalStorageManager",
    "RecoverySource",
]
