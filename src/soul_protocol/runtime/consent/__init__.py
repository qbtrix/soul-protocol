# consent/__init__.py — Consent passes: time-limited, domain-scoped, revocable
#   app access to a soul's memory, with every grant/read/write/denial signed
#   onto the trust chain.
# Created: 2026-11-14

from __future__ import annotations

from .models import (
    ConsentAccess,
    ConsentEvent,
    ConsentPass,
    ConsentStatus,
    hash_token,
    parse_duration,
)
from .registry import ConsentRegistry
from .service import ConsentSession, grant_pass, revoke_pass

__all__ = [
    "ConsentAccess",
    "ConsentEvent",
    "ConsentPass",
    "ConsentRegistry",
    "ConsentSession",
    "ConsentStatus",
    "grant_pass",
    "hash_token",
    "parse_duration",
    "revoke_pass",
]
