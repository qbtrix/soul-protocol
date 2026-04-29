# crypto/keystore.py — Minimal keystore for soul signing keys.
# Created: 2026-04-29 (#42) — Persists the soul's Ed25519 keypair inside
# the .soul archive at ``keys/private.key`` and ``keys/public.key``. Loads
# on awaken; generates a new keypair on first save when none exists.
#
# Threat model considerations:
#   - The private key is the soul's signing key. Compromise = the attacker
#     can append entries that pass verify_chain. Hence include_keys=False
#     on Soul.export() drops the private key, leaving only the public key
#     for verification on the receiving side.
#   - File mode 0o600 on private.key when written to a directory — best
#     effort on platforms that don't support chmod. zip archives carry no
#     filesystem permissions, so the only protection there is the optional
#     password encryption that already exists for .soul files.

from __future__ import annotations

import logging
import os
import stat
from pathlib import Path

logger = logging.getLogger(__name__)


PRIVATE_KEY_FILENAME = "keys/private.key"
PUBLIC_KEY_FILENAME = "keys/public.key"


class Keystore:
    """A pair of (private_key_bytes, public_key_bytes) with file I/O.

    The store does NOT generate keys itself — that's the
    :class:`Ed25519SignatureProvider`'s job. Keystore is just the
    serialization layer that knows where bytes live in a soul directory or
    archive.
    """

    def __init__(
        self,
        private_key_bytes: bytes | None = None,
        public_key_bytes: bytes | None = None,
    ) -> None:
        self.private_key_bytes = private_key_bytes
        self.public_key_bytes = public_key_bytes

    @property
    def has_private_key(self) -> bool:
        return self.private_key_bytes is not None

    @property
    def has_public_key(self) -> bool:
        return self.public_key_bytes is not None

    # ---------- Directory I/O (used by save_local / save_full) ----------

    def save_to_directory(
        self,
        soul_dir: Path,
        *,
        include_private: bool = True,
    ) -> None:
        """Write public.key (always) and private.key (when ``include_private``)
        under ``<soul_dir>/keys/``.

        Args:
            soul_dir: The soul's root directory (e.g. ``.soul/``).
            include_private: When False, only public.key is written. The
                soul stays verifiable but cannot append new entries until a
                private key is provided.
        """
        keys_dir = Path(soul_dir) / "keys"
        keys_dir.mkdir(parents=True, exist_ok=True)

        if self.public_key_bytes is not None:
            (keys_dir / "public.key").write_bytes(self.public_key_bytes)

        if include_private and self.private_key_bytes is not None:
            priv_path = keys_dir / "private.key"
            # Create the file with 0o600 permissions before writing bytes.
            fd = os.open(str(priv_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.write(fd, self.private_key_bytes)
            finally:
                os.close(fd)
            try:
                os.chmod(priv_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:  # pragma: no cover — Windows fallback
                pass

    @classmethod
    def load_from_directory(cls, soul_dir: Path) -> Keystore:
        """Load whatever keys exist under ``<soul_dir>/keys/``.

        Missing files are tolerated — the keystore returns a partial state.
        Callers decide what to do with a public-key-only keystore (verify
        works; append doesn't).
        """
        keys_dir = Path(soul_dir) / "keys"
        priv = keys_dir / "private.key"
        pub = keys_dir / "public.key"
        return cls(
            private_key_bytes=priv.read_bytes() if priv.exists() else None,
            public_key_bytes=pub.read_bytes() if pub.exists() else None,
        )

    # ---------- Archive (zip) I/O — exposed via plain dict for unpack/pack ----------

    def to_archive_files(self, *, include_private: bool = True) -> dict[str, bytes]:
        """Return a {filename: bytes} mapping for inclusion in a .soul zip.

        Filenames use forward slashes, matching ``zipfile`` conventions.
        """
        files: dict[str, bytes] = {}
        if self.public_key_bytes is not None:
            files[PUBLIC_KEY_FILENAME] = self.public_key_bytes
        if include_private and self.private_key_bytes is not None:
            files[PRIVATE_KEY_FILENAME] = self.private_key_bytes
        return files

    @classmethod
    def from_archive_files(cls, files: dict[str, bytes]) -> Keystore:
        """Reconstruct a keystore from an archive's {filename: bytes} map."""
        return cls(
            private_key_bytes=files.get(PRIVATE_KEY_FILENAME),
            public_key_bytes=files.get(PUBLIC_KEY_FILENAME),
        )


__all__ = ["Keystore", "PRIVATE_KEY_FILENAME", "PUBLIC_KEY_FILENAME"]
