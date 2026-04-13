# exceptions.py — Custom exception classes for soul-protocol.
# Created: v0.3.2 — SoulFileNotFoundError, SoulCorruptError, SoulExportError,
#   SoulRetireError for proper error handling in awaken(), export(), retire().
# Updated: feat/onboarding-full — added SoulProtectedError, raised when callers try
#   to delete or retire a root governance soul (Org Architecture RFC #164, layer 1).

from __future__ import annotations


class SoulProtocolError(Exception):
    """Base exception for all soul-protocol errors."""


class SoulFileNotFoundError(SoulProtocolError):
    """Raised when a soul file does not exist at the given path."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"No soul file at {path}")


class SoulCorruptError(SoulProtocolError):
    """Raised when a .soul archive is invalid or corrupted."""

    def __init__(self, path: str, reason: str = "") -> None:
        self.path = path
        self.reason = reason
        detail = f" — {reason}" if reason else ""
        super().__init__(f"Invalid .soul archive at {path}{detail}")


class SoulExportError(SoulProtocolError):
    """Raised when exporting a soul fails (disk full, permissions, etc.)."""

    def __init__(self, path: str, reason: str = "") -> None:
        self.path = path
        self.reason = reason
        detail = f" — {reason}" if reason else ""
        super().__init__(f"Failed to export soul to {path}{detail}")


class SoulRetireError(SoulProtocolError):
    """Raised when retiring a soul fails because memory preservation failed."""

    def __init__(self, reason: str = "") -> None:
        self.reason = reason
        super().__init__(f"Cannot retire soul: failed to save memories — {reason}")


class SoulEncryptedError(SoulProtocolError):
    """Raised when loading an encrypted .soul file without providing a password."""

    def __init__(self, soul_name: str = "") -> None:
        self.soul_name = soul_name
        hint = f" ({soul_name})" if soul_name else ""
        super().__init__(
            f"This .soul file{hint} is encrypted. "
            "Provide a password to decrypt it: Soul.awaken(path, password='...')"
        )


class SoulDecryptionError(SoulProtocolError):
    """Raised when decryption fails (wrong password or corrupted data)."""

    def __init__(self, reason: str = "wrong password or corrupted data") -> None:
        self.reason = reason
        super().__init__(f"Failed to decrypt .soul file — {reason}")


class SoulProtectedError(SoulProtocolError):
    """Raised when an operation is refused because the soul has a protected role.

    Currently the only protected role is ``"root"`` (an org governance soul).
    The only legitimate way to remove a root soul is ``soul org destroy``.
    """

    def __init__(self, name: str = "", role: str = "root", path: str | None = None) -> None:
        self.name = name
        self.role = role
        self.path = path
        who = name or path or "this soul"
        super().__init__(
            f"Refusing to delete {who}: role={role!r} is protected. "
            "Use `soul org destroy` to tear down an org instance."
        )
