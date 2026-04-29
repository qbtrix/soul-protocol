# tests/test_trust_chain/test_trust_chain.py — verify_chain happy / unhappy paths.
# Created: 2026-04-29 (#42) — Tampered signature, broken hash link,
# non-monotonic seq, duplicate seq, future timestamps. Empty chain.

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.trust.manager import TrustChainManager
from soul_protocol.spec.trust import (
    GENESIS_PREV_HASH,
    TrustChain,
    TrustEntry,
    chain_integrity_check,
    verify_chain,
)


def _build_chain(n: int = 3) -> TrustChainManager:
    p = Ed25519SignatureProvider.from_seed(b"S" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    for i in range(n):
        mgr.append("test.action", {"i": i})
    return mgr


def test_empty_chain_verifies():
    chain = TrustChain(did="did:soul:empty")
    assert verify_chain(chain) == (True, None)


def test_valid_chain_verifies():
    mgr = _build_chain(5)
    assert mgr.verify() == (True, None)


def test_tampered_signature_fails_verification():
    mgr = _build_chain(3)
    mgr.chain.entries[1].signature = "AAAA" + mgr.chain.entries[1].signature[4:]
    valid, reason = mgr.verify()
    assert valid is False
    assert "seq 1" in (reason or "")


def test_broken_hash_chain_fails_verification():
    mgr = _build_chain(3)
    # Change a content field on entry 1 — its hash changes — entry 2's
    # prev_hash is now wrong.
    mgr.chain.entries[1].payload_hash = "f" * 64
    valid, reason = mgr.verify()
    assert valid is False
    # Either signature or chain link will be flagged. Either is acceptable —
    # both prove tampering.
    assert reason is not None


def test_non_monotonic_seq_fails_verification():
    mgr = _build_chain(3)
    mgr.chain.entries[2].seq = 1  # duplicate of entries[1]
    valid, reason = mgr.verify()
    assert valid is False
    assert reason is not None


def test_duplicate_seq_is_caught():
    mgr = _build_chain(2)
    duplicate = mgr.chain.entries[1].model_copy()
    mgr.chain.entries.append(duplicate)
    valid, reason = mgr.verify()
    assert valid is False
    assert "duplicate seq" in (reason or "")


def test_future_timestamp_fails_verification():
    mgr = _build_chain(2)
    future = datetime.now(UTC) + timedelta(hours=1)
    mgr.chain.entries[0].timestamp = future
    valid, reason = mgr.verify()
    assert valid is False
    assert "future" in (reason or "")


def test_genesis_seq_must_be_zero():
    """A chain whose first entry has seq != 0 fails verification."""
    p = Ed25519SignatureProvider.from_seed(b"S" * 32)
    bad = TrustEntry(
        seq=5,  # invalid — first entry must be 0
        timestamp=datetime.now(UTC),
        actor_did="did:soul:test",
        action="x.y",
        payload_hash="a" * 64,
        prev_hash=GENESIS_PREV_HASH,
        public_key=p.public_key,
    )
    from soul_protocol.spec.trust import _signing_message

    bad.signature = p.sign(_signing_message(bad))
    chain = TrustChain(did="did:soul:test", entries=[bad])
    valid, reason = verify_chain(chain)
    assert valid is False


def test_genesis_prev_hash_must_be_constant():
    """Genesis entry whose prev_hash isn't GENESIS_PREV_HASH fails."""
    p = Ed25519SignatureProvider.from_seed(b"S" * 32)
    bad = TrustEntry(
        seq=0,
        timestamp=datetime.now(UTC),
        actor_did="did:soul:test",
        action="x.y",
        payload_hash="a" * 64,
        prev_hash="b" * 64,  # not genesis
        public_key=p.public_key,
    )
    from soul_protocol.spec.trust import _signing_message

    bad.signature = p.sign(_signing_message(bad))
    chain = TrustChain(did="did:soul:test", entries=[bad])
    valid, reason = verify_chain(chain)
    assert valid is False


def test_chain_integrity_check_summary():
    mgr = _build_chain(4)
    summary = chain_integrity_check(mgr.chain)
    assert summary["valid"] is True
    assert summary["length"] == 4
    assert summary["first_failure"] is None
    assert summary["signers"] == ["did:soul:test"]


def test_chain_integrity_check_reports_failure():
    mgr = _build_chain(3)
    mgr.chain.entries[2].signature = "AAAA" + mgr.chain.entries[2].signature[4:]
    summary = chain_integrity_check(mgr.chain)
    assert summary["valid"] is False
    assert summary["first_failure"] is not None
    assert summary["first_failure"]["seq"] == 2
