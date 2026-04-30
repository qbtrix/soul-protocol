# tests/test_trust_chain/test_chain_pruning.py — Touch-time chain pruning tests (#203).
# Created: 2026-04-29 — Touch-time stub for the v0.5.0 unbounded-chain pain.
# Covers TrustChainManager.prune(keep), Biorhythms.trust_chain_max_entries,
# and the chain.pruned audit marker. Verification of pruned chains uses the
# spec-layer rule that allows a seq gap immediately preceding a chain.pruned
# entry (the only place a gap is permitted).

from __future__ import annotations

import pytest

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.trust.manager import TrustChainManager
from soul_protocol.runtime.types import Biorhythms
from soul_protocol.spec.trust import GENESIS_PREV_HASH


def _make_mgr() -> TrustChainManager:
    p = Ed25519SignatureProvider.from_seed(b"P" * 32)
    return TrustChainManager(did="did:soul:test", provider=p)


# ----------------------------- Biorhythms config -----------------------------


def test_biorhythms_trust_chain_max_entries_defaults_to_zero():
    """Default config preserves current behaviour — no pruning."""
    bio = Biorhythms()
    assert bio.trust_chain_max_entries == 0


def test_biorhythms_trust_chain_max_entries_accepts_positive_cap():
    bio = Biorhythms(trust_chain_max_entries=10)
    assert bio.trust_chain_max_entries == 10


def test_biorhythms_trust_chain_max_entries_rejects_negative():
    with pytest.raises(ValueError):
        Biorhythms(trust_chain_max_entries=-1)


# ----------------------------- prune() unit tests ---------------------------


def test_prune_no_op_on_empty_chain():
    mgr = _make_mgr()
    summary = mgr.prune(keep=10)
    assert summary["count"] == 0
    assert mgr.length == 0


def test_prune_no_op_when_under_cap():
    mgr = _make_mgr()
    for i in range(5):
        mgr.append("memory.write", {"i": i})
    summary = mgr.prune(keep=10)
    assert summary["count"] == 0
    assert mgr.length == 5


def test_prune_collapses_to_genesis_plus_marker():
    """Option C: pruning drops every non-genesis entry and appends a
    `chain.pruned` marker linking from genesis."""
    mgr = _make_mgr()
    for i in range(20):
        mgr.append("memory.write", {"i": i})

    assert mgr.length == 20
    head_seq_before = mgr.head().seq

    summary = mgr.prune(keep=10)

    # Dropped seq=1..19 → 19 entries
    assert summary["count"] == 19
    assert summary["low_seq"] == 1
    assert summary["high_seq"] == 19

    # Chain is now [genesis (seq=0), chain.pruned marker (seq=20)]
    assert mgr.length == 2
    genesis = mgr.chain.entries[0]
    marker = mgr.chain.entries[1]
    assert genesis.seq == 0
    assert genesis.prev_hash == GENESIS_PREV_HASH

    # Marker continues the seq counter (head_seq_before + 1)
    assert marker.seq == head_seq_before + 1
    assert marker.action == "chain.pruned"


def test_prune_marker_payload_carries_audit_metadata():
    mgr = _make_mgr()
    for i in range(15):
        mgr.append("memory.write", {"i": i})
    summary = mgr.prune(keep=5, reason="touch-time")
    assert summary["reason"] == "touch-time"
    assert summary["low_seq"] == 1
    assert summary["high_seq"] == 14
    assert summary["count"] == 14


def test_prune_preserves_genesis_entry():
    mgr = _make_mgr()
    for i in range(10):
        mgr.append("memory.write", {"i": i})
    genesis_before = mgr.chain.entries[0].model_copy(deep=True)
    mgr.prune(keep=3)
    genesis_after = mgr.chain.entries[0]
    assert genesis_after.seq == 0
    assert genesis_after.signature == genesis_before.signature
    assert genesis_after.payload_hash == genesis_before.payload_hash
    assert genesis_after.prev_hash == GENESIS_PREV_HASH


def test_prune_returns_zero_when_only_genesis():
    """A chain with only the genesis entry has nothing prunable."""
    mgr = _make_mgr()
    mgr.append("first", {})
    summary = mgr.prune(keep=1)
    # length=1 ≤ keep=1 → no-op
    assert summary["count"] == 0
    assert mgr.length == 1


# ----------------------------- verification ---------------------------------


def test_verify_chain_accepts_pruned_chain():
    mgr = _make_mgr()
    for i in range(50):
        mgr.append("memory.write", {"i": i})
    mgr.prune(keep=10)

    # Append a few more to confirm normal monotonicity resumes after the marker
    for i in range(3):
        mgr.append("memory.write", {"j": i})

    valid, reason = mgr.verify()
    assert valid, reason
    assert reason is None


def test_verify_chain_accepts_repeated_pruning():
    mgr = _make_mgr()
    for cycle in range(3):
        for i in range(20):
            mgr.append("memory.write", {"cycle": cycle, "i": i})
        mgr.prune(keep=5)
    # One more append after the last prune to exercise post-marker monotonicity
    mgr.append("memory.write", {"final": True})

    valid, reason = mgr.verify()
    assert valid, reason


def test_verify_rejects_chain_pruned_with_bad_prev_hash():
    """Even chain.pruned entries must link from the previous (genesis) hash."""
    mgr = _make_mgr()
    for i in range(10):
        mgr.append("memory.write", {"i": i})
    mgr.prune(keep=3)

    # Tamper with the marker's prev_hash
    marker = mgr.chain.entries[1]
    marker.prev_hash = "f" * 64

    valid, reason = mgr.verify()
    assert valid is False
    assert reason is not None


def test_verify_rejects_non_chain_pruned_with_seq_gap():
    """A normal action whose seq gaps from prev still fails monotonicity.

    Only chain.pruned action gets the gap pass.
    """
    mgr = _make_mgr()
    for i in range(5):
        mgr.append("memory.write", {"i": i})
    # Forge a non-chain.pruned gap by fudging seq directly on a model.
    mgr.chain.entries[3].seq = 99
    valid, reason = mgr.verify()
    assert valid is False
    assert reason is not None


# ----------------------------- append-time auto prune -----------------------


def test_auto_prune_on_append_when_cap_set():
    """When trust_chain_max_entries is set on the manager, append() prunes
    BEFORE adding the new entry once the cap is reached."""
    p = Ed25519SignatureProvider.from_seed(b"P" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p, max_entries=10)

    for i in range(100):
        mgr.append("memory.write", {"i": i})
        # Cap should never be exceeded after each append
        assert mgr.length <= 10, f"Chain grew past cap at iter {i}"

    # Final state should still verify
    valid, reason = mgr.verify()
    assert valid, reason


def test_auto_prune_disabled_when_cap_zero():
    """Default (cap=0) means the chain grows unbounded — preserves current behaviour."""
    p = Ed25519SignatureProvider.from_seed(b"P" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p, max_entries=0)
    for i in range(50):
        mgr.append("memory.write", {"i": i})
    assert mgr.length == 50
    valid, _ = mgr.verify()
    assert valid


def test_brief_scenario_100_entries_cap_10():
    """The brief's headline test: 100-entry chain with cap=10 collapses
    on the boundary."""
    p = Ed25519SignatureProvider.from_seed(b"P" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p, max_entries=10)
    for i in range(100):
        mgr.append("memory.write", {"i": i})
    # After many cycles, length is bounded
    assert mgr.length <= 10
    # And the chain stays verifiable
    valid, reason = mgr.verify()
    assert valid, reason
