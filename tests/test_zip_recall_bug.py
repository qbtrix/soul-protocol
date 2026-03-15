# test_zip_recall_bug.py — Regression test for stale recall after .soul file update.
# Created: 2026-03-15 — The original bug: soul_recall via MCP returns 0 results for
#   memories that exist in the .soul file on disk. Root cause: MCP server loads souls
#   at startup and never reloads when the file is updated externally. The soul_reload
#   tool fixes this. Also covers basic zip roundtrip recall as a sanity check.

from __future__ import annotations

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryType


# ---------------------------------------------------------------------------
# Bug scenario 1: remember() → export to .soul file → awaken → recall
# ---------------------------------------------------------------------------


async def test_zip_recall_semantic_after_export_awaken(tmp_path):
    """Recall finds SEMANTIC memories after export/awaken roundtrip via .soul file.

    This is the core regression test for the zip recall bug.
    Steps:
      1. Birth a soul
      2. Add semantic memory containing "MiroFish swarm prediction"
      3. Confirm recall works on the original soul (sanity check)
      4. Export to .soul zip archive
      5. Awaken a new soul from the zip
      6. Confirm memory_count > 0 (memories are in the archive)
      7. Recall the same query — EXPECT results (currently BUG: returns 0)
    """
    soul = await Soul.birth("TestBot", values=["accuracy"])

    await soul.remember(
        "MiroFish swarm prediction algorithm uses tidal resonance",
        type=MemoryType.SEMANTIC,
        importance=8,
    )

    # Sanity: original soul can recall before export
    before_export = await soul.recall("MiroFish swarm prediction")
    assert len(before_export) >= 1, "Sanity check: original soul must recall the memory"
    assert any("MiroFish" in m.content for m in before_export)

    # Export to zip archive
    zip_path = tmp_path / "testbot.soul"
    await soul.export(str(zip_path))
    assert zip_path.exists(), "Export must create the .soul file"

    # Awaken from zip
    restored = await Soul.awaken(str(zip_path))

    # Confirm memories are present (proves data is in archive)
    assert restored.memory_count > 0, (
        f"Memories must exist after awaken: got memory_count={restored.memory_count}. "
        "This proves the data is in the archive but recall still fails."
    )

    # This is the bug: recall returns 0 even though memory_count > 0
    after_awaken = await restored.recall("MiroFish swarm prediction")
    assert len(after_awaken) >= 1, (
        f"BUG: recall returned 0 results after zip awaken, "
        f"but memory_count={restored.memory_count} proves memories exist in the archive. "
        f"Loaded soul: name={restored.name}, memory_count={restored.memory_count}"
    )
    assert any("MiroFish" in m.content for m in after_awaken), (
        "Recalled memory content must contain 'MiroFish'"
    )


async def test_zip_recall_episodic_after_export_awaken(tmp_path):
    """Recall finds EPISODIC memories after export/awaken roundtrip via .soul file.

    Episodic memories added via remember() are wrapped as interactions
    before storage. This tests the episodic tier specifically.
    """
    soul = await Soul.birth("TestBot")

    await soul.remember(
        "MiroFish swarm prediction",
        type=MemoryType.EPISODIC,
        importance=7,
    )

    # Sanity: original recall works
    before_export = await soul.recall("MiroFish")
    assert len(before_export) >= 1, "Sanity check: original soul must recall episodic memory"

    zip_path = tmp_path / "testbot_ep.soul"
    await soul.export(str(zip_path))

    restored = await Soul.awaken(str(zip_path))

    assert restored.memory_count > 0, (
        f"Episodic memories must survive zip roundtrip: memory_count={restored.memory_count}"
    )

    after_awaken = await restored.recall("MiroFish")
    assert len(after_awaken) >= 1, (
        f"BUG: episodic recall returned 0 results after zip awaken. "
        f"memory_count={restored.memory_count} confirms memories are in archive."
    )


async def test_zip_recall_via_bytes(tmp_path):
    """Recall works when soul is awakened from raw bytes (not a file path).

    Soul.awaken() can accept bytes directly. This exercises the bytes
    path of unpack_soul + MemoryManager.from_dict.
    """
    soul = await Soul.birth("TestBot")

    await soul.remember(
        "MiroFish swarm prediction via tidal resonance sensors",
        type=MemoryType.SEMANTIC,
        importance=9,
    )

    zip_path = tmp_path / "testbot_bytes.soul"
    await soul.export(str(zip_path))
    raw_bytes = zip_path.read_bytes()

    # Awaken from raw bytes
    restored = await Soul.awaken(raw_bytes)

    assert restored.memory_count > 0, (
        f"Bytes-awakened soul must have memories: memory_count={restored.memory_count}"
    )

    after_awaken = await restored.recall("MiroFish tidal resonance")
    assert len(after_awaken) >= 1, (
        f"BUG: recall from bytes-awakened soul returned 0 results. "
        f"memory_count={restored.memory_count} confirms data survived the roundtrip."
    )
    assert any("MiroFish" in m.content for m in after_awaken)


async def test_zip_recall_multiple_memories(tmp_path):
    """Multiple memories of different types all survive and are recallable after zip roundtrip.

    Tests that neither SEMANTIC nor EPISODIC memories are silently dropped
    during pack/unpack, and that recall surfaces them correctly.
    """
    soul = await Soul.birth("TestBot", values=["accuracy", "speed"])

    # Add several semantic memories
    await soul.remember(
        "MiroFish swarm prediction uses tidal resonance",
        type=MemoryType.SEMANTIC,
        importance=9,
    )
    await soul.remember(
        "The deep ocean router connects MiroFish nodes",
        type=MemoryType.SEMANTIC,
        importance=7,
    )
    await soul.remember(
        "Swarm coordination latency is below 50ms",
        type=MemoryType.SEMANTIC,
        importance=6,
    )

    original_count = soul.memory_count
    assert original_count >= 3, f"Expected at least 3 memories, got {original_count}"

    zip_path = tmp_path / "testbot_multi.soul"
    await soul.export(str(zip_path))

    restored = await Soul.awaken(str(zip_path))

    # All memories should survive the roundtrip
    assert restored.memory_count == original_count, (
        f"Memory count must be preserved after zip roundtrip: "
        f"original={original_count}, restored={restored.memory_count}"
    )

    # Recall for each memory should return results
    mirofish_results = await restored.recall("MiroFish swarm prediction")
    assert len(mirofish_results) >= 1, (
        f"BUG: 'MiroFish swarm prediction' recall returned 0 results after zip awaken. "
        f"memory_count={restored.memory_count}"
    )

    router_results = await restored.recall("deep ocean router")
    assert len(router_results) >= 1, (
        f"BUG: 'deep ocean router' recall returned 0 results after zip awaken. "
        f"memory_count={restored.memory_count}"
    )


async def test_zip_recall_returns_correct_content(tmp_path):
    """The content of recalled memories after zip roundtrip matches what was stored.

    This confirms not just that recall returns *something*, but that it
    returns the correct, unmangled content.
    """
    soul = await Soul.birth("TestBot")

    original_content = "MiroFish swarm prediction: tidal resonance at 7.83 Hz"
    await soul.remember(
        original_content,
        type=MemoryType.SEMANTIC,
        importance=10,
    )

    zip_path = tmp_path / "testbot_content.soul"
    await soul.export(str(zip_path))

    restored = await Soul.awaken(str(zip_path))
    results = await restored.recall("MiroFish tidal resonance")

    assert len(results) >= 1, (
        f"BUG: recall returned 0 results after zip awaken. "
        f"memory_count={restored.memory_count}"
    )

    recalled_content = results[0].content
    assert "MiroFish" in recalled_content, (
        f"Recalled content must contain 'MiroFish', got: {recalled_content!r}"
    )
    assert "tidal resonance" in recalled_content.lower(), (
        f"Recalled content must contain 'tidal resonance', got: {recalled_content!r}"
    )


# ---------------------------------------------------------------------------
# Bug scenario 6: stale data — .soul file updated externally, reload picks it up
# ---------------------------------------------------------------------------


async def test_stale_soul_reload_picks_up_new_memories(tmp_path):
    """Simulates the actual bug: MCP server loads a soul, the .soul file is
    updated externally with new memories, and recall doesn't find them until
    the soul is reloaded from disk.

    This is the root cause of the MiroFish recall bug — the MCP server loaded
    pocketpaw.soul at startup, but the MiroFish memory was added later by
    another process and exported to the same .soul file.
    """
    # Phase 1: create soul with initial memories and export
    soul_v1 = await Soul.birth("TestBot", values=["accuracy"])
    await soul_v1.remember(
        "Initial memory about ocean currents",
        type=MemoryType.SEMANTIC,
        importance=7,
    )
    zip_path = tmp_path / "testbot.soul"
    await soul_v1.export(str(zip_path))

    # Phase 2: simulate MCP server loading the soul at startup
    server_soul = await Soul.awaken(str(zip_path))
    assert server_soul.memory_count >= 1
    initial_count = server_soul.memory_count

    # Phase 3: externally, another process adds memories and re-exports
    external_soul = await Soul.awaken(str(zip_path))
    await external_soul.remember(
        "MiroFish swarm prediction uses tidal resonance",
        type=MemoryType.SEMANTIC,
        importance=9,
    )
    await external_soul.export(str(zip_path))  # overwrite the .soul file

    # Phase 4: server_soul is stale — it doesn't have the new memory
    stale_results = await server_soul.recall("MiroFish swarm prediction")
    assert len(stale_results) == 0, (
        "Server soul should NOT find MiroFish before reload (stale data)"
    )

    # Phase 5: reload from disk picks up the new memory
    reloaded = await Soul.awaken(str(zip_path))
    assert reloaded.memory_count > initial_count, (
        f"Reloaded soul should have more memories: "
        f"initial={initial_count}, reloaded={reloaded.memory_count}"
    )

    fresh_results = await reloaded.recall("MiroFish swarm prediction")
    assert len(fresh_results) >= 1, (
        f"Reloaded soul MUST find MiroFish after reload. "
        f"memory_count={reloaded.memory_count}"
    )
    assert any("MiroFish" in r.content for r in fresh_results)
