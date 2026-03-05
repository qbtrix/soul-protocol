# crypto/encrypt.py — Symmetric encryption for soul files using Fernet + PBKDF2.
# Created: 2026-02-22 — Provides passphrase-based encrypt/decrypt with salt prepended
# to the ciphertext so that only the passphrase is needed for decryption.

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# PBKDF2 iteration count — balance between security and speed
_ITERATIONS = 480_000

# Salt length in bytes
_SALT_LENGTH = 16


def derive_key(passphrase: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Derive a Fernet-compatible key from a passphrase using PBKDF2-HMAC-SHA256.

    Args:
        passphrase: The user-provided passphrase.
        salt: Optional salt bytes. If ``None``, a random 16-byte salt is generated.

    Returns:
        A tuple of ``(key, salt)`` where ``key`` is a url-safe base64-encoded
        32-byte key suitable for ``Fernet(key)``.
    """
    if salt is None:
        salt = os.urandom(_SALT_LENGTH)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    raw_key = kdf.derive(passphrase.encode("utf-8"))
    encoded_key = base64.urlsafe_b64encode(raw_key)
    return encoded_key, salt


def encrypt_data(data: bytes, passphrase: str) -> bytes:
    """Encrypt data with a passphrase using Fernet symmetric encryption.

    The output format is::

        [16 bytes salt][Fernet ciphertext...]

    The salt is prepended so that decryption only needs the passphrase.

    Args:
        data: Plaintext bytes to encrypt.
        passphrase: The passphrase to derive the encryption key from.

    Returns:
        Salt-prefixed ciphertext bytes.
    """
    key, salt = derive_key(passphrase)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data)
    return salt + encrypted


def decrypt_data(encrypted: bytes, passphrase: str) -> bytes:
    """Decrypt salt-prefixed Fernet ciphertext using a passphrase.

    Args:
        encrypted: The output of ``encrypt_data`` (salt + ciphertext).
        passphrase: The same passphrase used for encryption.

    Returns:
        The original plaintext bytes.

    Raises:
        cryptography.fernet.InvalidToken: If the passphrase is wrong or data
            is corrupted.
    """
    salt = encrypted[:_SALT_LENGTH]
    ciphertext = encrypted[_SALT_LENGTH:]

    key, _ = derive_key(passphrase, salt=salt)
    fernet = Fernet(key)
    return fernet.decrypt(ciphertext)
