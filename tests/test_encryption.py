# test_encryption.py — Tests for .soul file encryption at rest.
# Updated: feat/soul-encryption — Use precise SoulDecryptionError instead of
#   (SoulDecryptionError, Exception) in test_awaken_encrypted_wrong_password.
# Created: feat/soul-encryption — Covers encrypt/decrypt round-trip, wrong password,
#   no password on encrypted file, backward compat, manifest readability, and
#   the Soul.export()/Soul.awaken() integration with passwords.

from __future__ import annotations

import io
import json
import zipfile

import pytest

from soul_protocol.runtime.exceptions import SoulDecryptionError, SoulEncryptedError
from soul_protocol.runtime.export.crypto import decrypt_blob, encrypt_blob
from soul_protocol.runtime.export.pack import pack_soul
from soul_protocol.runtime.export.unpack import unpack_soul
from soul_protocol.runtime.types import Identity, SoulConfig


# ============ Fixtures ============


@pytest.fixture
def config() -> SoulConfig:
    """Return a SoulConfig for encryption tests."""
    return SoulConfig(
        identity=Identity(
            name="Aria",
            did="did:soul:aria-abc123",
            archetype="The Compassionate Creator",
            core_values=["empathy", "creativity"],
        ),
    )


@pytest.fixture
def memory_data() -> dict:
    """Return sample memory data for encryption tests."""
    return {
        "core": {"persona": "I am Aria.", "human": "User is kind."},
        "episodic": [
            {
                "id": "ep1",
                "type": "episodic",
                "content": "User told me a secret",
                "importance": 9,
                "confidence": 1.0,
                "entities": [],
                "created_at": "2026-03-10T00:00:00",
                "access_count": 0,
            }
        ],
        "semantic": [
            {
                "id": "sem1",
                "type": "semantic",
                "content": "User prefers Python",
                "importance": 8,
                "confidence": 1.0,
                "entities": [],
                "created_at": "2026-03-10T00:00:00",
                "access_count": 0,
            }
        ],
        "procedural": [],
        "graph": {"entities": {"Alice": "person"}, "edges": []},
    }


# ============ Low-level crypto tests ============


class TestCryptoBlob:
    """Tests for the encrypt_blob / decrypt_blob primitives."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypting then decrypting returns the original data."""
        plaintext = b"Hello, Soul Protocol!"
        password = "strong-password-123"

        encrypted = encrypt_blob(plaintext, password)
        assert encrypted != plaintext
        assert len(encrypted) > len(plaintext)

        decrypted = decrypt_blob(encrypted, password)
        assert decrypted == plaintext

    def test_wrong_password_raises(self):
        """Decrypting with the wrong password raises ValueError."""
        encrypted = encrypt_blob(b"secret data", "correct-password")

        with pytest.raises(ValueError, match="wrong password"):
            decrypt_blob(encrypted, "wrong-password")

    def test_corrupted_data_raises(self):
        """Decrypting corrupted data raises ValueError."""
        encrypted = encrypt_blob(b"test", "password")
        corrupted = encrypted[:16] + b"\x00" * 12 + encrypted[28:]

        with pytest.raises(ValueError):
            decrypt_blob(corrupted, "password")

    def test_too_short_data_raises(self):
        """Data shorter than salt+nonce+tag raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            decrypt_blob(b"short", "password")

    def test_different_salts_produce_different_ciphertext(self):
        """Same plaintext + password produces different ciphertext each time."""
        plaintext = b"same data"
        password = "same-password"

        enc1 = encrypt_blob(plaintext, password)
        enc2 = encrypt_blob(plaintext, password)
        assert enc1 != enc2  # different salts and nonces

    def test_empty_plaintext(self):
        """Encrypting empty bytes works correctly."""
        encrypted = encrypt_blob(b"", "password")
        decrypted = decrypt_blob(encrypted, "password")
        assert decrypted == b""

    def test_large_payload(self):
        """Encrypting a large payload works correctly."""
        plaintext = b"x" * 1_000_000  # 1 MB
        encrypted = encrypt_blob(plaintext, "password")
        decrypted = decrypt_blob(encrypted, "password")
        assert decrypted == plaintext


# ============ Pack/unpack encryption tests ============


class TestPackUnpackEncryption:
    """Tests for encrypted pack_soul / unpack_soul."""

    async def test_encrypted_roundtrip(self, config: SoulConfig):
        """Encrypted pack then decrypt produces identical config."""
        password = "my-secret-password"

        packed = await pack_soul(config, password=password)
        restored, memory_data = await unpack_soul(packed, password=password)

        assert restored.identity.name == "Aria"
        assert restored.identity.did == "did:soul:aria-abc123"
        assert restored.identity.archetype == "The Compassionate Creator"
        assert restored.identity.core_values == ["empathy", "creativity"]

    async def test_encrypted_roundtrip_with_memory(
        self, config: SoulConfig, memory_data: dict
    ):
        """Encrypted roundtrip preserves full memory data."""
        password = "memory-password"

        packed = await pack_soul(config, memory_data=memory_data, password=password)
        restored_config, restored_memory = await unpack_soul(packed, password=password)

        assert restored_config.identity.name == "Aria"
        assert restored_memory["core"]["persona"] == "I am Aria."
        assert len(restored_memory["episodic"]) == 1
        assert restored_memory["episodic"][0]["content"] == "User told me a secret"
        assert restored_memory["graph"]["entities"]["Alice"] == "person"

    async def test_encrypted_file_without_password_raises(self, config: SoulConfig):
        """Loading an encrypted archive without a password raises SoulEncryptedError."""
        packed = await pack_soul(config, password="secret")

        with pytest.raises(SoulEncryptedError, match="encrypted"):
            await unpack_soul(packed)

    async def test_encrypted_file_wrong_password_raises(self, config: SoulConfig):
        """Loading an encrypted archive with the wrong password raises SoulDecryptionError."""
        packed = await pack_soul(config, password="correct-password")

        with pytest.raises(SoulDecryptionError, match="wrong password"):
            await unpack_soul(packed, password="wrong-password")

    async def test_unencrypted_backward_compat(self, config: SoulConfig):
        """Unencrypted archives still load fine (no password needed)."""
        packed = await pack_soul(config)
        restored, _ = await unpack_soul(packed)

        assert restored.identity.name == "Aria"

    async def test_unencrypted_with_password_still_works(self, config: SoulConfig):
        """Passing a password to an unencrypted archive is a no-op, not an error."""
        packed = await pack_soul(config)
        restored, _ = await unpack_soul(packed, password="unnecessary-password")

        assert restored.identity.name == "Aria"

    async def test_manifest_readable_without_password(self, config: SoulConfig):
        """The manifest.json is always unencrypted and readable."""
        password = "encryption-password"
        packed = await pack_soul(config, password=password)

        buf = io.BytesIO(packed)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()

            # manifest.json should be present (not manifest.json.enc)
            assert "manifest.json" in names
            assert "manifest.json.enc" not in names

            manifest = json.loads(zf.read("manifest.json"))
            assert manifest["encrypted"] is True
            assert manifest["soul_name"] == "Aria"
            assert manifest["soul_id"] == "did:soul:aria-abc123"

    async def test_encrypted_files_have_enc_extension(self, config: SoulConfig):
        """Encrypted archives contain .enc files, not plain files."""
        packed = await pack_soul(config, password="test")

        buf = io.BytesIO(packed)
        with zipfile.ZipFile(buf, "r") as zf:
            names = set(zf.namelist())

        assert "soul.json.enc" in names
        assert "soul.json" not in names
        assert "state.json.enc" in names
        assert "dna.md.enc" in names
        assert "memory/core.json.enc" in names

    async def test_unencrypted_manifest_flag_false(self, config: SoulConfig):
        """Unencrypted archives have encrypted=false in manifest."""
        packed = await pack_soul(config)

        buf = io.BytesIO(packed)
        with zipfile.ZipFile(buf, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))
            assert manifest["encrypted"] is False

    async def test_encrypted_error_includes_soul_name(self, config: SoulConfig):
        """SoulEncryptedError message includes the soul name from manifest."""
        packed = await pack_soul(config, password="secret")

        with pytest.raises(SoulEncryptedError) as exc_info:
            await unpack_soul(packed)

        assert "Aria" in str(exc_info.value)


# ============ Soul.export() / Soul.awaken() integration ============


class TestSoulEncryptionIntegration:
    """Integration tests for Soul.export() and Soul.awaken() with encryption."""

    async def test_export_and_awaken_with_password(self, tmp_path):
        """Soul.export(password=...) then Soul.awaken(password=...) round-trips."""
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name="Aria", personality="A curious soul")
        await soul.remember("The user loves sunsets", importance=8)

        soul_path = tmp_path / "aria.soul"
        await soul.export(soul_path, password="sunset-password")

        restored = await Soul.awaken(soul_path, password="sunset-password")
        assert restored.name == "Aria"

    async def test_awaken_encrypted_without_password(self, tmp_path):
        """Soul.awaken() on encrypted file without password raises SoulEncryptedError."""
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name="Kairos")
        soul_path = tmp_path / "kairos.soul"
        await soul.export(soul_path, password="locked")

        with pytest.raises(SoulEncryptedError):
            await Soul.awaken(soul_path)

    async def test_awaken_encrypted_wrong_password(self, tmp_path):
        """Soul.awaken() with wrong password raises SoulDecryptionError."""
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name="Kairos")
        soul_path = tmp_path / "kairos.soul"
        await soul.export(soul_path, password="correct")

        with pytest.raises(SoulDecryptionError):
            await Soul.awaken(soul_path, password="incorrect")

    async def test_awaken_encrypted_bytes(self):
        """Soul.awaken() works with encrypted bytes (not just file paths)."""
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name="Echo")
        from soul_protocol.runtime.export.pack import pack_soul

        data = await pack_soul(soul.serialize(), password="bytes-pw")

        restored = await Soul.awaken(data, password="bytes-pw")
        assert restored.name == "Echo"

    async def test_export_without_password_backward_compat(self, tmp_path):
        """Soul.export() without password still works (unencrypted)."""
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name="Aria")
        soul_path = tmp_path / "aria.soul"
        await soul.export(soul_path)

        restored = await Soul.awaken(soul_path)
        assert restored.name == "Aria"
