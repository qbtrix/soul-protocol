---
{
  "title": "AES-256-GCM Encryption for Soul Archive Files",
  "summary": "`crypto.py` provides password-based encryption and decryption for `.soul` file contents using AES-256-GCM authenticated encryption with scrypt key derivation. Each call to `encrypt_blob` generates fresh randomness, ensuring that the same password encrypts the same content to a different ciphertext every time.",
  "concepts": [
    "AES-256-GCM",
    "scrypt",
    "key derivation",
    "encrypt_blob",
    "decrypt_blob",
    "derive_key",
    "authenticated encryption",
    "soul encryption",
    "password-based encryption",
    "InvalidTag",
    "OWASP"
  ],
  "categories": [
    "security",
    "encryption",
    "export",
    "cryptography"
  ],
  "source_docs": [
    "469854d2bdaf00a5"
  ],
  "backlinks": null,
  "word_count": 389,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Soul archives contain deeply personal data — personality traits, conversation memories, emotional state. At rest on disk (or in cloud storage), that data should be unreadable to anyone without the password. `crypto.py` implements that protection layer.

The design is deliberately conservative. It uses only well-vetted, audited primitives from the `cryptography` library and follows OWASP recommendations for password-based encryption.

## Cryptographic Design

### Key Derivation: scrypt

```python
_SCRYPT_N = 2**17  # ~128 MiB memory
_SCRYPT_R = 8
_SCRYPT_P = 1
```

Scrypt is a memory-hard KDF — deriving a key requires ~128 MiB of RAM. This makes brute-force attacks with GPU farms expensive: each guess requires 128 MiB, so a 1000-GPU rig is limited to a few thousand guesses/second instead of billions. OWASP recommends these parameters for high-security applications.

### Encryption: AES-256-GCM

```python
aesgcm = AESGCM(key)
ciphertext = aesgcm.encrypt(nonce, data, None)
```

AES-GCM is an authenticated encryption scheme — it provides both confidentiality (AES) and integrity (GCM authentication tag). If any byte of the ciphertext is tampered with, decryption will fail with an `InvalidTag` error rather than returning corrupted plaintext. This prevents bit-flip attacks.

### Wire Format

```
encrypt_blob output: [salt 16B][nonce 12B][ciphertext + GCM tag 16B]
```

Salt and nonce are prepended to the ciphertext so `decrypt_blob` can extract them without any side-channel. The 16-byte salt ensures each password produces a unique derived key. The 12-byte nonce is the AES-GCM standard.

### Fresh Randomness Per Call

Both salt and nonce are generated with `os.urandom()` on each `encrypt_blob()` call. Even if you encrypt identical plaintext with the same password twice, the output is different each time. This prevents ciphertext correlation attacks.

## Error Handling

```python
try:
    return aesgcm.decrypt(nonce, ciphertext, None)
except InvalidTag as exc:
    raise ValueError("Decryption failed — wrong password or corrupted data") from exc
```

`cryptography.exceptions.InvalidTag` is caught specifically (not `Exception`) and re-raised as `ValueError`. The unpack layer then wraps this as `SoulDecryptionError`. The error message deliberately does not distinguish between "wrong password" and "corrupted data" — revealing which one could help an attacker.

## Known Gaps

- No key stretching beyond scrypt. If `cryptography` ever deprecates scrypt, migration would require re-encrypting all soul files.
- The manifest (`manifest.json`) is intentionally left unencrypted so tools can inspect basic metadata without a password. This means the soul's name and creation date are visible to anyone with the file.