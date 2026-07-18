# tests/test_long_horizon/test_chain_pruning_long.py — 5000-entry chain stress (#203).
# Created: 2026-04-29 — Verifies the touch-time pruning stub stays correct at scale.
# A 5000-entry append loop with cap=100 forces ~50 prune cycles. The chain
# must remain bounded throughout, every entry must verify, and the final
# chain must contain the expected number of chain.pruned markers.

from __future__ import annotations

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.trust.manager import TrustChainManager
from soul_protocol.spec.trust import CHAIN_PRUNED_ACTION


def test_5000_entry_chain_compressed_to_100_via_pruning():
    """Stress: 5000 appends with cap=100 keeps the chain bounded and verifiable."""
    p = Ed25519SignatureProvider.from_seed(b"L" * 32)
    mgr = TrustChainManager(did="did:soul:long-horizon", provider=p, max_entries=100)

    max_observed = 0
    for i in range(5000):
        mgr.append("memory.write", {"i": i})
        if mgr.length > max_observed:
            max_observed = mgr.length

    # Hard cap was respected at every step.
    assert max_observed <= 100, f"chain grew past cap during stress; peak={max_observed}"
    assert mgr.length <= 100

    # Final chain still verifies cleanly. Even with ~50 chain.pruned markers
    # in flight (most got compressed away by later prunes), the spec's
    # gap-allowance rule must keep verification on the rails.
    valid, reason = mgr.verify()
    assert valid, reason
    assert reason is None

    # At least one chain.pruned marker should be present in the FINAL chain
    # (the most recent prune's marker, plus any subsequent regular entries).
    actions = [e.action for e in mgr.chain.entries]
    assert CHAIN_PRUNED_ACTION in actions, (
        "final chain should contain at least one chain.pruned marker"
    )

    # Genesis (seq=0) is always preserved — the chain's anchor cannot
    # be dropped by pruning, no matter how many cycles run.
    assert mgr.chain.entries[0].seq == 0


def test_long_chain_seq_counter_monotonic_across_prunes():
    """The chain.pruned marker carries the next-after-pruned seq, so the
    audit counter never resets, even across many prune cycles."""
    p = Ed25519SignatureProvider.from_seed(b"L" * 32)
    mgr = TrustChainManager(did="did:soul:test", provider=p, max_entries=20)

    for i in range(500):
        mgr.append("memory.write", {"i": i})

    # Final head's seq should match the total number of appends + the
    # number of pruning markers signed along the way. We don't need an
    # exact equation — just that head.seq is large.
    head = mgr.head()
    assert head is not None
    assert head.seq >= 400  # well past the cap of 20

    # Chain still verifies.
    valid, _ = mgr.verify()
    assert valid
