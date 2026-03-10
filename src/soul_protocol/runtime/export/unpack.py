# export/unpack.py — Load a SoulConfig from a .soul zip archive.
# Updated: feat/soul-encryption — Added password parameter for decrypting encrypted
#   .soul files. Raises SoulEncryptedError without password, SoulDecryptionError on
#   wrong password. Backward compatible with unencrypted archives.
# Updated: Added dna.md reading from archive into memory_data["dna_md"].
#   v0.2.2 — Added general_events.json to memory tier extraction.
#   v0.2.0 — Added self_model.json to memory tier extraction.
#   Returns full memory data including self_model alongside the config.

from __future__ import annotations

import io
import json
import zipfile

from soul_protocol.runtime.types import SoulConfig


async def unpack_soul(
    data: bytes,
    *,
    password: str | None = None,
) -> tuple[SoulConfig, dict]:
    """Load a ``SoulConfig`` and memory data from a ``.soul`` zip archive.

    Reads the ``soul.json`` entry from the archive and validates it.
    If the archive contains memory tier files (``memory/episodic.json``,
    etc.), those are loaded into a dict keyed by tier name.

    When the archive is encrypted (``manifest.encrypted == true``), a
    password must be provided. Without it, ``SoulEncryptedError`` is raised.

    Args:
        data: Raw bytes of the zip archive (as produced by ``pack_soul``).
        password: Password for decrypting encrypted archives.

    Returns:
        A tuple of (SoulConfig, memory_data).

    Raises:
        KeyError: If the archive does not contain ``soul.json``.
        SoulEncryptedError: If the archive is encrypted but no password given.
        SoulDecryptionError: If the password is wrong.
        pydantic.ValidationError: If the JSON does not match the schema.
    """
    from soul_protocol.runtime.exceptions import (
        SoulDecryptionError,
        SoulEncryptedError,
    )

    buf = io.BytesIO(data)
    memory_data: dict = {}

    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()

        # Check manifest to detect encryption
        is_encrypted = False
        soul_name = ""
        if "manifest.json" in names:
            manifest_raw = json.loads(zf.read("manifest.json"))
            is_encrypted = manifest_raw.get("encrypted", False)
            soul_name = manifest_raw.get("soul_name", "")

        if is_encrypted and password is None:
            raise SoulEncryptedError(soul_name)

        def _read(name: str) -> bytes:
            """Read a file from the archive, decrypting if needed."""
            if is_encrypted:
                enc_name = f"{name}.enc"
                if enc_name not in names:
                    raise KeyError(f"Missing encrypted file: {enc_name}")
                from soul_protocol.runtime.export.crypto import decrypt_blob

                try:
                    return decrypt_blob(zf.read(enc_name), password)  # type: ignore[arg-type]
                except ValueError as e:
                    raise SoulDecryptionError(str(e)) from e
            else:
                return zf.read(name)

        raw = _read("soul.json")
        payload = json.loads(raw)

        # Extract memory tier files if present
        for tier_name in [
            "core",
            "episodic",
            "semantic",
            "procedural",
            "graph",
            "self_model",
            "general_events",
        ]:
            mem_path = f"memory/{tier_name}.json"
            exists = (
                (f"{mem_path}.enc" in names) if is_encrypted else (mem_path in names)
            )
            if exists:
                tier_raw = _read(mem_path)
                memory_data[tier_name] = json.loads(tier_raw)

        # Read dna.md if present (human-readable personality snapshot)
        dna_exists = ("dna.md.enc" in names) if is_encrypted else ("dna.md" in names)
        if dna_exists:
            memory_data["dna_md"] = _read("dna.md").decode("utf-8")

    config = SoulConfig.model_validate(payload)
    return config, memory_data
