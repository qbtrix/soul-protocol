# export/unpack.py — Load a SoulConfig from a .soul zip archive.
# Updated: Added structured logging for archive extraction.

from __future__ import annotations

import io
import json
import logging
import zipfile

logger = logging.getLogger(__name__)

from soul_protocol.runtime.types import SoulConfig


async def unpack_soul(data: bytes) -> tuple[SoulConfig, dict]:
    """Load a ``SoulConfig`` and memory data from a ``.soul`` zip archive.

    Reads the ``soul.json`` entry from the archive and validates it.
    If the archive contains memory tier files (``memory/episodic.json``,
    etc.), those are loaded into a dict keyed by tier name.

    Args:
        data: Raw bytes of the zip archive (as produced by ``pack_soul``).

    Returns:
        A tuple of (SoulConfig, memory_data). memory_data is a dict that
        may contain keys: "core", "episodic", "semantic", "procedural",
        "graph". If no memory files are present, returns an empty dict.

    Raises:
        KeyError: If the archive does not contain ``soul.json``.
        pydantic.ValidationError: If the JSON does not match the schema.
    """
    buf = io.BytesIO(data)

    memory_data: dict = {}

    with zipfile.ZipFile(buf, "r") as zf:
        raw = zf.read("soul.json")
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
            if mem_path in zf.namelist():
                memory_data[tier_name] = json.loads(zf.read(mem_path))

        # Read dna.md if present (human-readable personality snapshot)
        if "dna.md" in zf.namelist():
            memory_data["dna_md"] = zf.read("dna.md").decode("utf-8")

    config = SoulConfig.model_validate(payload)
    logger.debug(
        "Soul unpacked: name=%s, memory_tiers=%s",
        config.identity.name,
        list(memory_data.keys()),
    )
    return config, memory_data
