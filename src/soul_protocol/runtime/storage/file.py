# storage/file.py — FileStorage backend persisting souls to the local filesystem.
# Updated: Added structured logging for save/load operations.

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import warnings
from pathlib import Path

logger = logging.getLogger(__name__)

from soul_protocol.runtime.dna.prompt import dna_to_markdown
from soul_protocol.runtime.types import SoulConfig

DEFAULT_SOUL_DIR: Path = Path.home() / ".soul"


def _safe_soul_id(config: SoulConfig) -> str:
    """Extract soul_id from config and sanitize for filesystem use.

    DIDs contain colons (e.g. ``did:soul:name-hash``) which are illegal
    in Windows paths. Replace colons with underscores to make them
    cross-platform safe while keeping them human-readable.
    """
    soul_id = config.identity.did or config.identity.name
    if ".." in soul_id or "/" in soul_id or "\\" in soul_id:
        raise ValueError(f"Soul ID contains unsafe path characters: {soul_id}")
    # Colons are illegal in Windows paths — replace with underscores
    return soul_id.replace(":", "_")


class FileStorage:
    """Filesystem-backed soul storage.

    Directory layout::

        <base_dir>/
            <soul_id>/
                soul.json    — full SoulConfig serialization
                dna.md       — human-readable DNA markdown
                state.json   — current SoulState snapshot
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or DEFAULT_SOUL_DIR

    async def save(self, soul_id: str, config: SoulConfig, path: Path | None = None) -> None:
        """Save a soul to the filesystem."""
        target_dir = (path or self._base_dir) / soul_id
        target_dir.mkdir(parents=True, exist_ok=True)

        # soul.json — full config
        soul_json_path = target_dir / "soul.json"
        soul_json_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

        # dna.md — human-readable personality
        dna_md_path = target_dir / "dna.md"
        dna_md_path.write_text(dna_to_markdown(config.identity, config.dna), encoding="utf-8")

        # state.json — current state snapshot
        state_json_path = target_dir / "state.json"
        state_json_path.write_text(config.state.model_dump_json(indent=2), encoding="utf-8")

    async def load(self, soul_id: str, path: Path | None = None) -> SoulConfig | None:
        """Load a soul from the filesystem, returning ``None`` if not found."""
        target_dir = (path or self._base_dir) / soul_id
        soul_json_path = target_dir / "soul.json"

        if not soul_json_path.exists():
            return None

        raw = soul_json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return SoulConfig.model_validate(data)

    async def delete(self, soul_id: str) -> bool:
        """Delete a soul directory. Returns ``True`` if it existed."""
        target_dir = self._base_dir / soul_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
            return True
        return False

    async def list_souls(self) -> list[str]:
        """List all soul IDs stored under the base directory."""
        if not self._base_dir.exists():
            return []
        return [
            p.name
            for p in sorted(self._base_dir.iterdir())
            if p.is_dir() and (p / "soul.json").exists()
        ]


# ------------------------------------------------------------------
# Convenience functions
# ------------------------------------------------------------------


async def save_soul(config: SoulConfig, path: Path | None = None) -> None:
    """Save a soul using the default FileStorage backend.

    .. deprecated::
        Does NOT persist memory tiers. Use ``save_soul_full()`` instead.
    """
    warnings.warn(
        "save_soul() does not persist memory tiers. Use save_soul_full() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    storage = FileStorage(base_dir=path)
    soul_id = config.identity.did or config.identity.name
    await storage.save(soul_id, config, path=None)


async def load_soul(path: Path) -> SoulConfig | None:
    """Load a soul from a specific directory path.

    ``path`` should point to a directory containing ``soul.json``.
    Returns ``None`` if the file does not exist.
    """
    soul_json = path / "soul.json"
    if not soul_json.exists():
        return None

    raw = soul_json.read_text(encoding="utf-8")
    data = json.loads(raw)
    return SoulConfig.model_validate(data)


# ------------------------------------------------------------------
# Full memory persistence functions
# ------------------------------------------------------------------


def _write_soul_files(soul_dir: Path, config: SoulConfig, memory_data: dict) -> None:
    """Write all soul files to a directory (used by save_soul_full)."""
    (soul_dir / "soul.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")
    (soul_dir / "state.json").write_text(config.state.model_dump_json(indent=2), encoding="utf-8")
    (soul_dir / "dna.md").write_text(dna_to_markdown(config.identity, config.dna), encoding="utf-8")

    mem_dir = soul_dir / "memory"
    mem_dir.mkdir(exist_ok=True)

    for key, default in [
        ("core", {}),
        ("episodic", []),
        ("semantic", []),
        ("procedural", []),
        ("graph", {}),
        ("self_model", {}),
        ("general_events", []),
    ]:
        (mem_dir / f"{key}.json").write_text(
            json.dumps(memory_data.get(key, default), indent=2, default=str),
            encoding="utf-8",
        )


async def save_soul_full(
    config: SoulConfig,
    memory_data: dict,
    path: Path | None = None,
) -> None:
    """Save soul config + full memory data to disk atomically.

    Writes to a temp directory first, then moves into place to avoid
    partial writes on crash.

    Args:
        config: The SoulConfig to persist.
        memory_data: Dict as produced by MemoryManager.to_dict().
        path: Base directory. Defaults to ``~/.soul/``.
              Soul ID is always appended: ``<path>/<soul_id>/``.
    """
    soul_id = _safe_soul_id(config)
    base = path or DEFAULT_SOUL_DIR
    base.mkdir(parents=True, exist_ok=True)
    soul_dir = base / soul_id

    # Atomic write: build in temp dir, then move into place
    with tempfile.TemporaryDirectory(dir=base) as tmp:
        tmp_dir = Path(tmp) / soul_id
        tmp_dir.mkdir()
        _write_soul_files(tmp_dir, config, memory_data)

        if soul_dir.exists():
            shutil.rmtree(soul_dir)
        shutil.move(str(tmp_dir), str(soul_dir))

    logger.debug("Soul saved (full): path=%s", soul_dir)


async def load_soul_full(path: Path) -> tuple[SoulConfig | None, dict]:
    """Load soul config + full memory data from disk.

    Args:
        path: Directory containing ``soul.json`` and optionally ``memory/``.

    Returns:
        A tuple of (SoulConfig or None, memory_data dict).
        If ``soul.json`` does not exist, returns (None, {}).
    """
    soul_json = path / "soul.json"
    if not soul_json.exists():
        return None, {}

    config = SoulConfig.model_validate_json(soul_json.read_text(encoding="utf-8"))

    memory_data: dict = {}
    mem_dir = path / "memory"
    if mem_dir.exists():
        for name in [
            "core",
            "episodic",
            "semantic",
            "procedural",
            "graph",
            "self_model",
            "general_events",
        ]:
            f = mem_dir / f"{name}.json"
            if f.exists():
                memory_data[name] = json.loads(f.read_text(encoding="utf-8"))

    logger.debug("Soul loaded (full): path=%s", path)
    return config, memory_data


async def save_soul_flat(
    config: SoulConfig,
    memory_data: dict,
    path: Path,
) -> None:
    """Save soul config + memory to a directory WITHOUT soul_id nesting.

    Used for .soul/ project folders where the directory IS the soul.
    Atomic: writes to temp dir, then moves files into place.

    Args:
        config: The SoulConfig to persist.
        memory_data: Dict as produced by MemoryManager.to_dict().
        path: Target directory (e.g. ``.soul/``). Created if missing.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    # Atomic write: build in temp dir, then move individual files into place
    with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
        tmp_dir = Path(tmp) / path.name
        tmp_dir.mkdir()
        _write_soul_files(tmp_dir, config, memory_data)

        # Move files into target (preserve existing dir structure)
        for item in tmp_dir.iterdir():
            dest = path / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
