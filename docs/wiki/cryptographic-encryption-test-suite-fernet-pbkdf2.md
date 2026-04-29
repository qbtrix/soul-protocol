---
{
  "title": "Cryptographic Encryption Test Suite (Fernet + PBKDF2)",
  "summary": "Test suite validating the `soul_protocol.runtime.crypto.encrypt` module, which provides passphrase-based symmetric encryption for soul data. Covers the full encrypt/decrypt roundtrip, wrong-passphrase rejection, and deterministic key derivation.",
  "concepts": [
    "Fernet encryption",
    "PBKDF2 key derivation",
    "passphrase authentication",
    "InvalidToken",
    "encrypt_data",
    "decrypt_data",
    "derive_key",
    "symmetric encryption",
    "soul archive security",
    "MAC verification"
  ],
  "categories": [
    "security",
    "cryptography",
    "testing",
    "test"
  ],
  "source_docs": [
    "7994e695fcbe6a16"
  ],
  "backlinks": null,
  "word_count": 386,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

This test suite guards the encryption utilities that protect sensitive soul data at rest. The `encrypt` module wraps Fernet symmetric encryption with PBKDF2 key derivation, ensuring that soul archives can only be read by holders of the correct passphrase.

## Why This Exists

Soul files store deeply personal companion data — memories, personality traits, relationship history. If those files were readable without authentication, any process with filesystem access could extract them. The crypto layer is the last line of defense when the `.soul` archive itself is exposed (e.g., on a shared drive or cloud storage).

## Test Structure

### Roundtrip Correctness

```python
def test_encrypt_decrypt_roundtrip():
    plaintext = b"Hello, Soul Protocol! This is secret data."
    passphrase = "strong-passphrase-42"
    encrypted = encrypt_data(plaintext, passphrase)
    decrypted = decrypt_data(encrypted, passphrase)
    assert decrypted == plaintext
```

This verifies the fundamental contract: data encrypted with a passphrase can be recovered intact. The test also asserts that ciphertext differs from plaintext and is longer — catching any accidental no-op implementation.

### Wrong Passphrase Rejection

```python
def test_wrong_passphrase_fails():
    encrypted = encrypt_data(b"Secret soul data", "correct-passphrase")
    with pytest.raises(InvalidToken):
        decrypt_data(encrypted, "wrong-passphrase")
```

Fernet raises `InvalidToken` when the MAC check fails. This test prevents a regression where decryption silently returns garbage instead of raising — which would be far more dangerous than a hard failure.

### Deterministic Key Derivation

```python
def test_derive_key_deterministic():
    salt = b"fixed-salt-16byt"
    key1, salt1 = derive_key("my-passphrase", salt=salt)
    key2, salt2 = derive_key("my-passphrase", salt=salt)
    assert key1 == key2
```

PBKDF2 with a fixed salt must always produce the same key. This property is essential for portability: a soul exported on one machine must decrypt on another using only the passphrase. The test also verifies that changing the passphrase (same salt) produces a different key, preventing a scenario where key derivation ignores its input.

## Data Flow

1. `derive_key(passphrase, salt)` — PBKDF2-HMAC-SHA256 produces a Fernet-compatible 32-byte key, encoded in URL-safe base64.
2. `encrypt_data(plaintext, passphrase)` — derives a key (generating a random salt if none provided), then encrypts with `Fernet.encrypt()`.
3. `decrypt_data(ciphertext, passphrase)` — re-derives the key using the embedded salt, then calls `Fernet.decrypt()`. Raises `InvalidToken` on any mismatch.

## Known Gaps

No explicit test covers salt storage (i.e., that the salt is embedded in the ciphertext blob and recovered correctly). The roundtrip test implicitly validates this, but a dedicated test for salt extraction would make the assumption explicit.