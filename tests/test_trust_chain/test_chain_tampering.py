# tests/test_trust_chain/test_chain_tampering.py — Adversarial verification tests.
# Created: 2026-04-29 (#42) — Modify content / signature / seq / insert bogus
# entries — verify() must catch each.

from __future__ import annotations

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.trust.manager import TrustChainManager
from soul_protocol.spec.trust import TrustEntry, compute_payload_hash, verify_chain


def _seeded_chain(seed_byte: bytes = b"T", n: int = 5) -> TrustChainManager:
    p = Ed25519SignatureProvider.from_seed(seed_byte * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p)
    for i in range(n):
        mgr.append("memory.write", {"i": i})
    return mgr


def test_modify_action_after_signing():
    mgr = _seeded_chain()
    mgr.chain.entries[2].action = "evil.action"
    valid, reason = mgr.verify()
    assert valid is False
    assert reason is not None


def test_modify_payload_hash_after_signing():
    mgr = _seeded_chain()
    mgr.chain.entries[2].payload_hash = "a" * 64
    valid, reason = mgr.verify()
    assert valid is False


def test_modify_signature_after_signing():
    mgr = _seeded_chain()
    sig = mgr.chain.entries[1].signature
    # Flip a bit in the base64 signature
    mgr.chain.entries[1].signature = "AAAA" + sig[4:]
    valid, reason = mgr.verify()
    assert valid is False


def test_modify_seq_numbers():
    mgr = _seeded_chain()
    # Swap two entries' seqs to make them non-monotonic.
    mgr.chain.entries[1].seq = 99
    valid, reason = mgr.verify()
    assert valid is False


def test_modify_actor_did():
    mgr = _seeded_chain()
    mgr.chain.entries[2].actor_did = "did:soul:attacker"
    valid, reason = mgr.verify()
    assert valid is False


def test_modify_public_key():
    """Swapping in a different public key should fail signature verification."""
    mgr = _seeded_chain()
    other = Ed25519SignatureProvider.from_seed(b"X" * 32)
    mgr.chain.entries[2].public_key = other.public_key
    valid, reason = mgr.verify()
    assert valid is False


def test_insert_bogus_entry_in_middle():
    """Inserting a freshly-signed entry in the middle breaks the chain."""
    mgr = _seeded_chain(n=4)
    # Make a brand-new genesis-like entry and shove it at position 2.
    p = Ed25519SignatureProvider.from_seed(b"T" * 32)
    bogus = TrustEntry(
        seq=2,
        actor_did="did:soul:test",
        action="memory.write",
        payload_hash=compute_payload_hash({"injected": True}),
        prev_hash="0" * 64,  # wrong — should be hash of entries[1]
        public_key=p.public_key,
    )
    from soul_protocol.spec.trust import _signing_message

    bogus.signature = p.sign(_signing_message(bogus))

    # Insert and shift downstream seqs would make this inconsistent — we
    # leave seqs as-is to force a duplicate seq=2.
    mgr.chain.entries.insert(2, bogus)
    valid, reason = mgr.verify()
    assert valid is False


def test_truncating_chain_preserves_validity():
    """A prefix of a valid chain stays verifiable — there's no anti-truncation
    guarantee in the chain itself; that's left to the receiver-side policy."""
    mgr = _seeded_chain(n=5)
    truncated = mgr.chain.entries[:3]
    chain = mgr.chain.model_copy(update={"entries": truncated})
    assert verify_chain(chain) == (True, None)


def test_swap_two_entries():
    """Swapping two entries breaks the chain."""
    mgr = _seeded_chain()
    mgr.chain.entries[1], mgr.chain.entries[2] = (
        mgr.chain.entries[2],
        mgr.chain.entries[1],
    )
    valid, reason = mgr.verify()
    assert valid is False


def test_replay_genesis_entry():
    """A second copy of entry 0 cannot pass verify."""
    mgr = _seeded_chain(n=3)
    duplicate_genesis = mgr.chain.entries[0].model_copy()
    mgr.chain.entries.append(duplicate_genesis)
    valid, reason = mgr.verify()
    assert valid is False
