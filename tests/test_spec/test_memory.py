# test_core/test_memory.py — Tests for MemoryEntry, MemoryStore protocol, and DictMemoryStore.
# Created: 2026-03-06 — Covers defaults, metadata, layer isolation, search, delete, count,
# layers listing, and protocol isinstance check.

from __future__ import annotations

from soul_protocol.spec import DictMemoryStore, MemoryEntry, MemoryStore


def test_memory_entry_defaults():
    """MemoryEntry auto-generates a 12-char hex id and a timestamp."""
    entry = MemoryEntry(layer="core", content="test content")

    assert entry.content == "test content"
    assert len(entry.id) == 12
    assert all(c in "0123456789abcdef" for c in entry.id)
    assert entry.timestamp is not None
    assert entry.source == ""
    assert entry.layer == "core"
    assert entry.metadata == {}


def test_memory_entry_with_metadata():
    """MemoryEntry stores arbitrary metadata without alteration."""
    entry = MemoryEntry(layer="core", content="met a user",
        metadata={"importance": 9, "tags": ["social", "first-meeting"]},
    )

    assert entry.metadata["importance"] == 9
    assert "social" in entry.metadata["tags"]


def test_dict_store_basic():
    """store() persists an entry; recall() returns it from the correct layer."""
    store = DictMemoryStore()
    entry = MemoryEntry(layer="core", content="hello world")

    returned_id = store.store("episodic", entry)

    assert returned_id == entry.id
    recalled = store.recall("episodic")
    assert len(recalled) == 1
    assert recalled[0].content == "hello world"


def test_dict_store_layers():
    """Entries stored in different layers are isolated from each other."""
    store = DictMemoryStore()

    store.store("episodic", MemoryEntry(layer="core", content="met Aria today"))
    store.store("semantic", MemoryEntry(layer="core", content="the sky is blue"))
    store.store("episodic", MemoryEntry(layer="core", content="had a dream"))

    episodic = store.recall("episodic")
    semantic = store.recall("semantic")

    assert len(episodic) == 2
    assert len(semantic) == 1
    assert semantic[0].content == "the sky is blue"


def test_dict_store_search():
    """search() returns entries with token overlap to the query."""
    store = DictMemoryStore()

    store.store("episodic", MemoryEntry(layer="core", content="the cat sat on the mat"))
    store.store("semantic", MemoryEntry(layer="core", content="dogs are loyal animals"))
    store.store("episodic", MemoryEntry(layer="core", content="the cat chased a bird"))

    results = store.search("cat mat")

    # Both cat-related entries should rank above the dogs entry
    assert len(results) >= 1
    contents = [r.content for r in results]
    assert any("cat" in c for c in contents)

    # Dogs entry should not appear — no token overlap with "cat mat"
    assert not any("dogs" in c for c in contents)


def test_dict_store_delete():
    """delete() removes an entry by id and returns True; False if not found."""
    store = DictMemoryStore()
    entry = MemoryEntry(layer="core", content="to be deleted")
    store.store("episodic", entry)

    result = store.delete(entry.id)

    assert result is True
    assert store.recall("episodic") == []


def test_dict_store_delete_missing_returns_false():
    """delete() returns False when the id does not exist."""
    store = DictMemoryStore()

    result = store.delete("nonexistentid1")

    assert result is False


def test_dict_store_layers_list():
    """layers() returns only layer names that have at least one entry."""
    store = DictMemoryStore()

    # Empty store — no layers
    assert store.layers() == []

    store.store("episodic", MemoryEntry(layer="core", content="first"))
    store.store("semantic", MemoryEntry(layer="core", content="second"))

    layer_names = store.layers()
    assert set(layer_names) == {"episodic", "semantic"}

    # Delete all episodic entries
    episodic = store.recall("episodic")
    store.delete(episodic[0].id)

    # Now only semantic should appear
    assert store.layers() == ["semantic"]


def test_dict_store_count():
    """count() returns total or per-layer entry count."""
    store = DictMemoryStore()

    store.store("episodic", MemoryEntry(layer="core", content="a"))
    store.store("episodic", MemoryEntry(layer="core", content="b"))
    store.store("semantic", MemoryEntry(layer="core", content="c"))

    assert store.count() == 3
    assert store.count("episodic") == 2
    assert store.count("semantic") == 1
    assert store.count("nonexistent") == 0


def test_dict_store_implements_protocol():
    """DictMemoryStore satisfies the MemoryStore runtime-checkable protocol."""
    store = DictMemoryStore()

    assert isinstance(store, MemoryStore)


def test_store_sets_layer_on_entry():
    """store() mutates entry.layer to match the target layer name."""
    store = DictMemoryStore()
    entry = MemoryEntry(layer="core", content="test")

    store.store("procedural", entry)

    assert entry.layer == "procedural"


def test_recall_returns_newest_first():
    """recall() orders entries by timestamp descending."""
    import time

    store = DictMemoryStore()
    store.store("episodic", MemoryEntry(layer="core", content="first"))
    time.sleep(0.01)
    store.store("episodic", MemoryEntry(layer="core", content="second"))

    recalled = store.recall("episodic")

    assert recalled[0].content == "second"
    assert recalled[1].content == "first"


def test_recall_limit():
    """recall() respects the limit parameter."""
    store = DictMemoryStore()
    for i in range(10):
        store.store("episodic", MemoryEntry(layer="core", content=f"entry {i}"))

    recalled = store.recall("episodic", limit=3)

    assert len(recalled) == 3
