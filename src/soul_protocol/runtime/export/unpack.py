# export/unpack.py — Load a SoulConfig from a .soul zip archive.
# Updated: 2026-04-29 (#42) — Read the trust chain (trust_chain/chain.json)
#   and key files (keys/public.key, keys/private.key) when present. Both are
#   optional — souls predating #42 just have an empty chain. Returns the
#   chain dict under ``memory_data["trust_chain"]`` and key bytes under
#   ``memory_data["keys"]`` so the Soul layer can rehydrate cleanly.
# Updated: 2026-04-29 (#41) — Read the social tier (memory/social.json) and
#   user-defined layers (memory/custom_layers.json) when present. Both are
#   optional, so older archives without these entries keep loading cleanly.
# Updated: feat/soul-encryption — Added password parameter for decrypting encrypted
#   .soul files. Raises SoulEncryptedError without password, SoulDecryptionError on
#   wrong password. Backward compatible with unencrypted archives.
# Updated: Added dna.md reading from archive into memory_data["dna_md"].
#   v0.2.2 — Added general_events.json to memory tier extraction.
#   v0.2.0 — Added self_model.json to memory tier extraction.
#   Returns full memory data including self_model alongside the config.
# Updated: Added structured logging for archive extraction.

from __future__ import annotations

import io
import json
import logging
import zipfile

from soul_protocol.runtime.types import SoulConfig

logger = logging.getLogger(__name__)


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
                    assert password is not None  # is_encrypted == True requires password
                    return decrypt_blob(zf.read(enc_name), password)
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
            "social",  # v0.4.0 (#41)
            "graph",
            "self_model",
            "general_events",
        ]:
            mem_path = f"memory/{tier_name}.json"
            exists = (f"{mem_path}.enc" in names) if is_encrypted else (mem_path in names)
            if exists:
                tier_raw = _read(mem_path)
                memory_data[tier_name] = json.loads(tier_raw)

        # v0.4.0 (#41) — User-defined layers, keyed by layer name. Optional;
        # only present when the soul actually used a custom layer.
        custom_path = "memory/custom_layers.json"
        custom_exists = (f"{custom_path}.enc" in names) if is_encrypted else (custom_path in names)
        if custom_exists:
            memory_data["custom_layers"] = json.loads(_read(custom_path))

        # Read dna.md if present (human-readable personality snapshot)
        dna_exists = ("dna.md.enc" in names) if is_encrypted else ("dna.md" in names)
        if dna_exists:
            memory_data["dna_md"] = _read("dna.md").decode("utf-8")

        # v0.4.0 (#42) — Trust chain. Empty/absent for legacy souls — that's
        # the equivalent of an empty TrustChain so the Soul awakens cleanly.
        chain_path = "trust_chain/chain.json"
        chain_exists = (f"{chain_path}.enc" in names) if is_encrypted else (chain_path in names)
        if chain_exists:
            memory_data["trust_chain"] = json.loads(_read(chain_path))

        # v0.4.0 (#42) — Keystore (raw 32-byte Ed25519 keys). Public is
        # always optional; private is only present when ``include_keys=True``
        # was used at export time. We expose them as a flat dict so the Soul
        # layer can hand the bytes to Keystore.from_archive_files().
        keys: dict[str, bytes] = {}
        for kf in ("keys/public.key", "keys/private.key"):
            kf_exists = (f"{kf}.enc" in names) if is_encrypted else (kf in names)
            if kf_exists:
                keys[kf] = _read(kf)
        if keys:
            memory_data["keys"] = keys

    config = SoulConfig.model_validate(payload)
    logger.debug(
        "Soul unpacked: name=%s, memory_tiers=%s",
        config.identity.name,
        list(memory_data.keys()),
    )
    return config, memory_data
