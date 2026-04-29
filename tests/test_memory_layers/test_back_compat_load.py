# tests/test_memory_layers/test_back_compat_load.py — 0.3.x souls load cleanly.
# Created: 2026-04-29 (#41) — Verifies that a soul exported by 0.3.x (where
# MemoryEntry has only `type` and no `layer` or `domain` fields) loads with
# layer derived from type and domain="default". No data loss.

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from soul_protocol.runtime.export.unpack import unpack_soul
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryEntry


def _build_legacy_soul_archive() -> bytes:
    """Build a synthetic 0.3.x .soul archive with no layer/domain fields."""
    soul_config = {
        "version": "1.0.0",
        "identity": {
            "did": "did:soul:legacy-test",
            "name": "Legacy",
            "archetype": "legacy",
        },
        "dna": {},
        "memory": {},
        "core_memory": {"persona": "", "human": ""},
        "state": {},
        "evolution": {},
        "lifecycle": "born",
        "skills": [],
        "evaluation_history": [],
        "interaction_count": 0,
    }

    legacy_episodic = [
        {
            "id": "epi001",
            "type": "episodic",
            "content": "An old conversation",
            "importance": 5,
            "created_at": "2026-01-15T10:00:00",
        },
    ]
    legacy_semantic = [
        {
            "id": "sem001",
            "type": "semantic",
            "content": "User likes Python",
            "importance": 7,
            "created_at": "2026-01-15T10:00:00",
        },
        {
            "id": "sem002",
            "type": "semantic",
            "content": "User uses macOS",
            "importance": 6,
            "created_at": "2026-01-15T10:01:00",
        },
    ]
    legacy_procedural = [
        {
            "id": "pro001",
            "type": "procedural",
            "content": "To deploy: run make deploy",
            "importance": 6,
            "created_at": "2026-01-15T10:02:00",
        },
    ]

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format_version": "1.0.0",
                    "soul_id": "did:soul:legacy-test",
                    "soul_name": "Legacy",
                    "encrypted": False,
                    "stats": {"version": "1.0.0", "lifecycle": "born", "role": ""},
                }
            ),
        )
        zf.writestr("soul.json", json.dumps(soul_config))
        zf.writestr("dna.md", "# Legacy soul\n")
        zf.writestr("state.json", "{}")
        zf.writestr("memory/core.json", json.dumps({"persona": "", "human": ""}))
        zf.writestr("memory/episodic.json", json.dumps(legacy_episodic))
        zf.writestr("memory/semantic.json", json.dumps(legacy_semantic))
        zf.writestr("memory/procedural.json", json.dumps(legacy_procedural))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_legacy_archive_unpacks_without_layer_or_domain():
    config, memory_data = await unpack_soul(_build_legacy_soul_archive())
    assert config.identity.name == "Legacy"
    # Legacy archives don't include the social tier — that should be absent.
    assert "social" not in memory_data
    # Episodic / semantic / procedural come back as raw dicts; auto-migration
    # happens when they're loaded into MemoryEntry instances.
    assert memory_data["semantic"][0]["content"] == "User likes Python"


@pytest.mark.asyncio
async def test_memory_entry_validate_back_fills_defaults():
    raw = {
        "id": "sem001",
        "type": "semantic",
        "content": "User likes Python",
        "importance": 7,
        "created_at": "2026-01-15T10:00:00",
    }
    entry = MemoryEntry.model_validate(raw)
    assert entry.layer == "semantic"
    assert entry.domain == "default"


@pytest.mark.asyncio
async def test_full_legacy_awaken_round_trip(tmp_path: Path):
    archive = _build_legacy_soul_archive()
    soul_path = tmp_path / "legacy.soul"
    soul_path.write_bytes(archive)

    soul = await Soul.awaken(soul_path)
    facts = soul._memory._semantic.facts()
    assert any(f.content == "User likes Python" for f in facts)
    assert any(f.content == "User uses macOS" for f in facts)
    # Layer auto-filled from type, domain set to default.
    for f in facts:
        assert f.layer == "semantic"
        assert f.domain == "default"

    # Episodic preserved
    epi = soul._memory._episodic.entries()
    assert any(e.content == "An old conversation" for e in epi)
    for e in epi:
        assert e.layer == "episodic"
        assert e.domain == "default"
