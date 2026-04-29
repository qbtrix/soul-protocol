---
{
  "title": "Symmetric Encryption for Soul Files (Fernet + PBKDF2)",
  "summary": "Provides passphrase-based encryption and decryption for soul file data using Fernet symmetric encryption with PBKDF2-HMAC-SHA256 key derivation. The salt is embedded in the ciphertext so only the passphrase is needed for decryption — no separate salt management required.",
  "concepts": [
    "Fernet",
    "PBKDF2",
    "symmetric encryption",
    "key derivation",
    "salt",
    "passphrase",
    "soul file encryption",
    "AES",
    "HMAC",
    "cryptography"
  ],
  "categories": [
    "security",
    "crypto",
    "soul file format"
  ],
  "source_docs": [
    "8b0f3b5869f40367"
  ],
  "backlinks": null,
  "word_count": 476,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul files contain sensitive identity and memory data that must be protected at rest. This module gives soul files a passphrase-based encryption layer using the industry-standard Fernet symmetric cipher backed by PBKDF2-HMAC-SHA256 key derivation.

The design goal is simplicity for the caller: you encrypt with a passphrase, you decrypt with the same passphrase — no key management, no separate salt files, nothing else to store.

## Key Design: Salt-Prefixed Ciphertext

The most important architectural decision here is that the 16-byte random salt is prepended directly to the Fernet ciphertext:

```
[16 bytes salt][Fernet ciphertext...]
```

This self-contained format means the decryption function can extract the salt from the first 16 bytes of the payload before re-deriving the key. Without this design, callers would need to store and pass the salt separately — introducing a second artifact to manage and a class of bugs where the wrong salt is used.

## Key Derivation

```python
def derive_key(passphrase: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    if salt is None:
        salt = os.urandom(_SALT_LENGTH)  # 16 bytes, cryptographically random
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    raw_key = kdf.derive(passphrase.encode("utf-8"))
    encoded_key = base64.urlsafe_b64encode(raw_key)
    return encoded_key, salt
```

PBKDF2 with 480,000 iterations deliberately makes brute-force attacks expensive. The iteration count follows NIST SP 800-132 recommendations for SHA-256 in 2025. The derived 32-byte key is base64url-encoded to match what `Fernet(key)` expects.

## Encryption Flow

```python
def encrypt_data(data: bytes, passphrase: str) -> bytes:
    key, salt = derive_key(passphrase)   # fresh random salt every time
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data)
    return salt + encrypted              # salt prepended for self-contained payload
```

A new salt is generated on every encryption call. This ensures that encrypting the same data twice with the same passphrase produces different ciphertexts — preventing correlation attacks across soul file backups.

Fernet itself provides authenticated encryption (AES-128-CBC + HMAC-SHA256), so any tampering with the ciphertext will be detected during decryption.

## Decryption Flow

```python
def decrypt_data(encrypted: bytes, passphrase: str) -> bytes:
    salt = encrypted[:_SALT_LENGTH]       # extract the prepended salt
    ciphertext = encrypted[_SALT_LENGTH:]
    key, _ = derive_key(passphrase, salt=salt)
    fernet = Fernet(key)
    return fernet.decrypt(ciphertext)
```

If the passphrase is wrong or the payload is corrupted, `fernet.decrypt()` raises `cryptography.fernet.InvalidToken`. This is intentional — callers should catch this exception to provide user-friendly error messages (e.g., "wrong passphrase").

## Security Properties

- **Confidentiality**: AES-128-CBC via Fernet
- **Integrity/Authenticity**: HMAC-SHA256 via Fernet (tamper-evident)
- **Passphrase hardening**: PBKDF2 at 480,000 iterations
- **Salt uniqueness**: Fresh random 16-byte salt per encryption
- **Self-contained payload**: No external state needed for decryption

## Known Gaps

No TODOs or FIXMEs are present. One forward concern: the 480,000 iteration count is hardcoded as a module-level constant `_ITERATIONS`. If NIST raises guidance (e.g., to 600,000+), updating it requires a library release and re-encryption of existing soul files — there is no migration path for in-place iteration-count upgrades without decrypting and re-encrypting.