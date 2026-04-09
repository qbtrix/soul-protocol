# tavernai.py — TavernAI Character Card V2 importer/exporter
# Created: 2026-03-23 — Import from TavernAI Character Card V2 JSON and PNG
#   (tEXt chunk with base64-encoded JSON). Export Soul back to Card V2 format.
#   Mapping: data.name -> identity, data.description + data.personality ->
#   core memory persona, data.first_mes -> procedural memory, data.tags -> metadata.

from __future__ import annotations

import base64
import json
import logging
import struct
import zlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from soul_protocol.runtime.types import MemoryType

if TYPE_CHECKING:
    from soul_protocol.runtime.soul import Soul

logger = logging.getLogger(__name__)

# Required spec identifier for Character Card V2
CHARA_CARD_V2_SPEC = "chara_card_v2"


def _validate_card_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and extract the 'data' block from a Character Card V2 structure.

    Args:
        data: The full card JSON. Must have {"spec": "chara_card_v2", "data": {...}}.

    Returns:
        The inner 'data' dict.

    Raises:
        ValueError: If the card format is invalid.
    """
    spec = data.get("spec", "")
    if spec != CHARA_CARD_V2_SPEC:
        raise ValueError(f"Not a Character Card V2: spec='{spec}', expected '{CHARA_CARD_V2_SPEC}'")

    card_data = data.get("data")
    if not isinstance(card_data, dict):
        raise ValueError("Character Card V2 missing 'data' object")

    if not card_data.get("name"):
        raise ValueError("Character Card V2 data missing 'name' field")

    return card_data


def _extract_json_from_png(png_bytes: bytes) -> dict[str, Any]:
    """Extract Character Card JSON from a PNG file's tEXt chunk.

    TavernAI stores character data in a PNG tEXt chunk with keyword 'chara'.
    The value is base64-encoded JSON.

    Args:
        png_bytes: Raw PNG file bytes.

    Returns:
        Parsed JSON dict from the tEXt chunk.

    Raises:
        ValueError: If no character data found in the PNG.
    """
    # Validate PNG signature
    png_sig = b"\x89PNG\r\n\x1a\n"
    if not png_bytes.startswith(png_sig):
        raise ValueError("Not a valid PNG file")

    offset = 8  # Skip signature
    while offset < len(png_bytes):
        if offset + 8 > len(png_bytes):
            break

        # Read chunk length and type
        chunk_len = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        chunk_type = png_bytes[offset + 4 : offset + 8]

        if chunk_type == b"tEXt":
            # tEXt chunk: keyword\0value
            chunk_data = png_bytes[offset + 8 : offset + 8 + chunk_len]
            null_idx = chunk_data.find(b"\x00")
            if null_idx >= 0:
                keyword = chunk_data[:null_idx].decode("latin-1")
                value = chunk_data[null_idx + 1 :]
                if keyword == "chara":
                    decoded = base64.b64decode(value)
                    return json.loads(decoded)

        elif chunk_type == b"iTXt":
            # iTXt chunk: keyword\0compression_flag\0compression_method\0language\0translated_keyword\0text
            chunk_data = png_bytes[offset + 8 : offset + 8 + chunk_len]
            null_idx = chunk_data.find(b"\x00")
            if null_idx >= 0:
                keyword = chunk_data[:null_idx].decode("latin-1")
                if keyword == "chara":
                    # Parse iTXt structure
                    rest = chunk_data[null_idx + 1 :]
                    if len(rest) >= 2:
                        compression_flag = rest[0]
                        # Skip compression_method, language, translated_keyword
                        rest = rest[2:]  # skip compression_flag + compression_method
                        # Find end of language tag
                        lang_end = rest.find(b"\x00")
                        if lang_end >= 0:
                            rest = rest[lang_end + 1 :]
                            # Find end of translated keyword
                            trans_end = rest.find(b"\x00")
                            if trans_end >= 0:
                                text_data = rest[trans_end + 1 :]
                                if compression_flag:
                                    text_data = zlib.decompress(text_data)
                                decoded = base64.b64decode(text_data)
                                return json.loads(decoded)

        # Move to next chunk: length(4) + type(4) + data(chunk_len) + CRC(4)
        offset += 4 + 4 + chunk_len + 4

    raise ValueError("No 'chara' tEXt/iTXt chunk found in PNG")


def _build_png_with_chara(image_bytes: bytes, card_json: dict[str, Any]) -> bytes:
    """Embed Character Card JSON into a PNG file's tEXt chunk.

    Creates a minimal PNG with the character data embedded if image_bytes
    is empty, otherwise inserts a tEXt chunk into the existing PNG.

    Args:
        image_bytes: Original PNG bytes (can be a minimal 1x1 PNG).
        card_json: The Character Card V2 JSON to embed.

    Returns:
        PNG bytes with embedded tEXt chunk.
    """
    encoded = base64.b64encode(json.dumps(card_json, ensure_ascii=False).encode("utf-8"))

    # Build tEXt chunk
    keyword = b"chara"
    text_data = keyword + b"\x00" + encoded
    chunk_type = b"tEXt"
    chunk_crc = zlib.crc32(chunk_type + text_data) & 0xFFFFFFFF
    text_chunk = (
        struct.pack(">I", len(text_data)) + chunk_type + text_data + struct.pack(">I", chunk_crc)
    )

    png_sig = b"\x89PNG\r\n\x1a\n"
    if not image_bytes.startswith(png_sig):
        raise ValueError("Not a valid PNG file for embedding")

    # Insert tEXt chunk before IEND
    iend_marker = b"IEND"
    iend_pos = image_bytes.rfind(iend_marker)
    if iend_pos < 0:
        raise ValueError("Cannot find IEND chunk in PNG")

    # Go back to the start of the IEND chunk (4 bytes for length before type)
    iend_chunk_start = iend_pos - 4
    return image_bytes[:iend_chunk_start] + text_chunk + image_bytes[iend_chunk_start:]


def _minimal_png() -> bytes:
    """Create a minimal valid 1x1 transparent PNG."""
    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"

    # IHDR chunk: 1x1, 8-bit RGBA
    ihdr_data = struct.pack(
        ">IIBBBBB", 1, 1, 8, 6, 0, 0, 0
    )  # width, height, bit_depth, color_type, compression, filter, interlace
    ihdr_type = b"IHDR"
    ihdr_crc = zlib.crc32(ihdr_type + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", len(ihdr_data)) + ihdr_type + ihdr_data + struct.pack(">I", ihdr_crc)

    # IDAT chunk: 1x1 transparent pixel (filter byte + RGBA)
    raw_data = b"\x00" + b"\x00\x00\x00\x00"  # filter=none + transparent pixel
    compressed = zlib.compress(raw_data)
    idat_type = b"IDAT"
    idat_crc = zlib.crc32(idat_type + compressed) & 0xFFFFFFFF
    idat = struct.pack(">I", len(compressed)) + idat_type + compressed + struct.pack(">I", idat_crc)

    # IEND chunk
    iend_type = b"IEND"
    iend_crc = zlib.crc32(iend_type) & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + iend_type + struct.pack(">I", iend_crc)

    return sig + ihdr + idat + iend


class TavernAIImporter:
    """Import and export TavernAI Character Card V2 format.

    Character Card V2 JSON structure:
    {
        "spec": "chara_card_v2",
        "data": {
            "name": str,
            "description": str,
            "personality": str,
            "scenario": str,
            "first_mes": str,
            "mes_example": str,
            "tags": list[str],
            "creator": str,
            "creator_notes": str,
            "character_version": str,
            "extensions": dict,
            ...
        }
    }
    """

    @staticmethod
    async def from_json(data: dict[str, Any]) -> Soul:
        """Create a Soul from a Character Card V2 JSON dict.

        Args:
            data: Full Character Card V2 JSON with 'spec' and 'data' fields.

        Returns:
            A Soul instance with mapped character data.

        Raises:
            ValueError: If the card format is invalid or missing required fields.
        """
        from soul_protocol.runtime.soul import Soul

        card = _validate_card_v2(data)

        name = card["name"]

        # Build persona from description + personality
        persona_parts: list[str] = []
        if card.get("description"):
            persona_parts.append(card["description"])
        if card.get("personality"):
            persona_parts.append(card["personality"])
        persona = "\n\n".join(persona_parts) if persona_parts else f"I am {name}."

        # Tags become values
        tags = card.get("tags", [])
        values = tags if isinstance(tags, list) else []

        # Creator as archetype hint
        archetype = card.get("creator_notes", "") or ""

        soul = await Soul.birth(
            name=name,
            archetype=archetype,
            persona=persona,
            values=values if values else None,
        )

        # first_mes -> procedural memory (greeting/conversation starter)
        if card.get("first_mes"):
            await soul.remember(
                f"Default greeting:\n{card['first_mes']}",
                type=MemoryType.PROCEDURAL,
                importance=7,
            )

        # scenario -> semantic memory
        if card.get("scenario"):
            await soul.remember(
                f"Character scenario:\n{card['scenario']}",
                type=MemoryType.SEMANTIC,
                importance=6,
            )

        # mes_example -> procedural memory (conversation examples)
        if card.get("mes_example"):
            await soul.remember(
                f"Example conversations:\n{card['mes_example']}",
                type=MemoryType.PROCEDURAL,
                importance=6,
            )

        # creator -> semantic memory
        if card.get("creator"):
            await soul.remember(
                f"Created by: {card['creator']}",
                type=MemoryType.SEMANTIC,
                importance=4,
            )

        # character_version -> semantic memory
        if card.get("character_version"):
            await soul.remember(
                f"Character version: {card['character_version']}",
                type=MemoryType.SEMANTIC,
                importance=3,
            )

        # Store any extensions as semantic memory
        extensions = card.get("extensions", {})
        if extensions and isinstance(extensions, dict):
            await soul.remember(
                f"Character extensions: {json.dumps(extensions)}",
                type=MemoryType.SEMANTIC,
                importance=4,
            )

        logger.info("Imported TavernAI Character Card V2: name=%s", name)
        return soul

    @staticmethod
    async def from_png(path: str | Path) -> Soul:
        """Extract Character Card V2 JSON from a PNG file and create a Soul.

        TavernAI character cards can be embedded in PNG files as a tEXt chunk
        with keyword 'chara' containing base64-encoded JSON.

        Args:
            path: Path to the PNG file containing a character card.

        Returns:
            A Soul instance with mapped character data.

        Raises:
            FileNotFoundError: If the PNG file doesn't exist.
            ValueError: If no character data found in the PNG or invalid format.
        """
        png_path = Path(path)
        if not png_path.exists():
            raise FileNotFoundError(f"PNG file not found: {png_path}")

        png_bytes = png_path.read_bytes()
        card_json = _extract_json_from_png(png_bytes)
        return await TavernAIImporter.from_json(card_json)

    @staticmethod
    async def to_character_card(soul: Soul) -> dict[str, Any]:
        """Export a Soul to Character Card V2 JSON format.

        Args:
            soul: The Soul to export.

        Returns:
            A Character Card V2 JSON dict ready for serialization.
        """
        core = soul.get_core_memory()

        # Gather procedural memories for first_mes and mes_example
        procedural = soul._memory._procedural.entries()
        first_mes = ""
        mes_example = ""
        for mem in procedural:
            content = mem.content
            if content.startswith("Default greeting:"):
                first_mes = content.replace("Default greeting:\n", "", 1)
            elif content.startswith("Example conversations:"):
                mes_example = content.replace("Example conversations:\n", "", 1)

        # Gather semantic memories for scenario
        scenario = ""
        semantic = soul._memory._semantic.facts()
        for mem in semantic:
            if mem.content.startswith("Character scenario:"):
                scenario = mem.content.replace("Character scenario:\n", "", 1)
                break

        # Creator from semantic memory
        creator = ""
        for mem in semantic:
            if mem.content.startswith("Created by:"):
                creator = mem.content.replace("Created by: ", "", 1)
                break

        # Tags from values
        tags = soul.identity.core_values if soul.identity.core_values else []

        card: dict[str, Any] = {
            "spec": CHARA_CARD_V2_SPEC,
            "data": {
                "name": soul.name,
                "description": core.persona or "",
                "personality": "",
                "scenario": scenario,
                "first_mes": first_mes,
                "mes_example": mes_example,
                "tags": tags,
                "creator": creator,
                "creator_notes": soul.archetype or "",
                "character_version": "1.0",
                "extensions": {},
            },
        }

        logger.info("Exported to TavernAI Character Card V2: name=%s", soul.name)
        return card

    @staticmethod
    async def to_png(
        soul: Soul, output_path: str | Path, image_path: str | Path | None = None
    ) -> Path:
        """Export a Soul to a PNG file with embedded Character Card V2.

        Args:
            soul: The Soul to export.
            output_path: Where to write the output PNG.
            image_path: Optional existing PNG to use as the base image.
                       If None, a minimal 1x1 transparent PNG is created.

        Returns:
            Path to the output PNG file.
        """
        card_json = await TavernAIImporter.to_character_card(soul)

        if image_path:
            img_path = Path(image_path)
            if not img_path.exists():
                raise FileNotFoundError(f"Image file not found: {img_path}")
            image_bytes = img_path.read_bytes()
        else:
            image_bytes = _minimal_png()

        png_bytes = _build_png_with_chara(image_bytes, card_json)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(png_bytes)

        logger.info("Exported TavernAI PNG: path=%s, name=%s", out, soul.name)
        return out
