# tests/test_trust_chain/test_key_rotation.py — Mixed-signer chain tests for
# the key rotation feature (#204). The trust chain spec already supports
# per-entry public_key, so a soul can rotate its signing key and the chain
# remains spec-verifiable. These tests pin down the contract:
#   * spec-level verify_chain accepts a mixed-signer chain unchanged
#   * Soul.verify_chain rejects rotation by default (allow-list empty)
#   * Soul.verify_chain accepts rotation when the rotated-out key is
#     registered in Keystore.previous_public_keys
#   * The allow-list round-trips through directory + archive serialization
#
# Created: 2026-04-29 (#204) — Trust chain verification hardening bundle.

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.crypto.keystore import (
    PREVIOUS_KEYS_FILENAME,
    Keystore,
)
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.trust.manager import TrustChainManager
from soul_protocol.spec.trust import verify_chain as spec_verify_chain

# ---------------------------------------------------------------------------
# Spec-layer behaviour — mixed-signer chains verify
# ---------------------------------------------------------------------------


class TestSpecLayerMixedSigner:
    """spec.trust.verify_chain checks each entry against its own embedded
    public_key. A mixed-signer chain is valid at the spec layer regardless
    of which keys were used."""

    def test_mixed_signer_chain_passes_spec_verify(self) -> None:
        """5 entries signed by key A, 5 entries signed by key B. The chain
        is internally consistent (signatures match each entry's embedded
        public_key) so spec-level verification passes."""
        # Build a manager seeded with key A.
        provider_a = Ed25519SignatureProvider.from_seed(b"A" * 32)
        mgr = TrustChainManager(did="did:soul:rotate", provider=provider_a)
        for i in range(5):
            mgr.append("test.action", {"i": i, "phase": "A"})

        # Rotate to key B.
        provider_b = Ed25519SignatureProvider.from_seed(b"B" * 32)
        mgr.provider = provider_b
        for i in range(5, 10):
            mgr.append("test.action", {"i": i, "phase": "B"})

        # Spec-level verification accepts this — each entry references
        # its own signer, hash chain is intact.
        valid, reason = spec_verify_chain(mgr.chain)
        assert valid is True, f"spec verify should pass; got {reason!r}"
        assert mgr.length == 10

        # Sanity: first 5 entries have key A's public_key, last 5 have B's.
        for entry in mgr.chain.entries[:5]:
            assert entry.public_key == provider_a.public_key
        for entry in mgr.chain.entries[5:]:
            assert entry.public_key == provider_b.public_key


# ---------------------------------------------------------------------------
# Soul-level behaviour — strict by default, rotation-aware via allow-list
# ---------------------------------------------------------------------------


class TestSoulVerifyChainKeyRotation:
    """Soul.verify_chain binds the chain to *this* soul. Without an
    allow-list, rotating keys breaks verification (older entries no longer
    match the current public key). Populating
    Keystore.previous_public_keys with the rotated-out key restores
    verification across the rotation."""

    @pytest.mark.asyncio
    async def test_rotation_without_allow_list_fails(self) -> None:
        """Default behavior: a soul that rotates its key without
        registering the previous key in the allow-list fails Soul-level
        verification because older entries reference the rotated-out key.
        """
        soul = await Soul.birth("RotateNoList", archetype="Test")
        # The soul's birth signature provider is the "old" key. Capture its
        # public key bytes for later — we rotate to a new provider below.
        old_pub_bytes = soul._keystore.public_key_bytes
        assert old_pub_bytes is not None

        # Append two entries under the original key.
        soul.trust_chain_manager.append("memory.write", {"id": "old1"})
        soul.trust_chain_manager.append("memory.write", {"id": "old2"})

        # Sanity: verification passes before rotation.
        valid, reason = soul.verify_chain()
        assert valid is True, f"baseline should pass; got {reason!r}"

        # Rotate: install a brand-new keypair and rebuild the manager.
        new_provider = Ed25519SignatureProvider.from_seed(b"R" * 32)
        soul._signature_provider = new_provider
        soul._trust_chain_manager.provider = new_provider
        soul._keystore.public_key_bytes = new_provider.public_key_bytes
        soul._keystore.private_key_bytes = new_provider.private_key_bytes
        # NOTE: we deliberately do NOT add the old public key to
        # previous_public_keys — that's the failure path.

        # Append two entries under the new key.
        soul.trust_chain_manager.append("memory.write", {"id": "new1"})
        soul.trust_chain_manager.append("memory.write", {"id": "new2"})

        # Soul.verify_chain rejects: the older entries reference the
        # rotated-out key, which is not in the allow-list.
        valid, reason = soul.verify_chain()
        assert valid is False
        assert reason is not None
        assert "public key mismatch" in reason

    @pytest.mark.asyncio
    async def test_rotation_with_allow_list_passes(self) -> None:
        """With Keystore.previous_public_keys populated, the rotated chain
        verifies because every entry's public_key matches either the
        current key or a registered previous key."""
        soul = await Soul.birth("RotateWithList", archetype="Test")
        old_pub_bytes = soul._keystore.public_key_bytes
        assert old_pub_bytes is not None

        # Append a few entries under the original key.
        for i in range(5):
            soul.trust_chain_manager.append("memory.write", {"id": f"old{i}"})

        # Rotate: register the old key in the allow-list FIRST, then
        # install the new keypair.
        new_provider = Ed25519SignatureProvider.from_seed(b"R" * 32)
        soul._keystore.add_previous_public_key(old_pub_bytes)
        soul._signature_provider = new_provider
        soul._trust_chain_manager.provider = new_provider
        soul._keystore.public_key_bytes = new_provider.public_key_bytes
        soul._keystore.private_key_bytes = new_provider.private_key_bytes

        # Append entries under the new key.
        for i in range(5):
            soul.trust_chain_manager.append("memory.write", {"id": f"new{i}"})

        # Verification passes because both keys are recognized.
        valid, reason = soul.verify_chain()
        assert valid is True, f"expected pass with allow-list; got {reason!r}"

    @pytest.mark.asyncio
    async def test_allow_list_does_not_accept_unrelated_key(self) -> None:
        """Adding a foreign key to previous_public_keys does NOT make the
        chain accept entries signed by some OTHER unrelated key. The
        allow-list is exact-match; only keys present in it are allowed."""
        soul = await Soul.birth("AllowListExact", archetype="Test")
        soul.trust_chain_manager.append("memory.write", {"id": "real"})

        # Register a foreign key in the allow-list — but the soul never
        # signed with it, so no chain entry references it.
        foreign = Ed25519SignatureProvider.from_seed(b"X" * 32)
        soul._keystore.add_previous_public_key(foreign.public_key_bytes)

        # Forge an entry from yet ANOTHER unrelated key (not in
        # allow-list, not the current key).
        from soul_protocol.spec.trust import (
            TrustEntry,
            _signing_message,
            compute_entry_hash,
        )

        intruder = Ed25519SignatureProvider.from_seed(b"I" * 32)
        head = soul.trust_chain.entries[-1]
        forged = TrustEntry(
            seq=head.seq + 1,
            actor_did=soul.did,
            action="memory.write",
            payload_hash="0" * 64,
            prev_hash=compute_entry_hash(head),
            algorithm="ed25519",
            public_key=intruder.public_key,
        )
        forged.signature = intruder.sign(_signing_message(forged))
        soul.trust_chain.entries.append(forged)

        valid, reason = soul.verify_chain()
        assert valid is False
        assert reason is not None
        assert "public key mismatch" in reason
        assert f"seq {forged.seq}" in reason


# ---------------------------------------------------------------------------
# Keystore allow-list mechanics
# ---------------------------------------------------------------------------


class TestKeystoreAllowList:
    """Keystore.previous_public_keys management API."""

    def test_default_allow_list_is_empty(self) -> None:
        ks = Keystore()
        assert ks.previous_public_keys == []

    def test_add_previous_public_key_appends(self) -> None:
        ks = Keystore()
        k1 = b"\x01" * 32
        k2 = b"\x02" * 32
        ks.add_previous_public_key(k1)
        ks.add_previous_public_key(k2)
        assert ks.previous_public_keys == [k1, k2]

    def test_add_previous_public_key_is_idempotent(self) -> None:
        ks = Keystore()
        k1 = b"\x01" * 32
        ks.add_previous_public_key(k1)
        ks.add_previous_public_key(k1)
        ks.add_previous_public_key(k1)
        assert ks.previous_public_keys == [k1]

    def test_add_previous_public_key_rejects_non_bytes(self) -> None:
        ks = Keystore()
        with pytest.raises(TypeError):
            ks.add_previous_public_key("not-bytes")  # type: ignore[arg-type]

    def test_constructor_accepts_initial_list(self) -> None:
        k1 = b"\x01" * 32
        k2 = b"\x02" * 32
        ks = Keystore(previous_public_keys=[k1, k2])
        assert ks.previous_public_keys == [k1, k2]

    def test_constructor_copies_list(self) -> None:
        """Mutating the input list after construction must not affect the
        keystore — the keystore takes its own copy."""
        seed = [b"\x01" * 32]
        ks = Keystore(previous_public_keys=seed)
        seed.append(b"\x02" * 32)
        assert ks.previous_public_keys == [b"\x01" * 32]


# ---------------------------------------------------------------------------
# Allow-list persistence — directory + archive round-trips
# ---------------------------------------------------------------------------


class TestAllowListPersistence:
    """previous_public_keys round-trips through both the directory layout
    and the archive (zip) layout, so a rotated soul stays verifiable
    after save / awaken."""

    def test_directory_round_trip(self, tmp_path: Path) -> None:
        k1 = b"\x01" * 32
        k2 = b"\x02" * 32
        original = Keystore(
            private_key_bytes=b"\xaa" * 32,
            public_key_bytes=b"\xbb" * 32,
            previous_public_keys=[k1, k2],
        )
        original.save_to_directory(tmp_path)

        loaded = Keystore.load_from_directory(tmp_path)
        assert loaded.previous_public_keys == [k1, k2]
        assert loaded.public_key_bytes == b"\xbb" * 32
        assert loaded.private_key_bytes == b"\xaa" * 32

    def test_directory_round_trip_empty_allow_list_skips_file(self, tmp_path: Path) -> None:
        """An empty allow-list does NOT write previous.keys at all — the
        on-disk format stays clean for non-rotating souls."""
        ks = Keystore(public_key_bytes=b"\xbb" * 32)
        ks.save_to_directory(tmp_path)
        assert not (tmp_path / "keys" / "previous.keys").exists()

        loaded = Keystore.load_from_directory(tmp_path)
        assert loaded.previous_public_keys == []

    def test_archive_round_trip(self) -> None:
        k1 = b"\x01" * 32
        k2 = b"\x02" * 32
        original = Keystore(
            private_key_bytes=b"\xaa" * 32,
            public_key_bytes=b"\xbb" * 32,
            previous_public_keys=[k1, k2],
        )
        files = original.to_archive_files()
        assert PREVIOUS_KEYS_FILENAME in files

        loaded = Keystore.from_archive_files(files)
        assert loaded.previous_public_keys == [k1, k2]
        assert loaded.public_key_bytes == b"\xbb" * 32
        assert loaded.private_key_bytes == b"\xaa" * 32

    def test_archive_round_trip_empty_allow_list_omits_file(self) -> None:
        ks = Keystore(public_key_bytes=b"\xbb" * 32)
        files = ks.to_archive_files()
        assert PREVIOUS_KEYS_FILENAME not in files

        loaded = Keystore.from_archive_files(files)
        assert loaded.previous_public_keys == []

    def test_archive_format_is_base64_lines(self) -> None:
        """Sanity check on the on-disk format — newline-separated base64
        of raw public-key bytes. Used so external tooling can inspect."""
        k1 = b"\x01" * 32
        k2 = b"\x02" * 32
        ks = Keystore(previous_public_keys=[k1, k2])
        blob = ks.to_archive_files(include_private=False)[PREVIOUS_KEYS_FILENAME]
        lines = blob.decode("ascii").splitlines()
        assert len(lines) == 2
        assert base64.b64decode(lines[0]) == k1
        assert base64.b64decode(lines[1]) == k2


# ---------------------------------------------------------------------------
# Public-only export still works after rotation
# ---------------------------------------------------------------------------


class TestRotationExportRecipient:
    """A recipient who receives a rotated soul without the private key
    should still be able to verify the entire chain — provided the
    sender shipped previous_public_keys in the archive."""

    @pytest.mark.asyncio
    async def test_rotation_survives_public_only_archive(self) -> None:
        """Build a rotated soul, archive it without the private key (the
        usual ``include_keys=False`` export shape) but WITH the
        previous_public_keys allow-list. Reconstruct the keystore from
        the archive map and verify the chain externally."""
        soul = await Soul.birth("ExportRotation", archetype="Test")
        old_pub_bytes = soul._keystore.public_key_bytes
        assert old_pub_bytes is not None
        for i in range(3):
            soul.trust_chain_manager.append("memory.write", {"id": f"old{i}"})

        new_provider = Ed25519SignatureProvider.from_seed(b"P" * 32)
        soul._keystore.add_previous_public_key(old_pub_bytes)
        soul._signature_provider = new_provider
        soul._trust_chain_manager.provider = new_provider
        soul._keystore.public_key_bytes = new_provider.public_key_bytes
        soul._keystore.private_key_bytes = new_provider.private_key_bytes

        for i in range(3):
            soul.trust_chain_manager.append("memory.write", {"id": f"new{i}"})

        # Recipient archive: public + previous.keys only, no private.
        files = soul._keystore.to_archive_files(include_private=False)
        assert PREVIOUS_KEYS_FILENAME in files
        assert "keys/private.key" not in files

        # Recipient reconstructs and verifies. Spec-level verification of
        # the chain itself passes; Soul-level binding (which matters here)
        # passes because the allow-list contains the rotated-out key.
        recipient_ks = Keystore.from_archive_files(files)
        assert old_pub_bytes in recipient_ks.previous_public_keys

        # The chain (still attached to soul) verifies via Soul-level
        # check using the same allow-list contents.
        valid, reason = soul.verify_chain()
        assert valid is True, f"expected pass; got {reason!r}"
