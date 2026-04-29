# tests/test_trust_chain/test_pubkey_binding.py — Verify that Soul.verify_chain
# binds the chain to the loaded keystore's public key.
# Created: 2026-04-29 — Closes the "swap signature + public_key" attack where a
# tamperer regenerates an internally-valid chain with their own keypair. The
# chain by itself is self-consistent, but it doesn't belong to *this* soul. The
# pubkey-binding check in Soul.verify_chain catches that.

from __future__ import annotations

import base64

import pytest

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.soul import Soul


@pytest.mark.asyncio
async def test_chain_with_foreign_pubkey_fails_verification():
    """A chain signed by a different key, with that key embedded per-entry,
    must fail Soul.verify_chain even though it would pass spec-level
    verify_chain (which only checks chain-internal consistency).
    """
    soul = await Soul.birth("PubkeyTest", archetype="Test")

    # Append a real entry signed by the soul's own key.
    soul.trust_chain_manager.append("memory.write", {"id": "real"})

    # Fabricate a "foreign" provider — different keypair entirely.
    foreign = Ed25519SignatureProvider.from_seed(b"F" * 32)

    # Build a forged entry whose public_key field claims the foreign key
    # signed it. The signature is real (from the foreign key), so the
    # chain-internal verify_chain would accept it.
    from soul_protocol.spec.trust import TrustEntry, _signing_message, compute_entry_hash

    head = soul.trust_chain.entries[-1]
    forged = TrustEntry(
        seq=head.seq + 1,
        actor_did=soul.did,
        action="memory.write",
        payload_hash="0" * 64,
        prev_hash=compute_entry_hash(head),
        algorithm="ed25519",
        public_key=foreign.public_key,
    )
    forged.signature = foreign.sign(_signing_message(forged))
    soul.trust_chain.entries.append(forged)

    # Spec-level verify_chain accepts it (chain is internally consistent).
    from soul_protocol.spec.trust import verify_chain as spec_verify

    spec_valid, _ = spec_verify(soul.trust_chain)
    assert spec_valid, "spec verify_chain should pass for an internally-consistent chain"

    # Soul.verify_chain catches it because the foreign entry's public_key
    # doesn't match the loaded keystore.
    soul_valid, reason = soul.verify_chain()
    assert soul_valid is False
    assert reason is not None
    assert "public key mismatch" in reason
    assert f"seq {forged.seq}" in reason


@pytest.mark.asyncio
async def test_chain_with_matching_pubkey_passes_verification():
    """Sanity: an honestly signed chain still verifies."""
    soul = await Soul.birth("HonestTest", archetype="Test")
    soul.trust_chain_manager.append("memory.write", {"id": "a"})
    soul.trust_chain_manager.append("memory.write", {"id": "b"})

    valid, reason = soul.verify_chain()
    assert valid is True, f"expected pass, got reason={reason!r}"


@pytest.mark.asyncio
async def test_verify_chain_skips_pubkey_check_when_keystore_empty(tmp_path):
    """Freshly-birthed souls before first save have a keystore with bytes
    populated (private + public from the in-memory provider). Confirm the
    binding check is non-blocking on the normal birth path.
    """
    soul = await Soul.birth("FreshSoul", archetype="Test")
    # Keystore is populated at birth (provider's bytes copied into keystore
    # in Soul.__init__). Verification should still pass with a new chain.
    assert soul._keystore.has_public_key
    soul.trust_chain_manager.append("memory.write", {"id": "x"})
    valid, reason = soul.verify_chain()
    assert valid is True, f"expected pass, got reason={reason!r}"


@pytest.mark.asyncio
async def test_chain_genesis_with_foreign_pubkey_also_caught():
    """The pubkey check must catch a forged genesis entry too — not just
    appended entries. An attacker who replaces an entire shared soul's
    chain with their own genesis-onwards chain shouldn't pass verification
    on the recipient side.
    """
    soul = await Soul.birth("GenesisTest", archetype="Test")
    foreign = Ed25519SignatureProvider.from_seed(b"X" * 32)

    from soul_protocol.spec.trust import (
        GENESIS_PREV_HASH,
        TrustEntry,
        _signing_message,
    )

    forged_genesis = TrustEntry(
        seq=0,
        actor_did=soul.did,
        action="memory.write",
        payload_hash="0" * 64,
        prev_hash=GENESIS_PREV_HASH,
        algorithm="ed25519",
        public_key=foreign.public_key,
    )
    forged_genesis.signature = foreign.sign(_signing_message(forged_genesis))

    # Replace the chain entirely.
    soul.trust_chain.entries.clear()
    soul.trust_chain.entries.append(forged_genesis)

    valid, reason = soul.verify_chain()
    assert valid is False
    assert reason is not None
    assert "public key mismatch" in reason

    # Sanity: the keystore's public key is NOT the foreign one.
    expected = base64.b64encode(soul._keystore.public_key_bytes).decode("ascii")
    assert expected != foreign.public_key
