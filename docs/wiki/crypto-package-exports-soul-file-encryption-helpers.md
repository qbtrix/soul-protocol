---
{
  "title": "Crypto Package Exports: Soul File Encryption Helpers",
  "summary": "The `runtime/crypto` package's `__init__.py` re-exports `derive_key`, `encrypt_data`, and `decrypt_data` from the internal `encrypt` module, providing a clean single-import path for the symmetric encryption primitives used to protect `.soul` archive files.",
  "concepts": [
    "derive_key",
    "encrypt_data",
    "decrypt_data",
    "soul file encryption",
    "symmetric encryption",
    "crypto package",
    "KDF",
    "passphrase",
    "soul archive",
    "eternal storage"
  ],
  "categories": [
    "cryptography",
    "soul file format",
    "security",
    "runtime"
  ],
  "source_docs": [
    "7d0718aa3ad3d64e"
  ],
  "backlinks": null,
  "word_count": 461,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Soul files (`.soul` archives) may contain sensitive user data — personal facts, conversation history, emotional states, and identity information. The crypto package provides the symmetric encryption layer that protects this data at rest, whether stored locally, migrated between platforms, or uploaded to eternal storage (Arweave/IPFS). This `__init__.py` re-exports the three core encryption primitives from the internal `encrypt` submodule, providing a clean stable import path.

## Exported API

```python
from soul_protocol.runtime.crypto import derive_key, encrypt_data, decrypt_data
```

| Function | Purpose |
|----------|---------|
| `derive_key` | Derives an encryption key from a user passphrase using a KDF |
| `encrypt_data` | Symmetrically encrypts a byte payload with the derived key |
| `decrypt_data` | Decrypts a previously encrypted byte payload |

All three are thin re-exports from `soul_protocol.runtime.crypto.encrypt`. The `__init__.py` exists solely to provide a clean `from soul_protocol.runtime.crypto import ...` path without requiring callers to know the internal submodule name.

## Usage Pattern

```python
from soul_protocol.runtime.crypto import derive_key, encrypt_data, decrypt_data

# Protect a soul archive before writing to disk or eternal storage
key = derive_key(passphrase="user-supplied-passphrase")
ciphertext = encrypt_data(plaintext_bytes, key)

# Recover it later on any platform
plaintext_bytes = decrypt_data(ciphertext, key)
```

The passphrase is the sole secret. Soul-protocol does not manage or escrow encryption keys — the user is fully responsible for their passphrase. This design enables true data sovereignty: no third party can decrypt the soul file, including soul-protocol's own servers.

## Why Symmetric Encryption

Soul files use symmetric encryption (not asymmetric/public-key) because:

1. **Portability**: A single passphrase-derived key works on every platform where the soul migrates — no key pair synchronization or certificate distribution required.
2. **Simplicity**: No certificate infrastructure, key pair management, or public key exchange protocol.
3. **User ownership**: The passphrase is something the user knows and controls entirely, with no third-party escrow.

## Import Path History

The module comment notes an update to fix absolute import paths (`soul_protocol.runtime.crypto.encrypt`) after a runtime restructure. Previously, relative imports failed when the package was installed from a distribution wheel — the package structure changed during the restructure, breaking the relative path. The fix to absolute imports ensures the module works identically in editable installs and distributed environments.

## Re-export Pattern and API Stability

The `__init__.py` re-export layer provides API stability. When `encrypt.py` is internally refactored (e.g., swapping the underlying cipher), callers importing from `soul_protocol.runtime.crypto` are unaffected. Only the stable surface (`derive_key`, `encrypt_data`, `decrypt_data`) is guaranteed across versions.

## Known Gaps

The cryptographic algorithm choices (KDF type and parameters, cipher mode) are implemented in `encrypt.py` and not documented here. The security posture of the entire crypto package depends on those choices. A security audit should verify that the KDF parameters (iteration count, salt length, memory cost) meet current recommendations and that the cipher provides authenticated encryption (AEAD) to prevent ciphertext tampering.