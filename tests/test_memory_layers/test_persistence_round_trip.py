# tests/test_memory_layers/test_persistence_round_trip.py — Save/load with layers.
# Created: 2026-04-29 (#41) — Verifies the persistence layer chooses the
# right on-disk shape: flat layout when every entry is in a built-in layer
# with domain="default", nested layout (memory/<layer>/<domain>/entries.json)
# when custom domains or custom layers appear. Either way, awakening the
# soul restores the same memories.

from __future__ import annotations

from pathlib import Path

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryEntry, MemoryType


@pytest.mark.asyncio
async def test_default_only_soul_uses_flat_layout(tmp_path: Path):
    soul = await Soul.birth(name="Flat", archetype="flat layout test")
    await soul.remember("User prefers dark mode", importance=7)
    await soul.remember("User uses Python daily", type=MemoryType.SEMANTIC, importance=7)

    target = tmp_path / "soul"
    await soul.save_local(target)

    # Flat layout: top-level memory/episodic.json etc.; no per-layer dirs.
    assert (target / "memory" / "semantic.json").exists()
    for tier in ("episodic", "semantic", "procedural", "social"):
        assert not (target / "memory" / tier).is_dir()

    # Round-trip
    rebuilt = await Soul.awaken(target)
    facts = rebuilt._memory._semantic.facts()
    contents = {f.content for f in facts}
    assert "User prefers dark mode" in contents
    assert "User uses Python daily" in contents
    for f in facts:
        assert f.domain == "default"


@pytest.mark.asyncio
async def test_custom_domain_soul_uses_nested_layout(tmp_path: Path):
    soul = await Soul.birth(name="Nested", archetype="nested layout test")
    await soul.remember("Q3 revenue up", domain="finance", importance=8)
    await soul.remember("NDA expires in March", domain="legal", importance=8)
    await soul.remember("User likes Python", importance=7)

    target = tmp_path / "soul"
    await soul.save_local(target)

    # Nested layout: memory/<layer>/<domain>/entries.json
    assert (target / "memory" / "semantic" / "finance" / "entries.json").exists()
    assert (target / "memory" / "semantic" / "legal" / "entries.json").exists()
    assert (target / "memory" / "semantic" / "default" / "entries.json").exists()
    assert (target / "memory" / "_layout.json").exists()

    rebuilt = await Soul.awaken(target)
    facts = rebuilt._memory._semantic.facts()
    domain_map = {f.content: f.domain for f in facts}
    assert domain_map.get("Q3 revenue up") == "finance"
    assert domain_map.get("NDA expires in March") == "legal"
    assert domain_map.get("User likes Python") == "default"


@pytest.mark.asyncio
async def test_custom_layer_round_trips(tmp_path: Path):
    soul = await Soul.birth(name="Custom", archetype="custom layer test")
    custom = soul._memory.layer("preferences")
    await custom.store(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="User likes night mode",
            importance=7,
        )
    )

    target = tmp_path / "soul"
    await soul.save_local(target)

    # Custom layer should land under memory/preferences/default/entries.json
    assert (target / "memory" / "preferences" / "default" / "entries.json").exists()

    rebuilt = await Soul.awaken(target)
    pref_view = rebuilt._memory.layer("preferences")
    entries = pref_view.entries()
    assert any(e.content == "User likes night mode" for e in entries)


@pytest.mark.asyncio
async def test_mixed_domains_and_custom_layers_round_trip(tmp_path: Path):
    soul = await Soul.birth(name="Mix", archetype="mixed test")
    await soul.remember("Q3 revenue up", domain="finance", importance=8)
    custom = soul._memory.layer("preferences")
    await custom.store(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="dark mode for finance dashboards",
            importance=7,
            domain="finance",
        )
    )
    target = tmp_path / "soul"
    await soul.save_local(target)

    rebuilt = await Soul.awaken(target)
    facts = rebuilt._memory._semantic.facts()
    fin_facts = [f for f in facts if f.domain == "finance"]
    assert any(f.content == "Q3 revenue up" for f in fin_facts)

    pref = rebuilt._memory.layer("preferences").entries()
    assert any(e.content == "dark mode for finance dashboards" for e in pref)


@pytest.mark.asyncio
async def test_export_archive_round_trips_custom_domains(tmp_path: Path):
    soul = await Soul.birth(name="Arch", archetype="archive test")
    await soul.remember("Q3 revenue up", domain="finance", importance=8)
    await soul.remember("User loves async coding", domain="default", importance=6)

    target = tmp_path / "out.soul"
    await soul.export(target)
    assert target.exists()

    rebuilt = await Soul.awaken(target)
    facts = rebuilt._memory._semantic.facts()
    finance = [f for f in facts if f.domain == "finance"]
    default = [f for f in facts if f.domain == "default"]
    assert any(f.content == "Q3 revenue up" for f in finance)
    assert any(f.content == "User loves async coding" for f in default)
