---
{
  "title": "Test Suite for Soul File Encryption",
  "summary": "Validates the full encryption stack for .soul files, from low-level blob crypto primitives through pack/unpack pipeline integration to the high-level Soul.export() and Soul.awaken() API. Covers round-trips, wrong-password errors, backward compatibility with unencrypted files, and manifest readability without a password.",
  "concepts": [
    "encryption",
    "soul file",
    "password",
    "AES",
    "salt",
    "SoulDecryptionError",
    "SoulEncryptedError",
    "pack soul",
    "unpack soul",
    "backward compatibility",
    "manifest",
    "at-rest encryption"
  ],
  "categories": [
    "testing",
    "security",
    "encryption",
    "soul-protocol",
    "test"
  ],
  "source_docs": [
    "01222f1877e14914"
  ],
  "backlinks": null,
  "word_count": 490,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_encryption.py` tests the at-rest encryption feature for `.soul` files. A soul file can contain intimate memories, personal history, and identity data — encrypting it at rest ensures that even if the file is stolen, it cannot be read without the password. The tests are organized in three layers, mirroring the implementation's own layering.

## Architecture: Three Encryption Layers

### Layer 1 — Low-level blob crypto (`TestCryptoBlob`)
Tests `encrypt_blob(data, password)` / `decrypt_blob(data, password)` directly. These are the primitive operations that all higher layers build on.

Key invariants:
- **Round-trip** — `decrypt(encrypt(data, pw), pw) == data`. Fundamental correctness.
- **Wrong password raises** — uses `ValueError` to signal bad credentials without leaking timing information.
- **Corrupted data raises** — truncated or modified ciphertext must fail, not silently return garbage.
- **Different salts produce different ciphertext** — confirms that each encryption call generates a fresh random salt, preventing the same plaintext from producing the same ciphertext across calls (rainbow table resistance).
- **Empty plaintext** — must encrypt and decrypt to `b""` without crashing.

```python
def test_different_salts_produce_different_ciphertext(self):
    pt = b"same plaintext"
    e1 = encrypt_blob(pt, "password")
    e2 = encrypt_blob(pt, "password")
    assert e1 != e2  # random salt per call
```

### Layer 2 — Pack/unpack pipeline (`TestPackUnpackEncryption`)
Tests `pack_soul()` / `unpack_soul()` with encryption at the `.soul` zip archive level. Async tests reflect I/O-bound nature of file operations.

Critical tests:
- **Encrypted round-trip with memory data** — ensures memory contents survive the full pack→unpack cycle with encryption.
- **No password on encrypted file raises `SoulEncryptedError`** — without this, users get an opaque `BadZipFile` exception, which gives no useful debugging info.
- **Wrong password raises `SoulDecryptionError`** — distinct from "no password" so callers can present the right error message.
- **Unencrypted backward compat** — old `.soul` files without encryption must still open without a password, preserving compatibility with existing archives.
- **Manifest readable without password** — the `manifest.json` inside the zip is NOT encrypted, so tools can inspect identity/version metadata without credentials.
- **Encrypted files have `.enc` extension** — internal zip entries for encrypted content use `.enc` suffixes, making encrypted vs. unencrypted entries distinguishable by inspection.

### Layer 3 — Soul API integration (`TestSoulEncryptionIntegration`)
Tests `Soul.export(password=...)` and `Soul.awaken(path, password=...)` end-to-end.

```python
async def test_export_and_awaken_with_password(tmp_path):
    soul = await Soul.birth("Aria")
    await soul.export(str(path), password="my-secret")
    restored = await Soul.awaken(str(path), password="my-secret")
    assert restored.name == "Aria"
```

- `test_awaken_encrypted_bytes` — confirms that in-memory bytes (not just file paths) can be awakened with a password.
- `test_export_without_password_backward_compat` — no password → no encryption, for users who don't need it.

## Fixtures

- `config()` — minimal `SoulConfig` with identity for a soul named "Aria".
- `memory_data()` — representative memory dict with episodic, semantic, procedural, and graph entries. Ensures that non-trivial memory contents survive encrypted round-trips.

## Known Gaps

The file header notes a precision fix: `test_awaken_encrypted_wrong_password` previously caught `(SoulDecryptionError, Exception)` as a broad fallback but was tightened to only `SoulDecryptionError`. This is important — catching bare `Exception` would mask unrelated errors. No remaining TODOs.
