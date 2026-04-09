# soulspec.py — SoulSpec format importer/exporter (soulspec.org)
# Created: 2026-03-23 — Import from SoulSpec directory (SOUL.md, IDENTITY.md,
#   STYLE.md, soul.json) and export back. Maps SoulSpec fields to DSP Soul
#   objects: name -> identity, SOUL.md -> core memory persona, IDENTITY.md ->
#   identity metadata, STYLE.md -> procedural memory, traits -> OCEAN if mappable.

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from soul_protocol.runtime.types import (
    MemoryType,
)

if TYPE_CHECKING:
    from soul_protocol.runtime.soul import Soul

logger = logging.getLogger(__name__)

# Known trait names that map directly to OCEAN dimensions
_OCEAN_TRAIT_MAP: dict[str, str] = {
    "openness": "openness",
    "open": "openness",
    "curiosity": "openness",
    "creative": "openness",
    "conscientiousness": "conscientiousness",
    "conscientious": "conscientiousness",
    "organized": "conscientiousness",
    "disciplined": "conscientiousness",
    "extraversion": "extraversion",
    "extraverted": "extraversion",
    "extroversion": "extraversion",
    "extroverted": "extraversion",
    "sociable": "extraversion",
    "agreeableness": "agreeableness",
    "agreeable": "agreeableness",
    "friendly": "agreeableness",
    "cooperative": "agreeableness",
    "neuroticism": "neuroticism",
    "neurotic": "neuroticism",
    "anxious": "neuroticism",
    "emotional_stability": "neuroticism",
}


def _map_traits_to_ocean(traits: dict[str, Any]) -> dict[str, float]:
    """Try to map arbitrary trait names to OCEAN dimensions.

    Returns a dict of OCEAN dimension -> float value (0.0 to 1.0).
    Only includes dimensions that could be confidently mapped.
    """
    ocean: dict[str, float] = {}
    for key, value in traits.items():
        normalized = key.lower().strip().replace(" ", "_").replace("-", "_")
        if normalized in _OCEAN_TRAIT_MAP:
            dimension = _OCEAN_TRAIT_MAP[normalized]
            if isinstance(value, (int, float)):
                # Clamp to 0.0-1.0 range
                if value > 1.0:
                    value = value / 100.0  # Assume 0-100 scale
                ocean[dimension] = max(0.0, min(1.0, float(value)))
            elif isinstance(value, str):
                # Try to parse string values
                level_map = {
                    "very low": 0.1,
                    "low": 0.25,
                    "below average": 0.35,
                    "average": 0.5,
                    "moderate": 0.5,
                    "medium": 0.5,
                    "above average": 0.65,
                    "high": 0.75,
                    "very high": 0.9,
                }
                if value.lower() in level_map:
                    ocean[dimension] = level_map[value.lower()]
    return ocean


def _extract_name_from_identity_md(content: str) -> str | None:
    """Extract a name from IDENTITY.md content (first heading or 'Name:' field)."""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line.lower().startswith("name:"):
            return line.split(":", 1)[1].strip()
    return None


def _extract_metadata_from_identity_md(content: str) -> dict[str, str]:
    """Extract key-value metadata from IDENTITY.md."""
    metadata: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, value = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            if key and value:
                metadata[key] = value
    return metadata


class SoulSpecImporter:
    """Import and export SoulSpec format (soulspec.org).

    SoulSpec uses a directory structure with:
    - SOUL.md: Personality description / persona markdown
    - IDENTITY.md: Name, role, backstory
    - STYLE.md: Communication style guidelines
    - soul.json: Structured metadata (name, traits, etc.)
    """

    @staticmethod
    async def from_directory(path: str | Path) -> Soul:
        """Read a SoulSpec directory and create a Soul.

        Expected directory contents:
        - soul.json (optional but recommended): structured metadata
        - SOUL.md (optional): personality / persona description
        - IDENTITY.md (optional): name, role, backstory
        - STYLE.md (optional): communication style

        At minimum, either soul.json with a 'name' field or IDENTITY.md
        with a name must be present.

        Args:
            path: Path to the SoulSpec directory.

        Returns:
            A Soul instance with mapped data.

        Raises:
            FileNotFoundError: If the directory doesn't exist.
            ValueError: If no name can be determined from the files.
        """
        from soul_protocol.runtime.soul import Soul

        dir_path = Path(path)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"SoulSpec directory not found: {dir_path}")

        # Read available files
        soul_json_data: dict[str, Any] = {}
        soul_md = ""
        identity_md = ""
        style_md = ""

        soul_json_path = dir_path / "soul.json"
        if soul_json_path.exists():
            soul_json_data = json.loads(soul_json_path.read_text(encoding="utf-8"))

        soul_md_path = dir_path / "SOUL.md"
        if soul_md_path.exists():
            soul_md = soul_md_path.read_text(encoding="utf-8").strip()

        identity_md_path = dir_path / "IDENTITY.md"
        if identity_md_path.exists():
            identity_md = identity_md_path.read_text(encoding="utf-8").strip()

        style_md_path = dir_path / "STYLE.md"
        if style_md_path.exists():
            style_md = style_md_path.read_text(encoding="utf-8").strip()

        # Determine name
        name = soul_json_data.get("name", "")
        if not name and identity_md:
            name = _extract_name_from_identity_md(identity_md) or ""
        if not name:
            raise ValueError(
                "Cannot determine soul name. Provide soul.json with 'name' "
                "or IDENTITY.md with a name heading."
            )

        # Build OCEAN from traits
        ocean: dict[str, float] | None = None
        raw_traits = soul_json_data.get("traits", {})
        if isinstance(raw_traits, dict):
            mapped = _map_traits_to_ocean(raw_traits)
            if mapped:
                ocean = mapped

        # Persona from SOUL.md
        persona = soul_md or soul_json_data.get("description", f"I am {name}.")

        # Archetype from soul.json
        archetype = soul_json_data.get("archetype", "")

        # Core values from soul.json
        values = soul_json_data.get("values", [])
        if isinstance(values, str):
            values = [v.strip() for v in values.split(",")]

        # Identity metadata from IDENTITY.md
        identity_meta = {}
        if identity_md:
            identity_meta = _extract_metadata_from_identity_md(identity_md)

        origin_story = identity_meta.get("backstory", "")
        if not origin_story:
            origin_story = identity_meta.get("background", "")

        # Communication style from STYLE.md
        communication: dict[str, str] | None = None
        if style_md:
            style_meta = _extract_metadata_from_identity_md(style_md)
            comm_fields = {}
            if "warmth" in style_meta:
                comm_fields["warmth"] = style_meta["warmth"]
            if "verbosity" in style_meta:
                comm_fields["verbosity"] = style_meta["verbosity"]
            if "humor" in style_meta or "humor_style" in style_meta:
                comm_fields["humor_style"] = style_meta.get(
                    "humor_style", style_meta.get("humor", "none")
                )
            if "emoji" in style_meta or "emoji_usage" in style_meta:
                comm_fields["emoji_usage"] = style_meta.get(
                    "emoji_usage", style_meta.get("emoji", "none")
                )
            if comm_fields:
                communication = comm_fields

        # Birth the soul
        soul = await Soul.birth(
            name=name,
            archetype=archetype,
            personality=origin_story,
            values=values if values else None,
            ocean=ocean,
            communication=communication,
            persona=persona,
        )

        # Store STYLE.md as procedural memory if present
        if style_md:
            await soul.remember(
                f"Communication style guide:\n{style_md}",
                type=MemoryType.PROCEDURAL,
                importance=7,
            )

        # Store IDENTITY.md as a semantic memory if it has content beyond name
        if identity_md and len(identity_md) > len(name) + 10:
            await soul.remember(
                f"Identity background:\n{identity_md}",
                type=MemoryType.SEMANTIC,
                importance=7,
            )

        logger.info("Imported SoulSpec from %s: name=%s", dir_path, name)
        return soul

    @staticmethod
    async def from_soul_json(data: dict[str, Any]) -> Soul:
        """Create a Soul from parsed soul.json data.

        Args:
            data: Parsed soul.json dictionary. Must contain at least 'name'.

        Returns:
            A Soul instance.

        Raises:
            ValueError: If 'name' is missing from the data.
        """
        from soul_protocol.runtime.soul import Soul

        name = data.get("name", "")
        if not name:
            raise ValueError("soul.json must contain a 'name' field.")

        # Map traits to OCEAN
        ocean: dict[str, float] | None = None
        raw_traits = data.get("traits", {})
        if isinstance(raw_traits, dict):
            mapped = _map_traits_to_ocean(raw_traits)
            if mapped:
                ocean = mapped

        persona = data.get("description", f"I am {name}.")
        archetype = data.get("archetype", "")
        values = data.get("values", [])
        if isinstance(values, str):
            values = [v.strip() for v in values.split(",")]

        soul = await Soul.birth(
            name=name,
            archetype=archetype,
            persona=persona,
            values=values if values else None,
            ocean=ocean,
        )

        # Store any extra fields as semantic memories
        extra_keys = set(data.keys()) - {"name", "description", "archetype", "values", "traits"}
        for key in sorted(extra_keys):
            val = data[key]
            if val and isinstance(val, str) and len(val) > 5:
                await soul.remember(
                    f"{key}: {val}",
                    type=MemoryType.SEMANTIC,
                    importance=5,
                )

        logger.info("Imported from soul.json: name=%s", name)
        return soul

    @staticmethod
    async def to_soulspec(soul: Soul, output_dir: str | Path) -> Path:
        """Export a Soul back to SoulSpec directory format.

        Creates:
        - soul.json: Structured metadata
        - SOUL.md: Persona / personality description
        - IDENTITY.md: Name, archetype, values, backstory
        - STYLE.md: Communication style

        Args:
            soul: The Soul to export.
            output_dir: Directory to write files into (created if needed).

        Returns:
            Path to the output directory.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Build soul.json
        personality = soul.dna.personality
        traits: dict[str, Any] = {
            "openness": personality.openness,
            "conscientiousness": personality.conscientiousness,
            "extraversion": personality.extraversion,
            "agreeableness": personality.agreeableness,
            "neuroticism": personality.neuroticism,
        }

        soul_json: dict[str, Any] = {
            "name": soul.name,
            "archetype": soul.archetype or "",
            "description": soul.get_core_memory().persona or f"I am {soul.name}.",
            "values": soul.identity.core_values,
            "traits": traits,
        }

        (out / "soul.json").write_text(
            json.dumps(soul_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # SOUL.md — persona / personality description
        persona = soul.get_core_memory().persona or f"I am {soul.name}."
        (out / "SOUL.md").write_text(
            f"# {soul.name}\n\n{persona}\n",
            encoding="utf-8",
        )

        # IDENTITY.md — structured identity
        identity_lines = [
            f"# {soul.name}",
            "",
            f"Name: {soul.name}",
        ]
        if soul.archetype:
            identity_lines.append(f"Archetype: {soul.archetype}")
        if soul.identity.origin_story:
            identity_lines.append(f"Backstory: {soul.identity.origin_story}")
        if soul.identity.core_values:
            identity_lines.append(f"Values: {', '.join(soul.identity.core_values)}")
        identity_lines.append(f"DID: {soul.did}")
        identity_lines.append("")

        (out / "IDENTITY.md").write_text(
            "\n".join(identity_lines),
            encoding="utf-8",
        )

        # STYLE.md — communication style
        comm = soul.dna.communication
        style_lines = [
            "# Communication Style",
            "",
            f"Warmth: {comm.warmth}",
            f"Verbosity: {comm.verbosity}",
            f"Humor: {comm.humor_style}",
            f"Emoji: {comm.emoji_usage}",
            "",
        ]
        (out / "STYLE.md").write_text(
            "\n".join(style_lines),
            encoding="utf-8",
        )

        logger.info("Exported SoulSpec to %s: name=%s", out, soul.name)
        return out
