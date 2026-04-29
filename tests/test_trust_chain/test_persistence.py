# tests/test_trust_chain/test_persistence.py — Save/awaken roundtrips for trust chain.
# Created: 2026-04-29 (#42) — Trust chain survives export/awaken cycles. The
# include_keys flag controls whether the recipient can append; verification
# always works thanks to the embedded public key per entry.

from __future__ import annotations

from pathlib import Path

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction


@pytest.mark.asyncio
async def test_export_with_keys_then_awaken_can_append(tmp_path: Path):
    soul = await Soul.birth("Alpha")
    await soul.observe(Interaction(user_input="hi", agent_output="hello"))
    pre_length = soul.trust_chain.length

    archive = tmp_path / "alpha.soul"
    await soul.export(archive, include_keys=True)

    soul2 = await Soul.awaken(archive)
    assert soul2.trust_chain.length == pre_length
    assert soul2.verify_chain() == (True, None)

    # Can append after awaken because the private key is restored
    await soul2.observe(Interaction(user_input="more", agent_output="ok"))
    assert soul2.trust_chain.length > pre_length
    assert soul2.verify_chain() == (True, None)


@pytest.mark.asyncio
async def test_export_without_keys_can_still_verify(tmp_path: Path):
    soul = await Soul.birth("Beta")
    await soul.observe(Interaction(user_input="hi", agent_output="hello"))
    pre_length = soul.trust_chain.length

    archive = tmp_path / "beta.soul"
    await soul.export(archive, include_keys=False)

    soul2 = await Soul.awaken(archive)
    assert soul2.trust_chain.length == pre_length
    assert soul2.verify_chain() == (True, None)


@pytest.mark.asyncio
async def test_export_without_keys_blocks_appends(tmp_path: Path):
    """A soul awakened without a private key should silently skip chain
    appends — the underlying action still happens (memory writes etc.) but
    no new entry lands in the chain."""
    soul = await Soul.birth("Gamma")
    await soul.observe(Interaction(user_input="hi", agent_output="hello"))
    pre_length = soul.trust_chain.length

    archive = tmp_path / "gamma.soul"
    await soul.export(archive, include_keys=False)

    soul2 = await Soul.awaken(archive)
    await soul2.observe(Interaction(user_input="another", agent_output="ok"))

    # Length unchanged — the action ran but no new chain entry was signed
    assert soul2.trust_chain.length == pre_length


@pytest.mark.asyncio
async def test_directory_round_trip_preserves_chain(tmp_path: Path):
    soul = await Soul.birth("Delta")
    await soul.observe(Interaction(user_input="hi", agent_output="hello"))
    await soul.observe(Interaction(user_input="more", agent_output="ok"))
    pre_length = soul.trust_chain.length

    soul_dir = tmp_path / "delta-soul"
    await soul.save_local(soul_dir)

    # Per-entry files exist for human inspection
    for i in range(pre_length):
        assert (soul_dir / "trust_chain" / f"entry_{i:03d}.json").exists()
    assert (soul_dir / "trust_chain" / "chain.json").exists()
    assert (soul_dir / "keys" / "public.key").exists()

    soul2 = await Soul.awaken(soul_dir)
    assert soul2.trust_chain.length == pre_length
    assert soul2.verify_chain() == (True, None)


@pytest.mark.asyncio
async def test_directory_save_excludes_private_when_asked(tmp_path: Path):
    soul = await Soul.birth("Epsilon")
    await soul.observe(Interaction(user_input="hi", agent_output="hello"))

    soul_dir = tmp_path / "epsilon-soul"
    await soul.save_local(soul_dir, include_keys=False)

    assert (soul_dir / "keys" / "public.key").exists()
    assert not (soul_dir / "keys" / "private.key").exists()


@pytest.mark.asyncio
async def test_legacy_archive_without_chain_still_loads(tmp_path: Path):
    """A soul created before #42 has no trust_chain/ directory in its archive.
    Awaken should silently produce an empty chain instead of failing."""
    # Simulate by exporting then editing the zip to drop trust_chain entries.
    soul = await Soul.birth("Legacy")
    archive = tmp_path / "legacy.soul"
    await soul.export(archive, include_keys=True)

    # Strip trust_chain/* from the archive
    import zipfile

    stripped = tmp_path / "stripped.soul"
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(stripped, "w") as dst:
        for item in src.infolist():
            if item.filename.startswith("trust_chain/"):
                continue
            dst.writestr(item, src.read(item.filename))

    soul2 = await Soul.awaken(stripped)
    assert soul2.trust_chain.length == 0
    assert soul2.verify_chain() == (True, None)
