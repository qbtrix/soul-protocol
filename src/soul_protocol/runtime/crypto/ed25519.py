# crypto/ed25519.py — Ed25519 SignatureProvider implementation.
# Created: 2026-04-29 (#42) — Concrete signer/verifier wired to the
# `cryptography` library (already a base dep). Used by TrustChainManager
# and any caller that needs a SignatureProvider conforming to the spec.
#
# Ed25519 is the default for the trust chain because:
#   - 32-byte keys, 64-byte signatures — compact even after base64.
#   - Deterministic signatures (no nonce reuse risk).
#   - Built into `cryptography` so we don't add a new dep.
#   - Already used elsewhere in the project (org root keys in cli/org.py).

from __future__ import annotations

import base64
import logging

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from soul_protocol.spec.trust import DEFAULT_ALGORITHM, SignatureProvider

logger = logging.getLogger(__name__)


class Ed25519SignatureProvider:
    """A :class:`SignatureProvider` backed by Ed25519 keys.

    Construct without arguments to get a fresh keypair; pass
    ``private_key_bytes`` (raw 32 bytes) to wrap an existing key. For
    deterministic test keys, use :meth:`from_seed`.

    The provider exposes raw public/private bytes as base64 strings so the
    chain can travel over plain JSON. Private bytes are also available as
    ``private_key_bytes`` for direct keystore I/O.
    """

    algorithm: str = DEFAULT_ALGORITHM

    def __init__(self, private_key_bytes: bytes | None = None) -> None:
        if private_key_bytes is None:
            self._private = Ed25519PrivateKey.generate()
        else:
            if len(private_key_bytes) != 32:
                raise ValueError(
                    f"Ed25519 private key must be 32 bytes, got {len(private_key_bytes)}"
                )
            self._private = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        self._public = self._private.public_key()

    # ---------- Class constructors ----------

    @classmethod
    def from_seed(cls, seed: bytes) -> Ed25519SignatureProvider:
        """Build a provider from a fixed seed.

        Useful for test isolation: identical seeds produce identical
        keypairs. The seed is used directly as the 32-byte private key, so
        callers MUST pass exactly 32 bytes (or pad / hash upstream).
        """
        if len(seed) != 32:
            raise ValueError(f"Ed25519 seed must be 32 bytes, got {len(seed)}")
        return cls(private_key_bytes=seed)

    # ---------- Properties ----------

    @property
    def private_key_bytes(self) -> bytes:
        """Raw 32-byte private key. Treat as a secret."""
        from cryptography.hazmat.primitives import serialization

        return self._private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @property
    def public_key_bytes(self) -> bytes:
        """Raw 32-byte public key."""
        from cryptography.hazmat.primitives import serialization

        return self._public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @property
    def public_key(self) -> str:
        """Base64-encoded public key. Safe to ship over JSON."""
        return base64.b64encode(self.public_key_bytes).decode("ascii")

    # ---------- Sign / verify ----------

    def sign(self, message: bytes) -> str:
        """Sign ``message`` and return a base64 string of the raw signature."""
        sig = self._private.sign(message)
        return base64.b64encode(sig).decode("ascii")

    def verify(self, message: bytes, signature: str, public_key: str) -> bool:
        """Verify ``signature`` against ``message`` using ``public_key``.

        Returns False on any failure (bad encoding, wrong key length, bad
        signature). Never raises — keeps verification call sites simple.
        """
        try:
            sig_bytes = base64.b64decode(signature)
            pk_bytes = base64.b64decode(public_key)
            pk = Ed25519PublicKey.from_public_bytes(pk_bytes)
            pk.verify(sig_bytes, message)
            return True
        except (InvalidSignature, ValueError):
            return False
        except Exception as e:
            logger.debug("Unexpected verify error: %s", e)
            return False


# Static check that we satisfy the protocol — caught at import time.
_: SignatureProvider = Ed25519SignatureProvider()
del _


__all__ = ["Ed25519SignatureProvider"]
