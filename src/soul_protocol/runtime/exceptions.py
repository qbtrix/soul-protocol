# exceptions.py — Custom exception classes for soul-protocol.
# Created: v0.3.2 — SoulFileNotFoundError, SoulCorruptError, SoulExportError,
#   SoulRetireError for proper error handling in awaken(), export(), retire().
# Updated: feat/onboarding-full — added SoulProtectedError, raised when callers try
#   to delete or retire a root governance soul (Org Architecture RFC #164, layer 1).
# Updated: 2026-04-29 (#41) — added DomainAccessError, raised by
#   :class:`soul_protocol.runtime.middleware.DomainIsolationMiddleware` when
#   the wrapped soul tries to write to a domain outside the allowed list.
# Updated: 2026-04-29 (#192) — added ReconsolidationWindowClosedError and
#   PredictionErrorOutOfBandError for the v0.5.0 brain-aligned memory update
#   primitives (confirm/update/supersede). The window error fires when
#   ``Soul.update()`` is called outside the 1-hour post-recall window;
#   the band error fires when the supplied prediction_error doesn't match
#   the verb's allowed band.

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


class DomainAccessError(SoulProtocolError):
    """Raised when a wrapped soul tries to use a memory domain it is not
    allowed to access.

    Used by :class:`soul_protocol.runtime.middleware.DomainIsolationMiddleware`
    on writes to a domain that isn't in the middleware's allow-list. Reads
    silently filter to the allowed domains instead of raising.
    """

    def __init__(self, requested: str, allowed: list[str]) -> None:
        self.requested = requested
        self.allowed = list(allowed)
        super().__init__(
            f"Domain {requested!r} is not in the allowed list "
            f"({', '.join(repr(a) for a in self.allowed) or 'none'}). "
            "DomainIsolationMiddleware blocks writes to disallowed domains."
        )


class ReconsolidationWindowClosedError(SoulProtocolError):
    """Raised by :meth:`Soul.update` when the reconsolidation window for
    a memory has closed.

    The window opens for a memory id whenever :meth:`Soul.recall` returns
    that entry, and stays open for one hour by default (per RFC #192).
    Outside the window the trace is "stable again" — in-place edits are
    refused; the caller must promote the change to :meth:`Soul.supersede`.
    """

    def __init__(self, memory_id: str, opened_at: str | None = None) -> None:
        self.memory_id = memory_id
        self.opened_at = opened_at
        hint = f" (last opened at {opened_at})" if opened_at else ""
        super().__init__(
            f"Reconsolidation window closed for memory {memory_id!r}{hint}. "
            "Call Soul.recall(...) on this id to reopen the window, "
            "or use Soul.supersede(...) to write a new orthogonal trace."
        )


class PredictionErrorOutOfBandError(SoulProtocolError):
    """Raised when a memory-update verb is called with a prediction_error
    score outside the verb's allowed band.

    Bands (per RFC #192, §3):
      - ``confirm``   → PE < 0.2
      - ``update``    → 0.2 <= PE < 0.85
      - ``supersede`` → PE >= 0.85

    The verbs are intentionally band-strict: the right verb for a given PE
    is also the right verb for what the caller is trying to do. A soft
    warning would let drift accumulate; a hard error keeps the contract
    tight.
    """

    def __init__(self, verb: str, prediction_error: float, allowed: str) -> None:
        self.verb = verb
        self.prediction_error = prediction_error
        self.allowed = allowed
        super().__init__(
            f"prediction_error={prediction_error} is outside the {verb!r} band "
            f"({allowed}). Use the verb whose band matches the PE: "
            "confirm for PE<0.2, update for 0.2<=PE<0.85, supersede for PE>=0.85."
        )
