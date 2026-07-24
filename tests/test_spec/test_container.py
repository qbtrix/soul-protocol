# test_core/test_container.py — Tests for SoulContainer: create, open, save, properties.
# Created: 2026-03-06 — Covers basic creation, traits, name/id properties,
# save/open lifecycle, FileNotFoundError, memory property, and repr.

from __future__ import annotations

import pytest

from soul_protocol.spec import DictMemoryStore, MemoryEntry, MemoryStore, SoulContainer


def test_create_basic():
    """SoulContainer.create() with just a name produces a usable container."""
    soul = SoulContainer.create("Aria")

    assert soul.name == "Aria"
    assert soul.id is not None
    assert len(soul.id) == 12


def test_create_with_traits():
    """SoulContainer.create() passes traits through to the identity."""
    traits = {"role": "guide", "openness": 0.9}
    soul = SoulContainer.create("Kairos", traits=traits)

    assert soul.identity.traits["role"] == "guide"
    assert soul.identity.traits["openness"] == 0.9


def test_create_with_no_traits_defaults_to_empty_dict():
    """traits defaults to empty dict when not provided."""
    soul = SoulContainer.create("Aria")

    assert soul.identity.traits == {}


def test_name_and_id():
    """name and id properties reflect the underlying identity."""
    soul = SoulContainer.create("Echo")

    assert soul.name == soul.identity.name
    assert soul.id == soul.identity.id


def test_save_and_open(tmp_path):
    """save() writes a .soul file; open() restores identity and memories."""
    path = tmp_path / "test.soul"
    soul = SoulContainer.create("Aria", traits={"role": "assistant"})
    soul.memory.store("episodic", MemoryEntry(layer="core", content="hello world"))
    soul.save(path)

    restored = SoulContainer.open(path)

    assert restored.name == soul.name
    assert restored.id == soul.id
    assert restored.identity.traits == soul.identity.traits

    recalled = restored.memory.recall("episodic")
    assert len(recalled) == 1
    assert recalled[0].content == "hello world"


def test_save_and_open_multiple_memories(tmp_path):
    """save/open preserves multiple memories across multiple layers."""
    path = tmp_path / "multi.soul"
    soul = SoulContainer.create("Multi")
    soul.memory.store("episodic", MemoryEntry(layer="core", content="episodic one"))
    soul.memory.store("episodic", MemoryEntry(layer="core", content="episodic two"))
    soul.memory.store("semantic", MemoryEntry(layer="core", content="semantic one"))
    soul.save(path)

    restored = SoulContainer.open(path)

    assert restored.memory.count("episodic") == 2
    assert restored.memory.count("semantic") == 1


def test_open_nonexistent_raises_file_not_found():
    """SoulContainer.open() raises FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        SoulContainer.open("/tmp/does_not_exist_abc123.soul")


def test_memory_property():
    """The .memory property returns a MemoryStore instance."""
    soul = SoulContainer.create("Aria")

    assert isinstance(soul.memory, MemoryStore)


def test_memory_default_is_dict_memory_store():
    """Without a custom store, .memory is a DictMemoryStore."""
    soul = SoulContainer.create("Aria")

    assert isinstance(soul.memory, DictMemoryStore)


def test_repr():
    """__repr__ includes name and id."""
    soul = SoulContainer.create("Aria")
    r = repr(soul)

    assert "SoulContainer" in r
    assert "Aria" in r
    assert soul.id in r


def test_save_overwrites_existing_file(tmp_path):
    """save() silently overwrites an existing file at the same path."""
    path = tmp_path / "overwrite.soul"

    soul_v1 = SoulContainer.create("Version1")
    soul_v1.save(path)

    soul_v2 = SoulContainer.create("Version2")
    soul_v2.save(path)

    restored = SoulContainer.open(path)
    assert restored.name == "Version2"
