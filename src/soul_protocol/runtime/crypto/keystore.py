# crypto/keystore.py — Minimal keystore for soul signing keys.
# Updated: 2026-04-29 (#204) — Added ``previous_public_keys`` allow-list so a
#   soul that rotates its signing key keeps verifying its older entries.
#   Persists alongside ``public.key`` / ``private.key`` as
#   ``keys/previous.keys`` (newline-separated base64 lines). Empty
#   allow-list keeps the prior strict-current-key behavior — opt-in.
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
#   - ``previous_public_keys`` is a forward-compatible field. A runtime
#     that rotates keys should append the rotated-out public key here
#     before installing the new one. Older runtimes that don't honor this
#     field will reject the rotated chain — that's the safe failure mode.

from __future__ import annotations

import base64
import logging
import os
import stat
from pathlib import Path

logger = logging.getLogger(__name__)


PRIVATE_KEY_FILENAME = "keys/private.key"
PUBLIC_KEY_FILENAME = "keys/public.key"
PREVIOUS_KEYS_FILENAME = "keys/previous.keys"


class Keystore:
    """A pair of (private_key_bytes, public_key_bytes) with file I/O.

    The store does NOT generate keys itself — that's the
    :class:`Ed25519SignatureProvider`'s job. Keystore is just the
    serialization layer that knows where bytes live in a soul directory or
    archive.

    ``previous_public_keys`` is an optional list of raw public-key bytes
    that previously signed entries on this soul's chain. When non-empty,
    :meth:`Soul.verify_chain` accepts entries whose ``public_key`` matches
    ANY of (current public key, any previous key) — enabling key rotation
    without breaking historical verification (#204).
    """

    def __init__(
        self,
        private_key_bytes: bytes | None = None,
        public_key_bytes: bytes | None = None,
        previous_public_keys: list[bytes] | None = None,
    ) -> None:
        self.private_key_bytes = private_key_bytes
        self.public_key_bytes = public_key_bytes
        self.previous_public_keys: list[bytes] = (
            list(previous_public_keys) if previous_public_keys else []
        )

    @property
    def has_private_key(self) -> bool:
        return self.private_key_bytes is not None

    @property
    def has_public_key(self) -> bool:
        return self.public_key_bytes is not None

    def add_previous_public_key(self, public_key_bytes: bytes) -> None:
        """Append ``public_key_bytes`` to the rotated-out allow-list.

        Idempotent: a key that's already present is ignored. Use this just
        before installing a new keypair so the chain entries signed by the
        old key continue to verify.
        """
        if not isinstance(public_key_bytes, (bytes, bytearray)):
            raise TypeError(
                f"add_previous_public_key expects bytes; got {type(public_key_bytes).__name__}"
            )
        if bytes(public_key_bytes) in self.previous_public_keys:
            return
        self.previous_public_keys.append(bytes(public_key_bytes))

    # ---------- Directory I/O (used by save_local / save_full) ----------

    def save_to_directory(
        self,
        soul_dir: Path,
        *,
        include_private: bool = True,
    ) -> None:
        """Write public.key (always) and private.key (when ``include_private``)
        under ``<soul_dir>/keys/``.

        Also writes ``previous.keys`` (newline-separated base64 entries)
        when the rotated-out allow-list is populated.

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

        if self.previous_public_keys:
            (keys_dir / "previous.keys").write_bytes(
                _encode_previous_keys(self.previous_public_keys)
            )

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
        prev = keys_dir / "previous.keys"
        return cls(
            private_key_bytes=priv.read_bytes() if priv.exists() else None,
            public_key_bytes=pub.read_bytes() if pub.exists() else None,
            previous_public_keys=(
                _decode_previous_keys(prev.read_bytes()) if prev.exists() else None
            ),
        )

    # ---------- Archive (zip) I/O — exposed via plain dict for unpack/pack ----------

    def to_archive_files(self, *, include_private: bool = True) -> dict[str, bytes]:
        """Return a {filename: bytes} mapping for inclusion in a .soul zip.

        Filenames use forward slashes, matching ``zipfile`` conventions.
        ``previous.keys`` is included only when the allow-list is
        non-empty; older runtimes that don't recognize the file will
        simply ignore it (forward-compatible).
        """
        files: dict[str, bytes] = {}
        if self.public_key_bytes is not None:
            files[PUBLIC_KEY_FILENAME] = self.public_key_bytes
        if include_private and self.private_key_bytes is not None:
            files[PRIVATE_KEY_FILENAME] = self.private_key_bytes
        if self.previous_public_keys:
            files[PREVIOUS_KEYS_FILENAME] = _encode_previous_keys(self.previous_public_keys)
        return files

    @classmethod
    def from_archive_files(cls, files: dict[str, bytes]) -> Keystore:
        """Reconstruct a keystore from an archive's {filename: bytes} map."""
        prev_blob = files.get(PREVIOUS_KEYS_FILENAME)
        return cls(
            private_key_bytes=files.get(PRIVATE_KEY_FILENAME),
            public_key_bytes=files.get(PUBLIC_KEY_FILENAME),
            previous_public_keys=_decode_previous_keys(prev_blob) if prev_blob else None,
        )


# ---------- Helpers (module-private) ----------


def _encode_previous_keys(keys: list[bytes]) -> bytes:
    """Encode a list of raw public-key bytes as newline-separated base64.

    One key per line, ``\\n`` separator, trailing newline. Stable and
    diff-friendly. Empty list → empty bytes (caller should skip writing).
    """
    if not keys:
        return b""
    return b"\n".join(base64.b64encode(k) for k in keys) + b"\n"


def _decode_previous_keys(blob: bytes) -> list[bytes]:
    """Decode a newline-separated base64 blob to a list of raw key bytes.

    Tolerates trailing newlines, blank lines, and whitespace. Lines that
    don't decode are skipped with a debug log — corrupted entries don't
    fail the whole keystore load.
    """
    out: list[bytes] = []
    for line in blob.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            out.append(base64.b64decode(text, validate=True))
        except (ValueError, base64.binascii.Error) as e:
            logger.debug("Skipping unreadable previous-key line: %s", e)
    return out


__all__ = [
    "Keystore",
    "PRIVATE_KEY_FILENAME",
    "PUBLIC_KEY_FILENAME",
    "PREVIOUS_KEYS_FILENAME",
]
