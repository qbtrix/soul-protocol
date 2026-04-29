# tests/test_trust_chain/test_trust_entry.py — TrustEntry / hashing tests.
# Created: 2026-04-29 (#42) — Canonical-JSON guarantees: same content → same hash
# regardless of dict key order. Genesis sentinel. Pydantic round-trip.

from __future__ import annotations

from datetime import UTC, datetime

from soul_protocol.spec.trust import (
    GENESIS_PREV_HASH,
    TrustEntry,
    compute_entry_hash,
    compute_payload_hash,
)


def test_genesis_constant_is_64_zeros():
    assert GENESIS_PREV_HASH == "0" * 64


def test_payload_hash_is_canonical_under_key_order():
    a = compute_payload_hash({"a": 1, "b": 2, "c": 3})
    b = compute_payload_hash({"c": 3, "b": 2, "a": 1})
    assert a == b


def test_payload_hash_changes_with_value():
    a = compute_payload_hash({"x": 1})
    b = compute_payload_hash({"x": 2})
    assert a != b


def test_payload_hash_is_64_hex_chars():
    h = compute_payload_hash({"action": "memory.write"})
    assert len(h) == 64
    int(h, 16)  # Raises if not hex


def test_entry_hash_excludes_signature():
    """Entry hash should be the same whether signature is set or not."""
    e1 = TrustEntry(
        seq=0,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        actor_did="did:soul:test",
        action="x.y",
        payload_hash="a" * 64,
        prev_hash=GENESIS_PREV_HASH,
        signature="",
        public_key="abc",
    )
    e2 = e1.model_copy(update={"signature": "GARBAGE"})
    assert compute_entry_hash(e1) == compute_entry_hash(e2)


def test_entry_hash_differs_when_payload_hash_differs():
    base = TrustEntry(
        seq=0,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        actor_did="did:soul:test",
        action="x.y",
        payload_hash="a" * 64,
        prev_hash=GENESIS_PREV_HASH,
        public_key="k",
    )
    other = base.model_copy(update={"payload_hash": "b" * 64})
    assert compute_entry_hash(base) != compute_entry_hash(other)


def test_entry_pydantic_round_trip_preserves_fields():
    original = TrustEntry(
        seq=42,
        timestamp=datetime(2026, 4, 29, 12, tzinfo=UTC),
        actor_did="did:soul:test",
        action="memory.write",
        payload_hash="abc" * 21 + "a",
        prev_hash="def" * 21 + "f",
        signature="sig",
        algorithm="ed25519",
        public_key="pk",
    )
    rt = TrustEntry.model_validate_json(original.model_dump_json())
    assert rt.seq == original.seq
    assert rt.actor_did == original.actor_did
    assert rt.action == original.action
    assert rt.payload_hash == original.payload_hash
    assert rt.prev_hash == original.prev_hash
    assert rt.signature == original.signature
    assert rt.algorithm == original.algorithm
    assert rt.public_key == original.public_key
    assert rt.timestamp == original.timestamp


def test_naive_timestamp_is_normalized_to_utc():
    naive = datetime(2026, 1, 1, 12, 0, 0)  # no tzinfo
    e = TrustEntry(
        seq=0,
        timestamp=naive,
        actor_did="x",
        action="x.y",
        payload_hash="a" * 64,
        prev_hash=GENESIS_PREV_HASH,
    )
    assert e.timestamp.tzinfo is UTC


def test_genesis_entry_shape():
    """A freshly built genesis entry has seq=0 and prev_hash=GENESIS_PREV_HASH."""
    e = TrustEntry(
        seq=0,
        timestamp=datetime.now(UTC),
        actor_did="did:soul:test",
        action="memory.write",
        payload_hash=compute_payload_hash({}),
        prev_hash=GENESIS_PREV_HASH,
        public_key="pk",
    )
    assert e.seq == 0
    assert e.prev_hash == GENESIS_PREV_HASH
