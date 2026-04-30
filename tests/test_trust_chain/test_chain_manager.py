# tests/test_trust_chain/test_chain_manager.py — TrustChainManager API tests.
# Updated: 2026-04-29 (#201) — audit_log() now returns a ``summary`` key on
# every row. Existing assertions about the row shape were broadened to
# include the new key.
# Created: 2026-04-29 (#42) — append() correctness, query() prefix matching,
# persistence round-trip, genesis-from-empty case.

from __future__ import annotations

import pytest

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.trust.manager import TrustChainManager
from soul_protocol.spec.trust import GENESIS_PREV_HASH


def test_genesis_entry_uses_genesis_prev_hash():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)

    e = mgr.append("memory.write", {"k": "v"})
    assert e.seq == 0
    assert e.prev_hash == GENESIS_PREV_HASH


def test_append_creates_verifiable_chain():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    for i in range(5):
        mgr.append("memory.write", {"i": i})
    assert mgr.length == 5
    assert mgr.verify() == (True, None)


def test_append_increments_seq_monotonically():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    a = mgr.append("a", {})
    b = mgr.append("b", {})
    c = mgr.append("c", {})
    assert (a.seq, b.seq, c.seq) == (0, 1, 2)


def test_query_prefix_matches_only_matching_actions():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    mgr.append("memory.write", {})
    mgr.append("evolution.proposed", {})
    mgr.append("memory.supersede", {})
    mgr.append("learning.event", {})

    memory_only = mgr.query("memory.")
    assert len(memory_only) == 2
    assert all(e.action.startswith("memory.") for e in memory_only)


def test_query_empty_prefix_returns_all():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    for _ in range(3):
        mgr.append("x", {})
    assert len(mgr.query("")) == 3


def test_head_returns_latest_entry():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    assert mgr.head() is None

    e1 = mgr.append("a", {})
    assert mgr.head() == e1

    e2 = mgr.append("b", {})
    assert mgr.head() == e2


def test_persistence_round_trip_preserves_chain():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    mgr.append("memory.write", {"i": 1})
    mgr.append("memory.write", {"i": 2})
    mgr.append("evolution.applied", {"mutation_id": "m1"})

    serialized = mgr.to_dict()
    restored = TrustChainManager.from_dict(serialized, provider=p)

    assert restored.length == mgr.length
    assert restored.verify() == (True, None)
    assert [e.action for e in restored.chain.entries] == [
        "memory.write",
        "memory.write",
        "evolution.applied",
    ]


def test_actor_did_defaults_to_manager_did():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test-soul", provider=p)
    e = mgr.append("x", {})
    assert e.actor_did == "did:soul:test-soul"


def test_actor_did_can_be_overridden():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:soul-a", provider=p)
    e = mgr.append("delegation.signed", {}, actor_did="did:soul:agent-b")
    assert e.actor_did == "did:soul:agent-b"


def test_audit_log_shape_and_filtering():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    mgr.append("memory.write", {})
    mgr.append("evolution.proposed", {})
    mgr.append("memory.supersede", {})

    log = mgr.audit_log(action_prefix="memory.")
    assert len(log) == 2
    for row in log:
        assert set(row.keys()) == {
            "seq",
            "timestamp",
            "action",
            "actor_did",
            "payload_hash",
            "summary",
        }
        assert row["action"].startswith("memory.")


def test_audit_log_limit_takes_tail():
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    for i in range(10):
        mgr.append("x", {"i": i})
    log = mgr.audit_log(limit=3)
    assert len(log) == 3
    assert [row["seq"] for row in log] == [7, 8, 9]


def test_payload_is_hashed_not_stored():
    """The chain stores only payload_hash; original payload is NOT recoverable."""
    p = Ed25519SignatureProvider.from_seed(b"M" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    secret_payload = {"secret": "do-not-leak", "tokens": ["t1", "t2"]}
    e = mgr.append("memory.write", secret_payload)

    serialized = mgr.to_dict()
    raw = str(serialized)
    assert "do-not-leak" not in raw
    assert "t1" not in raw
    assert e.payload_hash  # but the hash is there


def test_public_only_provider_blocks_append():
    """A provider with no public_key cannot append."""

    class NoOpProvider:
        algorithm = "ed25519"
        public_key = ""

        def sign(self, message):
            return ""

        def verify(self, message, signature, public_key):
            return False

    mgr = TrustChainManager(did="did:soul:test", provider=NoOpProvider())
    with pytest.raises(ValueError):
        mgr.append("x", {})
