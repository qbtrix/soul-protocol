---
{
  "title": "Soul Archive Unpacker: Loading .soul ZIP Archives",
  "summary": "`unpack_soul` deserializes a `.soul` ZIP archive back into a `(SoulConfig, memory_data)` tuple, handling both encrypted and unencrypted archives with clear error separation between missing-password and wrong-password scenarios. It is the read-side counterpart to `pack_soul` and is called on every `awaken()` operation.",
  "concepts": [
    "unpack_soul",
    "soul archive",
    "ZIP deserialization",
    "SoulEncryptedError",
    "SoulDecryptionError",
    "manifest detection",
    "memory tier extraction",
    "backward compatibility",
    "SoulConfig",
    "password handling"
  ],
  "categories": [
    "export",
    "soul-lifecycle",
    "deserialization",
    "security"
  ],
  "source_docs": [
    "05f8089b1d32820a"
  ],
  "backlinks": null,
  "word_count": 360,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`unpack_soul` is the deserialization complement of `pack_soul`. Every time a soul is loaded from disk, the raw bytes pass through this function to produce a live `SoulConfig` and the soul's memory state.

Its primary challenge is handling the encryption layer transparently: callers should not need to know whether an archive is encrypted — they just pass a password if they have one. The function detects encryption from the manifest and raises actionable errors if the password situation is wrong.

## Encryption Detection and Error Handling

```python
if "manifest.json" in names:
    manifest_raw = json.loads(zf.read("manifest.json"))
    is_encrypted = manifest_raw.get("encrypted", False)
    soul_name = manifest_raw.get("soul_name", "")

if is_encrypted and password is None:
    raise SoulEncryptedError(soul_name)
```

The manifest is always unencrypted, so this detection works without any decryption attempt. Raising `SoulEncryptedError` with the soul's name gives callers a prompt they can show directly to users: "This soul is encrypted. Please enter the password for 'PocketPaw'."

The wrong-password case is caught differently:

```python
try:
    return decrypt_blob(zf.read(enc_name), password)
except ValueError as e:
    raise SoulDecryptionError(str(e)) from e
```

AES-GCM's `InvalidTag` → `ValueError` → `SoulDecryptionError` chain ensures the caller gets a typed exception for the wrong-password scenario, distinct from the no-password scenario.

## Inner `_read` Helper

```python
def _read(name: str) -> bytes:
    if is_encrypted:
        enc_name = f"{name}.enc"
        if enc_name not in names:
            raise KeyError(f"Missing encrypted file: {enc_name}")
        return decrypt_blob(zf.read(enc_name), password)
    else:
        return zf.read(name)
```

Like `pack.py`'s `_write`, this closure abstracts the encrypted/unencrypted distinction from the rest of the unpacking logic. Adding a new file to the archive only requires one new `_read()` call.

## Memory Tier Extraction

All seven tiers (`core`, `episodic`, `semantic`, `procedural`, `graph`, `self_model`, `general_events`) are extracted conditionally — only if the file exists in the archive. This makes `unpack_soul` backward compatible with older archives that predate some tiers.

The `dna.md` file is also read into `memory_data["dna_md"]` if present, giving callers access to the human-readable personality blueprint alongside the structured data.

## Known Gaps

- No checksum verification — the manifest has a `checksum` field but it is always `""` in current archives, so unpack cannot detect silent corruption.
- `SoulConfig.model_validate(payload)` will raise `pydantic.ValidationError` on schema mismatches. There is no migration layer for older soul formats.