# export/pack.py — Create .soul zip archives from a SoulConfig.
# Updated: 2026-04-29 (#42) — Trust chain is written to ``trust_chain/chain.json``
#   (canonical Pydantic-serialized form) plus ``trust_chain/entry_NNN.json`` for
#   human inspection. Soul keys are persisted under ``keys/`` — public.key always,
#   private.key only when ``include_keys=True``. Trust chain + key files are
#   passed in via ``trust_chain_data`` and ``key_files`` so this module stays
#   ignorant of the runtime managers.
# Updated: 2026-04-29 (#41) — Added social tier and custom_layers to the
#   archive. Social entries get their own ``memory/social.json`` so legacy
#   flat-layout readers see them. Custom layers (any user-defined layer
#   name) round-trip via ``memory/custom_layers.json`` keyed by layer name.
# Updated: feat/soul-encryption — Added optional password parameter for AES-256-GCM
#   encryption at rest. Encrypted files use .enc extension, manifest stays readable.
# Updated: v0.2.2 — Added general_events.json to memory/ directory in archives.
#   v0.2.0 — Added self_model.json to memory/ directory in archives.
#   Includes episodic, semantic, procedural, graph, self_model, and general_events tiers.
# Updated: Added structured logging for archive creation.

from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime

from soul_protocol.runtime.dna.prompt import dna_to_markdown
from soul_protocol.runtime.types import SoulConfig, SoulManifest

logger = logging.getLogger(__name__)


async def pack_soul(
    config: SoulConfig,
    memory_data: dict | None = None,
    *,
    password: str | None = None,
    trust_chain_data: dict | None = None,
    key_files: dict[str, bytes] | None = None,
) -> bytes:
    """Create a ``.soul`` zip archive from a ``SoulConfig``.

    The archive always contains:

    - ``manifest.json`` — archive metadata (``SoulManifest``), always unencrypted
    - ``soul.json`` — the complete ``SoulConfig``
    - ``dna.md`` — human-readable DNA markdown
    - ``state.json`` — current ``SoulState`` snapshot
    - ``memory/core.json`` — ``CoreMemory`` (persona + human)

    Optionally:

    - ``trust_chain/chain.json`` + ``trust_chain/entry_NNN.json`` (#42)
    - ``keys/public.key`` + ``keys/private.key`` (#42 — private only when included)

    When ``password`` is provided, all files except ``manifest.json`` are
    encrypted with AES-256-GCM. Encrypted files get a ``.enc`` extension.

    Args:
        config: The SoulConfig to archive.
        memory_data: Optional full memory state dict.
        password: Optional password for encryption. If None, no encryption.
        trust_chain_data: Optional Pydantic-serialized TrustChain dict
            (i.e. TrustChain.model_dump(mode='json')). When present, the
            chain is written to ``trust_chain/chain.json`` and each entry
            to ``trust_chain/entry_NNN.json``.
        key_files: Optional ``{filename: bytes}`` keystore mapping. The
            caller (Soul.export) decides whether to include the private
            key. Empty/None skips the keys/ directory entirely.

    Returns:
        The zip archive as raw bytes.
    """
    encrypting = password is not None

    encrypt_fn = None
    if encrypting:
        from soul_protocol.runtime.export.crypto import encrypt_blob

        encrypt_fn = encrypt_blob

    def _write(zf: zipfile.ZipFile, name: str, content: str | bytes) -> None:
        """Write a file into the ZIP, encrypting if a password was given."""
        raw = content.encode("utf-8") if isinstance(content, str) else content
        if encrypting and encrypt_fn is not None:
            assert password is not None  # encrypting == True guarantees this
            zf.writestr(f"{name}.enc", encrypt_fn(raw, password))
        else:
            zf.writestr(name, raw)

    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # soul.json — full config
        _write(zf, "soul.json", config.model_dump_json(indent=2))

        # dna.md — human-readable personality blueprint
        _write(zf, "dna.md", dna_to_markdown(config.identity, config.dna))

        # state.json — current state
        _write(zf, "state.json", config.state.model_dump_json(indent=2))

        # memory/core.json — always-loaded core memory
        if memory_data and "core" in memory_data:
            core_json = json.dumps(memory_data["core"], indent=2, default=str)
        else:
            core_json = config.core_memory.model_dump_json(indent=2)
        _write(zf, "memory/core.json", core_json)

        # Additional memory tiers (only if memory_data provided)
        if memory_data:
            for tier_name in [
                "episodic",
                "semantic",
                "procedural",
                "social",  # v0.4.0 (#41) — relationship layer
                "graph",
                "self_model",
                "general_events",
            ]:
                default = {} if tier_name in ("graph", "self_model") else []
                tier_data = memory_data.get(tier_name, default)
                _write(
                    zf,
                    f"memory/{tier_name}.json",
                    json.dumps(tier_data, indent=2, default=str),
                )
            # v0.4.0 (#41) — Custom layer entries keyed by layer name. Only
            # written when at least one custom layer has data, so default
            # souls keep the pre-#41 archive shape.
            custom_layers = memory_data.get("custom_layers") or {}
            if any(custom_layers.values()):
                _write(
                    zf,
                    "memory/custom_layers.json",
                    json.dumps(custom_layers, indent=2, default=str),
                )

        # v0.4.0 (#42) — Trust chain. Skipped entirely when no chain or empty
        # entries — keeps legacy souls free of trust_chain/.
        if trust_chain_data and trust_chain_data.get("entries"):
            _write(
                zf,
                "trust_chain/chain.json",
                json.dumps(trust_chain_data, indent=2, default=str),
            )
            for entry in trust_chain_data.get("entries", []):
                seq = entry.get("seq", 0)
                _write(
                    zf,
                    f"trust_chain/entry_{seq:03d}.json",
                    json.dumps(entry, indent=2, default=str),
                )

        # v0.4.0 (#42) — Keystore. public.key always when present; private.key
        # only when the caller (Soul.export) opted into include_keys=True.
        if key_files:
            for fname, data_bytes in key_files.items():
                _write(zf, fname, data_bytes)

        # manifest.json — archive metadata (always unencrypted, written last)
        manifest = SoulManifest(
            format_version="1.0.0",
            created=config.identity.born,
            exported=datetime.now(),
            soul_id=config.identity.did,
            soul_name=config.identity.name,
            checksum="",  # MVP: no checksum yet
            encrypted=encrypting,
            stats={
                "version": config.version,
                "lifecycle": config.lifecycle.value,
                "role": config.identity.role,
            },
        )
        manifest_json = manifest.model_dump_json(indent=2)
        zf.writestr("manifest.json", manifest_json)

    data = buf.getvalue()
    logger.debug(
        "Soul packed: name=%s, size=%d bytes",
        config.identity.name,
        len(data),
    )
    return data
