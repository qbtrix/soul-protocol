# soul_file.py — Pack and unpack .soul files (zip archives) for the core layer.
# Created: v0.4.0 — Minimal .soul file format: manifest.json, identity.json,
# and memory/{layer}.json entries. No dependency on opinionated modules.

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from .identity import Identity
from .manifest import Manifest
from .memory import DictMemoryStore, MemoryEntry, MemoryStore


def pack_soul(
    identity: Identity,
    memory_store: MemoryStore,
    *,
    manifest: dict[str, Any] | None = None,
) -> bytes:
    """Pack a soul into a .soul file (zip archive).

    The archive layout::

        soul.zip
        +-- manifest.json
        +-- identity.json
        +-- memory/
            +-- {layer_name}.json   # one file per layer

    Args:
        identity: The soul's identity.
        memory_store: The memory store to serialize.
        manifest: Optional extra fields to merge into the manifest.

    Returns:
        The zip archive as raw bytes.
    """
    buf = io.BytesIO()

    # Collect layers and their entries
    layer_names = memory_store.layers()
    layer_data: dict[str, list[dict[str, Any]]] = {}
    for layer_name in layer_names:
        entries = memory_store.recall(layer_name, limit=999_999)
        layer_data[layer_name] = [entry.model_dump(mode="json") for entry in entries]

    # Build manifest
    manifest_model = Manifest(
        soul_id=identity.id,
        soul_name=identity.name,
        created=identity.created_at,
        stats={
            "total_memories": sum(len(v) for v in layer_data.values()),
            "layers": layer_names,
        },
    )
    if manifest:
        for key, value in manifest.items():
            if hasattr(manifest_model, key):
                setattr(manifest_model, key, value)
            else:
                manifest_model.stats[key] = value

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # manifest.json
        zf.writestr(
            "manifest.json",
            manifest_model.model_dump_json(indent=2),
        )

        # identity.json
        zf.writestr(
            "identity.json",
            identity.model_dump_json(indent=2),
        )

        # memory/{layer}.json
        for layer_name, entries in layer_data.items():
            zf.writestr(
                f"memory/{layer_name}.json",
                json.dumps(entries, indent=2, default=str),
            )

    return buf.getvalue()


def unpack_soul(data: bytes) -> tuple[Identity, dict[str, list[dict[str, Any]]]]:
    """Unpack a .soul file.

    Args:
        data: Raw bytes of a .soul zip archive.

    Returns:
        A tuple of (Identity, layers_dict) where layers_dict maps
        layer names to lists of raw memory entry dicts.

    Raises:
        ValueError: If the archive is missing required files.
    """
    buf = io.BytesIO(data)
    layers: dict[str, list[dict[str, Any]]] = {}

    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()

        # identity.json is required
        if "identity.json" not in names:
            raise ValueError("Invalid .soul file: missing identity.json")

        identity_raw = json.loads(zf.read("identity.json"))
        identity = Identity.model_validate(identity_raw)

        # Read all memory/{layer}.json files
        for name in names:
            if name.startswith("memory/") and name.endswith(".json"):
                layer_name = name[len("memory/") : -len(".json")]
                if layer_name:
                    layer_raw = json.loads(zf.read(name))
                    if isinstance(layer_raw, list):
                        layers[layer_name] = layer_raw

    return identity, layers


def unpack_to_container(
    data: bytes,
) -> tuple[Identity, DictMemoryStore]:
    """Unpack a .soul file into an Identity and a populated DictMemoryStore.

    Convenience wrapper around ``unpack_soul`` that hydrates memory entries
    into a usable DictMemoryStore.

    Args:
        data: Raw bytes of a .soul zip archive.

    Returns:
        A tuple of (Identity, DictMemoryStore).
    """
    identity, layers = unpack_soul(data)
    store = DictMemoryStore()

    for layer_name, entries_raw in layers.items():
        for entry_dict in entries_raw:
            entry = MemoryEntry.model_validate(entry_dict)
            store.store(layer_name, entry)

    return identity, store
