# export/unpack.py — Load a SoulConfig from a .soul zip archive.
# Updated: v0.2.2 — Added general_events.json to memory tier extraction.
#   v0.2.0 — Added self_model.json to memory tier extraction.
#   Returns full memory data including self_model alongside the config.

from __future__ import annotations

import io
import json
import zipfile

from soul_protocol.types import SoulConfig


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
        for tier_name in ["core", "episodic", "semantic", "procedural", "graph", "self_model", "general_events"]:
            mem_path = f"memory/{tier_name}.json"
            if mem_path in zf.namelist():
                memory_data[tier_name] = json.loads(zf.read(mem_path))

    config = SoulConfig.model_validate(payload)
    return config, memory_data
