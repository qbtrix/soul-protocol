# export/pack.py — Create .soul zip archives from a SoulConfig.
# Updated: v0.2.2 — Added general_events.json to memory/ directory in archives.
#   v0.2.0 — Added self_model.json to memory/ directory in archives.
#   Includes episodic, semantic, procedural, graph, self_model, and general_events tiers.

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime

from soul_protocol.dna.prompt import dna_to_markdown
from soul_protocol.types import SoulConfig, SoulManifest


async def pack_soul(
    config: SoulConfig,
    memory_data: dict | None = None,
) -> bytes:
    """Create a ``.soul`` zip archive from a ``SoulConfig``.

    The archive always contains:

    - ``manifest.json`` — archive metadata (``SoulManifest``)
    - ``soul.json`` — the complete ``SoulConfig``
    - ``dna.md`` — human-readable DNA markdown
    - ``state.json`` — current ``SoulState`` snapshot
    - ``memory/core.json`` — ``CoreMemory`` (persona + human)

    If ``memory_data`` is provided (dict from ``MemoryManager.to_dict()``),
    the archive additionally includes:

    - ``memory/episodic.json``
    - ``memory/semantic.json``
    - ``memory/procedural.json``
    - ``memory/graph.json``

    Args:
        config: The SoulConfig to archive.
        memory_data: Optional full memory state dict. If None, only core
            memory from the config is included (backward compatible).

    Returns:
        The zip archive as raw bytes.
    """
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # soul.json — full config
        soul_json = config.model_dump_json(indent=2)
        zf.writestr("soul.json", soul_json)

        # dna.md — human-readable personality blueprint
        dna_md = dna_to_markdown(config.identity, config.dna)
        zf.writestr("dna.md", dna_md)

        # state.json — current state
        state_json = config.state.model_dump_json(indent=2)
        zf.writestr("state.json", state_json)

        # memory/core.json — always-loaded core memory
        if memory_data and "core" in memory_data:
            core_json = json.dumps(memory_data["core"], indent=2, default=str)
        else:
            core_json = config.core_memory.model_dump_json(indent=2)
        zf.writestr("memory/core.json", core_json)

        # Additional memory tiers (only if memory_data provided)
        if memory_data:
            for tier_name in ["episodic", "semantic", "procedural", "graph", "self_model", "general_events"]:
                default = {} if tier_name in ("graph", "self_model") else []
                tier_data = memory_data.get(tier_name, default)
                zf.writestr(
                    f"memory/{tier_name}.json",
                    json.dumps(tier_data, indent=2, default=str),
                )

        # manifest.json — archive metadata (written last so we know contents)
        manifest = SoulManifest(
            format_version="1.0.0",
            created=config.identity.born,
            exported=datetime.now(),
            soul_id=config.identity.did,
            soul_name=config.identity.name,
            checksum="",  # MVP: no checksum yet
            stats={
                "version": config.version,
                "lifecycle": config.lifecycle.value,
            },
        )
        manifest_json = manifest.model_dump_json(indent=2)
        zf.writestr("manifest.json", manifest_json)

    return buf.getvalue()
