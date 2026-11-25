# consent/__init__.py — Consent passes: time-limited, domain-scoped, revocable
#   app access to a soul's memory, with every grant/read/write/denial signed
#   onto the trust chain.
# Created: 2026-11-14
# Updated: 2026-11-25 (#326 review) — Exports ConsentManager (``soul.consent``)
#   instead of the grant_pass / revoke_pass functions.

from __future__ import annotations

from .models import (
    ConsentAccess,
    ConsentEvent,
    ConsentPass,
    ConsentStatus,
    TrimRecord,
    hash_token,
    parse_duration,
)
from .registry import ConsentRegistry
from .service import ConsentManager, ConsentSession

__all__ = [
    "ConsentAccess",
    "ConsentEvent",
    "ConsentManager",
    "ConsentPass",
    "ConsentRegistry",
    "ConsentSession",
    "ConsentStatus",
    "TrimRecord",
    "hash_token",
    "parse_duration",
]
