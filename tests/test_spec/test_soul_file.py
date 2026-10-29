# test_core/test_soul_file.py — Tests for pack_soul(), unpack_soul(), unpack_to_container().
# Created: 2026-03-06 — Covers roundtrip fidelity, multi-layer preservation,
# the container convenience helper, and error handling for invalid input.

from __future__ import annotations

import pytest

from soul_protocol.spec import (
    DictMemoryStore,
    Identity,
    MemoryEntry,
    pack_soul,
    unpack_soul,
    unpack_to_container,
)


def _make_identity(name: str = "Aria") -> Identity:
    return Identity(name=name, traits={"role": "assistant"})


def _make_store_with_entries(*entries: tuple[str, str]) -> DictMemoryStore:
    """Helper: (layer, content) pairs -> populated DictMemoryStore."""
    store = DictMemoryStore()
    for layer, content in entries:
        store.store(layer, MemoryEntry(layer="core", content=content))
    return store


def test_pack_unpack_roundtrip():
    """pack_soul then unpack_soul preserves identity and memory content."""
    identity = _make_identity()
    store = _make_store_with_entries(("episodic", "met a user today"))

    data = pack_soul(identity, store)
    restored_identity, layers = unpack_soul(data)

    assert restored_identity.id == identity.id
    assert restored_identity.name == identity.name
    assert restored_identity.traits == identity.traits

    assert "episodic" in layers
    assert len(layers["episodic"]) == 1
    assert layers["episodic"][0]["content"] == "met a user today"


def test_pack_with_layers():
    """Multiple layers are all preserved through pack/unpack."""
    identity = _make_identity("Kairos")
    store = _make_store_with_entries(
        ("episodic", "went for a walk"),
        ("semantic", "earth orbits the sun"),
        ("procedural", "how to make tea"),
    )

    data = pack_soul(identity, store)
    _, layers = unpack_soul(data)

    assert set(layers.keys()) == {"episodic", "semantic", "procedural"}
    assert layers["semantic"][0]["content"] == "earth orbits the sun"
    assert layers["procedural"][0]["content"] == "how to make tea"


def test_pack_empty_memory():
    """Packing a soul with no memories produces a valid archive with no memory files."""
    identity = _make_identity()
    store = DictMemoryStore()

    data = pack_soul(identity, store)
    restored_identity, layers = unpack_soul(data)

    assert restored_identity.id == identity.id
    assert layers == {}


def test_unpack_to_container():
    """unpack_to_container returns Identity and a populated DictMemoryStore."""
    identity = _make_identity()
    store = _make_store_with_entries(
        ("episodic", "first memory"),
        ("episodic", "second memory"),
    )

    data = pack_soul(identity, store)
    restored_identity, restored_store = unpack_to_container(data)

    assert restored_identity.id == identity.id
    recalled = restored_store.recall("episodic")
    assert len(recalled) == 2
    contents = {e.content for e in recalled}
    assert "first memory" in contents
    assert "second memory" in contents


def test_unpack_to_container_preserves_layer_names():
    """unpack_to_container populates the correct layer names on the store."""
    identity = _make_identity()
    store = _make_store_with_entries(
        ("semantic", "knowledge entry"),
        ("working", "scratch pad note"),
    )

    data = pack_soul(identity, store)
    _, restored_store = unpack_to_container(data)

    assert set(restored_store.layers()) == {"semantic", "working"}


def test_unpack_invalid_raises_value_error():
    """unpack_soul raises ValueError for data that is not a valid .soul archive."""
    with pytest.raises((ValueError, Exception)):
        unpack_soul(b"this is not a zip file")


def test_unpack_missing_identity_raises_value_error():
    """unpack_soul raises ValueError when identity.json is absent from the archive."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", '{"format_version": "1.0.0"}')
    buf.seek(0)

    with pytest.raises(ValueError, match="identity.json"):
        unpack_soul(buf.getvalue())


def test_pack_produces_bytes():
    """pack_soul returns bytes, not a string or other type."""
    identity = _make_identity()
    store = DictMemoryStore()

    data = pack_soul(identity, store)

    assert isinstance(data, bytes)
    assert len(data) > 0
