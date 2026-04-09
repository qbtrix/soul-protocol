# importers/__init__.py — Format importers for Soul Protocol
# Created: 2026-03-23 — Exports SoulSpecImporter, TavernAIImporter, and
#   detect_format() for automatic format detection from file/directory paths.

from __future__ import annotations

import json
from pathlib import Path

from .soulspec import SoulSpecImporter
from .tavernai import TavernAIImporter

__all__ = [
    "SoulSpecImporter",
    "TavernAIImporter",
    "detect_format",
]


def detect_format(path: str | Path) -> str:
    """Auto-detect the format of a soul file or directory.

    Inspects the path to determine which importer should handle it.

    Detection rules:
    - Directory with soul.json, SOUL.md, IDENTITY.md, or STYLE.md -> "soulspec"
    - JSON file with {"spec": "chara_card_v2"} -> "tavernai"
    - PNG file (starts with PNG signature) -> "tavernai_png"
    - Directory with soul.json containing DSP format_version -> "soul_protocol"
    - .soul file (ZIP archive) -> "soul_protocol"
    - .json file with DSP identity/dna structure -> "soul_protocol"
    - .yaml/.yml file -> "soul_protocol"
    - .md file -> "soul_protocol"

    Args:
        path: Path to a file or directory to inspect.

    Returns:
        One of: "soulspec", "tavernai", "tavernai_png", "soul_protocol", "unknown"

    Raises:
        FileNotFoundError: If the path doesn't exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Path not found: {p}")

    # Directory detection
    if p.is_dir():
        has_soul_json = (p / "soul.json").exists()
        has_soul_md = (p / "SOUL.md").exists()
        has_identity_md = (p / "IDENTITY.md").exists()
        has_style_md = (p / "STYLE.md").exists()

        # SoulSpec uses SOUL.md, IDENTITY.md, STYLE.md alongside soul.json
        soulspec_markers = sum([has_soul_md, has_identity_md, has_style_md])

        if soulspec_markers >= 1:
            return "soulspec"

        if has_soul_json:
            # Check if soul.json looks like DSP or SoulSpec
            try:
                data = json.loads((p / "soul.json").read_text())
                if isinstance(data, dict):
                    # DSP soul.json has 'identity' and 'dna' keys
                    if "identity" in data or "dna" in data or "format_version" in data:
                        return "soul_protocol"
                    # SoulSpec soul.json has 'name' and 'traits' at top level
                    if "name" in data and ("traits" in data or "description" in data):
                        return "soulspec"
                    return "soulspec"
            except (json.JSONDecodeError, OSError):
                pass

        return "unknown"

    # File detection
    suffix = p.suffix.lower()

    if suffix == ".png":
        # Check for PNG signature
        try:
            header = p.read_bytes()[:8]
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                return "tavernai_png"
        except OSError:
            pass
        return "unknown"

    if suffix == ".json":
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict):
                if data.get("spec") == "chara_card_v2":
                    return "tavernai"
                # DSP format
                if "identity" in data or "dna" in data or "version" in data:
                    return "soul_protocol"
                # SoulSpec standalone soul.json
                if "name" in data and ("traits" in data or "description" in data):
                    return "soulspec"
        except (json.JSONDecodeError, OSError):
            pass
        return "unknown"

    if suffix == ".soul":
        return "soul_protocol"

    if suffix in (".yaml", ".yml"):
        return "soul_protocol"

    if suffix == ".md":
        return "soul_protocol"

    return "unknown"
