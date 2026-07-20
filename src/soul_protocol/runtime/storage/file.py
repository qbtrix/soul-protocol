# storage/file.py — FileStorage backend persisting souls to the local filesystem.
# Updated: 2026-07-12 (#282) — Crash-safe saves via temp-dir + fsync + atomic
#   replace. Added load-time .bak recovery: when the canonical path is missing
#   but a sibling .bak exists, the loader auto-promotes it. save_soul_flat()
#   merges files into the existing directory to preserve user files.
# Updated: 2026-04-29 (#42) — Trust chain + keystore land alongside the soul.
#   ``trust_chain/chain.json`` and per-entry ``trust_chain/entry_NNN.json`` are
#   written when the chain has any entries. ``keys/public.key`` is always
#   written when present; ``keys/private.key`` is written only when the
#   caller (Soul.save / Soul.save_local) opts in via include_keys=True.
# Updated: 2026-04-29 (#41) — Layered + domain-aware on-disk layout. Default
#   souls (every entry domain="default", only built-in layers) keep the
#   pre-#41 flat layout (memory/episodic.json + memory/semantic.json + ...).
#   Souls that use a non-default domain or any custom layer write a NESTED
#   layout: memory/<layer>/<domain>/entries.json, plus the full memory data
#   in memory/_runtime.json (so the runtime can rehydrate without scanning
#   the tree). On load, presence of subdirectories under memory/ flips the
#   loader into nested mode; otherwise it reads the flat tier files. Adds
#   social.json to the flat tier file list.
# Updated: Added structured logging for save/load operations.

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import warnings
from pathlib import Path

from soul_protocol.runtime.dna.prompt import dna_to_markdown
from soul_protocol.runtime.types import SoulConfig

logger = logging.getLogger(__name__)

DEFAULT_SOUL_DIR: Path = Path.home() / ".soul"


def _backup_path(path: Path) -> Path:
    """Return the sibling backup path used for crash recovery."""
    return path.with_name(f"{path.name}.bak")


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _fsync_directory(path: Path) -> None:
    """Best-effort fsync for directory metadata.

    Windows does not support opening directories with os.open(), so this
    is a no-op on win32.  On POSIX systems it ensures the directory entry
    changes (renames, new files) have been flushed to stable storage.
    """
    if os.name == "nt":
        return
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_tree(path: Path) -> None:
    """Best-effort fsync of all files and directory metadata under ``path``."""
    for child in path.rglob("*"):
        if child.is_file():
            try:
                with child.open("rb") as f:
                    os.fsync(f.fileno())
            except OSError:
                logger.debug("Could not fsync file during soul save: %s", child)
    for child in sorted((p for p in path.rglob("*") if p.is_dir()), reverse=True):
        _fsync_directory(child)
    _fsync_directory(path)


def _replace_with_backup(source: Path, target: Path, *, keep_backup: bool) -> None:
    """Replace ``target`` with ``source`` while preserving the old target first.

    Safety invariant: at every point during this function, at least one
    complete copy of the data (target or .bak) exists on disk, so a
    power loss at any step leaves a recoverable state.
    """
    backup = _backup_path(target)
    target_was_backed_up = False

    # Only remove a stale .bak when the target ALSO exists — if the
    # target is missing the .bak may be the ONLY surviving copy from a
    # previous interrupted swap.
    if backup.exists() and target.exists():
        _remove_path(backup)

    if target.exists():
        os.replace(target, backup)
        target_was_backed_up = True
        _fsync_directory(target.parent)

    try:
        os.replace(source, target)
    except Exception:
        if target_was_backed_up and not target.exists() and backup.exists():
            os.replace(backup, target)
        raise

    _fsync_directory(target.parent)

    if target_was_backed_up and not keep_backup:
        _remove_path(backup)
        _fsync_directory(target.parent)


def _recover_backup(path: Path) -> bool:
    """Promote a sibling ``.bak`` if the canonical path is missing.

    Returns True if recovery was performed.  This closes the power-loss
    gap in ``_replace_with_backup``: between the target→.bak rename and
    the source→target rename, the canonical path doesn't exist.  If the
    process dies in that window the .bak holds the only good copy.  This
    function is called at load time to recover from that state.

    Race-safe: if two loaders race, the second one will see
    ``FileNotFoundError`` from ``os.replace`` because the first already
    moved the backup.  We catch that and return True if the canonical
    path now exists (meaning another process did the recovery for us).
    """
    if path.exists():
        return False
    backup = _backup_path(path)
    if backup.exists():
        try:
            os.replace(backup, path)
        except FileNotFoundError:
            # Another process already promoted the backup.
            if path.exists():
                return True
            return False
        _fsync_directory(path.parent)
        logger.info("Recovered soul from backup: %s -> %s", backup, path)
        return True
    return False


def write_bytes_atomic(path: Path, data: bytes, *, keep_backup: bool = True) -> None:
    """Write bytes via temp file + fsync + atomic replace.

    For a single file, ``os.replace(temp, target)`` is atomic on its own:
    the path always resolves to old or new, never missing.  If
    ``keep_backup`` is True, we *copy* (not move) the previous version to
    ``.bak`` **before** the replace so there is no absent-path window.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        # Copy (not move) old file to .bak before the atomic replace so
        # the canonical path is never absent.
        if keep_backup and path.exists():
            backup = _backup_path(path)
            import shutil

            shutil.copy2(path, backup)

        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    except Exception:
        _remove_path(tmp_path)
        raise


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

    .. note::

        This function does **not** perform crash recovery.  If the soul
        directory vanished mid-swap, the ``.bak`` sibling is not promoted.
        Use ``load_soul_full()`` or ``Soul.awaken()`` for crash-safe
        loading — they call ``_recover_backup()`` automatically.
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


_FLAT_TIERS: list[tuple[str, object]] = [
    ("core", {}),
    ("episodic", []),
    ("semantic", []),
    ("procedural", []),
    ("social", []),
    ("graph", {}),
    ("self_model", {}),
    ("general_events", []),
]

_LAYER_TIERS = ("episodic", "semantic", "procedural", "social")


def _needs_nested_layout(memory_data: dict) -> bool:
    """Detect whether the soul has any non-default-domain entries or custom layers.

    Returns True when at least one entry uses ``domain != "default"`` or
    when a custom layer has any entries. This flips the on-disk layout
    from the flat legacy form to the nested ``<layer>/<domain>/`` form.
    """
    custom_layers = memory_data.get("custom_layers") or {}
    for entries in custom_layers.values():
        if entries:
            return True
    for tier in _LAYER_TIERS:
        for entry in memory_data.get(tier, []) or []:
            domain = entry.get("domain", "default") if isinstance(entry, dict) else "default"
            if domain and domain != "default":
                return True
    return False


def _write_soul_files(
    soul_dir: Path,
    config: SoulConfig,
    memory_data: dict,
) -> None:
    """Write all soul files to a directory (used by save_soul_full).

    Picks between the flat legacy layout (every domain is "default", only
    built-in layers) and the nested layered layout (custom domains or
    custom layers are present). Either way, ``soul.json`` / ``state.json``
    / ``dna.md`` / ``memory/core.json`` / ``memory/graph.json`` /
    ``memory/self_model.json`` / ``memory/general_events.json`` /
    ``memory/archives.json`` always live at predictable paths so loaders
    that don't care about layers keep working.

    Trust chain (#42) and keystore (#42) are written when present. The
    ``trust_chain`` and ``keys`` keys in memory_data carry the data — see
    Soul.serialize_for_storage() for the producer.
    """
    (soul_dir / "soul.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")
    (soul_dir / "state.json").write_text(config.state.model_dump_json(indent=2), encoding="utf-8")
    (soul_dir / "dna.md").write_text(dna_to_markdown(config.identity, config.dna), encoding="utf-8")

    # v0.4.0 (#42) — Trust chain on disk: chain.json + per-entry files.
    trust_chain_data = memory_data.get("trust_chain")
    if trust_chain_data and trust_chain_data.get("entries"):
        tc_dir = soul_dir / "trust_chain"
        tc_dir.mkdir(parents=True, exist_ok=True)
        (tc_dir / "chain.json").write_text(
            json.dumps(trust_chain_data, indent=2, default=str),
            encoding="utf-8",
        )
        for entry in trust_chain_data.get("entries", []):
            seq = entry.get("seq", 0)
            (tc_dir / f"entry_{seq:03d}.json").write_text(
                json.dumps(entry, indent=2, default=str),
                encoding="utf-8",
            )

    # v0.4.0 (#42) — Keystore. Pass-through whatever bytes the Soul layer
    # decides to ship (public always, private only when include_keys=True).
    key_files = memory_data.get("keys")
    if key_files:
        keys_dir = soul_dir / "keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        for fname, data in key_files.items():
            # fname is like "keys/public.key" or "keys/private.key"
            target = soul_dir / fname
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    mem_dir = soul_dir / "memory"
    mem_dir.mkdir(exist_ok=True)

    nested = _needs_nested_layout(memory_data)

    if nested:
        # Stable companion files (no domain semantics)
        for key, default in [
            ("core", {}),
            ("graph", {}),
            ("self_model", {}),
            ("general_events", []),
            ("archives", []),
        ]:
            (mem_dir / f"{key}.json").write_text(
                json.dumps(memory_data.get(key, default), indent=2, default=str),
                encoding="utf-8",
            )
        # Per-layer / per-domain entry files
        for tier in _LAYER_TIERS:
            entries = memory_data.get(tier, []) or []
            grouped: dict[str, list] = {}
            for entry in entries:
                domain = (
                    entry.get("domain", "default") if isinstance(entry, dict) else "default"
                ) or "default"
                grouped.setdefault(domain, []).append(entry)
            for domain, group in grouped.items():
                ddir = mem_dir / tier / domain
                ddir.mkdir(parents=True, exist_ok=True)
                (ddir / "entries.json").write_text(
                    json.dumps(group, indent=2, default=str),
                    encoding="utf-8",
                )
        # Custom layers
        for layer_name, entries_list in (memory_data.get("custom_layers") or {}).items():
            grouped = {}
            for entry in entries_list or []:
                domain = (
                    entry.get("domain", "default") if isinstance(entry, dict) else "default"
                ) or "default"
                grouped.setdefault(domain, []).append(entry)
            for domain, group in grouped.items():
                ddir = mem_dir / layer_name / domain
                ddir.mkdir(parents=True, exist_ok=True)
                (ddir / "entries.json").write_text(
                    json.dumps(group, indent=2, default=str),
                    encoding="utf-8",
                )
        # _layout.json marks the directory as nested so loaders know which
        # branch to take without scanning the tree first.
        (mem_dir / "_layout.json").write_text(
            json.dumps({"layout": "nested", "version": 1}, indent=2),
            encoding="utf-8",
        )
        return

    # Flat legacy layout
    for key, default in _FLAT_TIERS:
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

    # Atomic-ish directory write: build a sibling temp dir, fsync it, then
    # replace the live directory through a backup instead of deleting first.
    with tempfile.TemporaryDirectory(prefix=f".{soul_id}.tmp-", dir=base) as tmp:
        tmp_dir = Path(tmp) / soul_id
        tmp_dir.mkdir()
        _write_soul_files(tmp_dir, config, memory_data)
        _fsync_tree(tmp_dir)
        _replace_with_backup(tmp_dir, soul_dir, keep_backup=False)

    logger.debug("Soul saved (full): path=%s", soul_dir)


def _is_nested_layout(mem_dir: Path) -> bool:
    """Heuristically detect whether ``mem_dir`` uses the v0.4.0 nested layout.

    True when ``_layout.json`` says so OR when at least one tier directory
    (``episodic/``, ``semantic/``, ...) exists as a directory rather than a
    flat ``.json`` file. Allows old souls (which only have flat .json
    files) to round-trip without a separate migration step.
    """
    layout_marker = mem_dir / "_layout.json"
    if layout_marker.exists():
        try:
            data = json.loads(layout_marker.read_text(encoding="utf-8"))
            if data.get("layout") == "nested":
                return True
        except (json.JSONDecodeError, OSError):
            pass
    for tier in _LAYER_TIERS:
        if (mem_dir / tier).is_dir():
            return True
    return False


def _read_nested_layer(layer_dir: Path) -> list[dict]:
    """Read every entries.json under a layer directory and concatenate them."""
    out: list[dict] = []
    if not layer_dir.is_dir():
        return out
    for domain_dir in sorted(layer_dir.iterdir()):
        if not domain_dir.is_dir():
            continue
        entries_file = domain_dir / "entries.json"
        if not entries_file.exists():
            continue
        try:
            chunk = json.loads(entries_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(chunk, list):
            out.extend(chunk)
    return out


async def load_soul_full(path: Path) -> tuple[SoulConfig | None, dict]:
    """Load soul config + full memory data from disk.

    Args:
        path: Directory containing ``soul.json`` and optionally ``memory/``.

    Returns:
        A tuple of (SoulConfig or None, memory_data dict).
        If ``soul.json`` does not exist, returns (None, {}).
    """
    # Crash recovery: if the directory vanished mid-swap, promote .bak.
    _recover_backup(path)

    soul_json = path / "soul.json"
    if not soul_json.exists():
        return None, {}

    config = SoulConfig.model_validate_json(soul_json.read_text(encoding="utf-8"))

    memory_data: dict = {}
    mem_dir = path / "memory"
    if mem_dir.exists():
        # Companion files (no domain semantics)
        for name in ["core", "graph", "self_model", "general_events", "archives"]:
            f = mem_dir / f"{name}.json"
            if f.exists():
                memory_data[name] = json.loads(f.read_text(encoding="utf-8"))

        if _is_nested_layout(mem_dir):
            # Built-in layers stitched back from <layer>/<domain>/entries.json
            for tier in _LAYER_TIERS:
                memory_data[tier] = _read_nested_layer(mem_dir / tier)
            # Custom layers — anything else that's a directory under memory/
            custom: dict[str, list[dict]] = {}
            for child in sorted(mem_dir.iterdir()):
                if not child.is_dir() or child.name in _LAYER_TIERS:
                    continue
                custom[child.name] = _read_nested_layer(child)
            if custom:
                memory_data["custom_layers"] = custom
        else:
            # Flat legacy layout — episodic.json / semantic.json / ...
            for name in ["episodic", "semantic", "procedural", "social"]:
                f = mem_dir / f"{name}.json"
                if f.exists():
                    memory_data[name] = json.loads(f.read_text(encoding="utf-8"))

    # v0.4.0 (#42) — Trust chain. Optional; legacy souls have no chain dir.
    chain_file = path / "trust_chain" / "chain.json"
    if chain_file.exists():
        try:
            memory_data["trust_chain"] = json.loads(chain_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load trust_chain/chain.json: %s", e)

    # v0.4.0 (#42) — Keystore. public.key alone is enough to verify; private.key
    # is required to append new entries.
    keys_dir = path / "keys"
    if keys_dir.exists():
        keys: dict[str, bytes] = {}
        for kf in ("keys/public.key", "keys/private.key"):
            kp = path / kf
            if kp.exists():
                try:
                    keys[kf] = kp.read_bytes()
                except OSError as e:
                    logger.warning("Could not read %s: %s", kf, e)
        if keys:
            memory_data["keys"] = keys

    logger.debug("Soul loaded (full): path=%s", path)
    return config, memory_data


async def save_soul_flat(
    config: SoulConfig,
    memory_data: dict,
    path: Path,
) -> None:
    """Save soul config + memory to a directory WITHOUT soul_id nesting.

    Used for .soul/ project folders where the directory IS the soul.
    Writes soul files to a temp directory and then merges them into the
    existing ``path``, preserving any unmanaged files the user keeps
    alongside their soul (notes, .git/, etc.).

    Args:
        config: The SoulConfig to persist.
        memory_data: Dict as produced by MemoryManager.to_dict().
        path: Target directory (e.g. ``.soul/``). Created if missing.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    # Build all soul files in a temp sibling directory, fsync them, then
    # merge per-file into the live directory.  This preserves unmanaged
    # files the user may keep alongside the soul (notes, .git/, etc.)
    # while still giving each individual file an atomic write.
    with tempfile.TemporaryDirectory(prefix=f".{path.name}.tmp-", dir=path.parent) as tmp:
        tmp_dir = Path(tmp)
        _write_soul_files(tmp_dir, config, memory_data)
        _fsync_tree(tmp_dir)

        # Collect the set of relative paths we're about to write.
        new_files: set[Path] = set()
        for src_file in tmp_dir.rglob("*"):
            if src_file.is_file():
                new_files.add(src_file.relative_to(tmp_dir))

        # Merge: walk the temp tree and atomically replace each file
        # in the target directory.  Create subdirectories as needed.
        for rel in new_files:
            src_file = tmp_dir / rel
            dst_file = path / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src_file, dst_file)

        # Clean up stale managed files that existed in the previous save
        # but are absent from the new one (e.g. _layout.json after a
        # layout change from nested to flat).  Only touch managed
        # directories — never delete user files at the top level.
        #
        # Exception: keys/private_key and keys/private.pem are excluded
        # from pruning.  A save with include_keys=False omits these from
        # the new file set, but deleting them would destroy the user's
        # signing capability — that should require an explicit action.
        _prune_protected = {
            Path("keys") / "private_key",
            Path("keys") / "private.pem",
        }
        managed_dirs = ["memory", "trust_chain", "keys"]
        for mdir_name in managed_dirs:
            mdir = path / mdir_name
            if not mdir.is_dir():
                continue
            for old_file in list(mdir.rglob("*")):
                if not old_file.is_file():
                    continue
                rel = old_file.relative_to(path)
                if rel not in new_files and rel not in _prune_protected:
                    old_file.unlink()
            # Remove empty subdirectories left behind
            for old_dir in sorted(
                (d for d in mdir.rglob("*") if d.is_dir()),
                reverse=True,
            ):
                try:
                    old_dir.rmdir()  # only removes empty dirs
                except OSError:
                    pass

        _fsync_directory(path)
