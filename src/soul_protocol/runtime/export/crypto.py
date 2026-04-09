# crypto.py — AES-256-GCM encryption for .soul file contents.
# Updated: feat/soul-encryption — Catch cryptography.exceptions.InvalidTag specifically
#   instead of bare Exception in decrypt_blob().
# Created: feat/soul-encryption — Password-based encryption at rest for soul files.
#   Uses scrypt for key derivation (memory-hard, resistant to GPU attacks).
#   Encrypts individual file contents inside the ZIP, leaving manifest readable.
#   Format: 16-byte salt + 12-byte nonce + ciphertext + 16-byte GCM tag.

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# scrypt parameters — intentionally conservative for password hashing.
# n=2^17 (~128 MiB memory), r=8, p=1 matches OWASP recommendations.
_SCRYPT_N = 2**17
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_LENGTH = 16
_NONCE_LENGTH = 12  # AES-GCM standard nonce size
_KEY_LENGTH = 32  # AES-256


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from a password and salt using scrypt.

    Args:
        password: The user-provided password.
        salt: A 16-byte random salt.

    Returns:
        A 32-byte derived key suitable for AES-256.
    """
    kdf = Scrypt(
        salt=salt,
        length=_KEY_LENGTH,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_blob(data: bytes, password: str) -> bytes:
    """Encrypt a blob with AES-256-GCM using a password-derived key.

    Output format: salt (16 bytes) || nonce (12 bytes) || ciphertext+tag.

    The salt is generated fresh for each call so the same password
    produces different ciphertext every time.

    Args:
        data: Plaintext bytes to encrypt.
        password: The user-provided password.

    Returns:
        Encrypted bytes with salt and nonce prepended.
    """
    salt = os.urandom(_SALT_LENGTH)
    nonce = os.urandom(_NONCE_LENGTH)
    key = derive_key(password, salt)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)

    return salt + nonce + ciphertext


def decrypt_blob(encrypted: bytes, password: str) -> bytes:
    """Decrypt a blob previously encrypted with encrypt_blob().

    Args:
        encrypted: The full encrypted payload (salt + nonce + ciphertext+tag).
        password: The password used during encryption.

    Returns:
        The original plaintext bytes.

    Raises:
        ValueError: If the password is wrong or the data is corrupted.
    """
    min_length = _SALT_LENGTH + _NONCE_LENGTH + 16  # at least tag
    if len(encrypted) < min_length:
        raise ValueError("Encrypted data is too short to be valid")

    salt = encrypted[:_SALT_LENGTH]
    nonce = encrypted[_SALT_LENGTH : _SALT_LENGTH + _NONCE_LENGTH]
    ciphertext = encrypted[_SALT_LENGTH + _NONCE_LENGTH :]

    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise ValueError("Decryption failed — wrong password or corrupted data") from exc
