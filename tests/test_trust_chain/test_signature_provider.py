# tests/test_trust_chain/test_signature_provider.py — Ed25519SignatureProvider tests.
# Created: 2026-04-29 (#42) — Sign/verify happy path, wrong-key rejection,
# from_seed determinism, public key serialization round-trips.

from __future__ import annotations

import base64

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.spec.trust import SignatureProvider


def test_provider_satisfies_protocol():
    """Ed25519SignatureProvider implements the SignatureProvider Protocol."""
    p = Ed25519SignatureProvider()
    assert isinstance(p, SignatureProvider)


def test_sign_and_verify_happy_path():
    p = Ed25519SignatureProvider()
    msg = b"hello world"
    sig = p.sign(msg)

    assert p.verify(msg, sig, p.public_key) is True


def test_verify_rejects_wrong_message():
    p = Ed25519SignatureProvider()
    sig = p.sign(b"hello world")

    assert p.verify(b"goodbye world", sig, p.public_key) is False


def test_verify_rejects_wrong_key():
    p1 = Ed25519SignatureProvider()
    p2 = Ed25519SignatureProvider()
    msg = b"hello"
    sig = p1.sign(msg)

    # p2's public key cannot verify p1's signature
    assert p1.verify(msg, sig, p2.public_key) is False


def test_verify_rejects_garbage_signature():
    p = Ed25519SignatureProvider()
    assert p.verify(b"hi", "not-base64!!!", p.public_key) is False
    assert p.verify(b"hi", "AAAA", p.public_key) is False


def test_verify_rejects_garbage_public_key():
    p = Ed25519SignatureProvider()
    sig = p.sign(b"hi")
    assert p.verify(b"hi", sig, "garbage") is False


def test_from_seed_is_deterministic():
    seed = b"X" * 32
    p1 = Ed25519SignatureProvider.from_seed(seed)
    p2 = Ed25519SignatureProvider.from_seed(seed)

    assert p1.public_key == p2.public_key
    assert p1.private_key_bytes == p2.private_key_bytes

    # Ed25519 signatures are deterministic too
    msg = b"deterministic"
    assert p1.sign(msg) == p2.sign(msg)


def test_from_seed_validates_length():
    import pytest

    with pytest.raises(ValueError):
        Ed25519SignatureProvider.from_seed(b"short")


def test_constructor_validates_private_key_length():
    import pytest

    with pytest.raises(ValueError):
        Ed25519SignatureProvider(private_key_bytes=b"\x00" * 16)


def test_public_key_round_trip_via_base64():
    p = Ed25519SignatureProvider()
    raw = p.public_key_bytes
    encoded = p.public_key

    decoded = base64.b64decode(encoded)
    assert decoded == raw
    assert len(raw) == 32


def test_private_key_bytes_round_trip():
    p1 = Ed25519SignatureProvider()
    p2 = Ed25519SignatureProvider(private_key_bytes=p1.private_key_bytes)

    assert p1.public_key == p2.public_key
    msg = b"roundtrip"
    sig = p1.sign(msg)
    assert p2.verify(msg, sig, p2.public_key) is True


def test_algorithm_attr_is_ed25519():
    p = Ed25519SignatureProvider()
    assert p.algorithm == "ed25519"
