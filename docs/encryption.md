# Encryption

Soul Protocol supports AES-256-GCM encryption for `.soul` archives,
allowing you to protect a soul's data at rest with a password.

## How It Works

When you export with `--password`, the archive is encrypted using:

- **Algorithm:** AES-256-GCM (authenticated encryption)
- **Key derivation:** scrypt (N=2¹⁴, r=8, p=1) with a random 16-byte salt
- **Nonce:** Random 12 bytes per file
- **Scope:** All files inside the `.soul` archive are encrypted *except*
  `manifest.json`, which remains readable so tools can detect that the
  archive is encrypted without needing the password.

> **Privacy note:** The manifest intentionally keeps the soul's **name**,
> **DID**, and **role** in plaintext so that tooling can index and display
> archives without decryption. If you are encrypting for privacy, be aware
> that the soul's identity header is visible — only the memory tiers,
> trust chain, and signing keys are protected by the password.

The `cryptography` Python package is required:

```bash
pip install cryptography
```

## CLI Usage

### Encrypting a soul

```bash
soul export aria.soul -o aria-secure.soul --password
```

You will be prompted to enter and confirm the password interactively.
The password never appears in your shell history.

### Reading an encrypted soul

```bash
# Inspect
soul inspect aria-secure.soul --password

# Unpack to directory
soul unpack aria-secure.soul -d ./aria/ --password
```

### Error handling

If you try to open an encrypted `.soul` file without `--password`,
the CLI prints a friendly message:

```
Error: This .soul file is encrypted. Pass --password to decrypt it.
```

A wrong password produces:

```
Error: Wrong password — decryption failed. Check your password and try again.
```

## Python API

```python
from soul_protocol.runtime.soul import Soul

# Export with encryption
soul = await Soul.birth("Aria")
await soul.export("aria.soul", password="my-secret")

# Awaken with decryption
soul = await Soul.awaken("aria.soul", password="my-secret")
```

### Exception handling

```python
from soul_protocol.runtime.exceptions import (
    SoulEncryptedError,
    SoulDecryptionError,
)

try:
    soul = await Soul.awaken("aria.soul")
except SoulEncryptedError:
    print("This soul is encrypted — provide a password.")
except SoulDecryptionError:
    print("Wrong password.")
```

## Archive Format

An encrypted `.soul` file is a standard ZIP archive containing:

| File | Encrypted? | Description |
|------|-----------|-------------|
| `manifest.json` | No | Contains `"encrypted": true`, format version, soul name |
| `soul.json.enc` | Yes | Soul configuration (identity, DNA, state) |
| `memory.json.enc` | Yes | All memory tiers |
| `trust_chain.json.enc` | Yes | Trust chain entries |
| `keys.json.enc` | Yes | Signing keys (when `include_keys=True`) |

Each `.enc` file stores: `salt (16B) || nonce (12B) || ciphertext+tag`.
