# crypto/__init__.py — Re-exports for the crypto subpackage.
# Updated: 2026-04-29 (#42) — Added Ed25519SignatureProvider and Keystore for
#   the trust chain feature. Both are runtime-side (concrete implementations);
#   the SignatureProvider protocol itself lives in spec.trust.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Created: 2026-02-22 — Exposes symmetric encryption helpers for soul file protection.

from __future__ import annotations

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.crypto.encrypt import decrypt_data, derive_key, encrypt_data
from soul_protocol.runtime.crypto.keystore import (
    PRIVATE_KEY_FILENAME,
    PUBLIC_KEY_FILENAME,
    Keystore,
)

__all__ = [
    "derive_key",
    "encrypt_data",
    "decrypt_data",
    "Ed25519SignatureProvider",
    "Keystore",
    "PRIVATE_KEY_FILENAME",
    "PUBLIC_KEY_FILENAME",
]
