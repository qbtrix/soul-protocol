# middleware/__init__.py — Soul middleware components.
# Created: 2026-04-29 (#41) — New runtime package for soul middleware. The
#   first occupant is DomainIsolationMiddleware, which wraps a Soul and
#   enforces a domain allow-list on every read and write.
# Updated: 2026-05 — Added AutoObserveMiddleware, which wraps a Soul so every
#   conversation turn is captured automatically (auto-recall + auto-observe).

from __future__ import annotations

from soul_protocol.runtime.middleware.auto_observe import AutoObserveMiddleware
from soul_protocol.runtime.middleware.domain_isolation import (
    DomainIsolationMiddleware,
)

__all__ = [
    "AutoObserveMiddleware",
    "DomainIsolationMiddleware",
]
