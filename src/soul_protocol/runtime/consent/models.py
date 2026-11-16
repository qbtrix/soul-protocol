# consent/models.py — Data models for consent passes and the consent access log.
# Created: 2026-11-14 — ConsentPass (a signed, time-limited, domain-scoped
#   grant of memory access to one app) and ConsentEvent (one line in the
#   consent access log: grant / revoke / read / write / denied). Also the
#   token + duration helpers shared by the registry, CLI, MCP and gateway.

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ConsentAccess = Literal["read", "read_write"]
ConsentStatus = Literal["active", "expired", "revoked"]
ConsentEventKind = Literal["grant", "revoke", "read", "write", "denied"]

#: Prefix on every consent token so leaked tokens are easy to recognise.
TOKEN_PREFIX = "scp_"

#: App ids are short, printable identifiers ("fitness-app", "com.acme.notes").
APP_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,99}$")

#: Longest pass a soul will issue. Long-lived access should be re-granted.
MAX_PASS_DURATION = timedelta(days=365)

_DURATION_PATTERN = re.compile(r"^\s*(\d+)\s*([mhdw])\s*$", re.IGNORECASE)
_DURATION_UNITS = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC and normalise aware ones to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_duration(text: str) -> timedelta:
    """Parse ``"30m"``, ``"12h"``, ``"7d"`` or ``"2w"`` into a timedelta.

    Raises ``ValueError`` for anything else, for zero, and for durations
    longer than :data:`MAX_PASS_DURATION`.
    """
    match = _DURATION_PATTERN.match(text or "")
    if not match:
        raise ValueError(
            f"Invalid duration {text!r}. Use a number followed by m, h, d or w "
            "(for example 30m, 12h, 7d, 2w)."
        )
    amount = int(match.group(1))
    if amount <= 0:
        raise ValueError("Duration must be greater than zero.")
    delta = timedelta(**{_DURATION_UNITS[match.group(2).lower()]: amount})
    if delta > MAX_PASS_DURATION:
        raise ValueError("Duration cannot be longer than 365 days.")
    return delta


def new_token() -> str:
    """Return a fresh, unguessable consent token (shown to the owner once)."""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex of a token. Only the hash is ever stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_pass_id() -> str:
    return "cp_" + secrets.token_hex(6)


class ConsentPass(BaseModel):
    """A signed grant letting one app use some of a soul's memory domains.

    The fields that define what the pass allows (app, domains, access,
    times, token hash, issuer) are signed with the soul's Ed25519 key when
    the pass is issued, so any edit to them in the stored file makes the
    pass invalid. ``revoked_at`` is deliberately outside the signature: a
    soul must always be able to revoke, even when it cannot sign.
    """

    id: str
    app_id: str
    domains: list[str] = Field(min_length=1)
    access: ConsentAccess = "read"
    issued_at: datetime
    expires_at: datetime
    note: str = ""
    token_hash: str
    soul_did: str
    public_key: str = ""
    signature: str = ""
    revoked_at: datetime | None = None
    revoke_reason: str = ""

    @field_validator("issued_at", "expires_at", "revoked_at")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value)

    def signed_fields(self) -> dict[str, Any]:
        """The exact dict the soul signs. Order-independent (canonical JSON)."""
        return {
            "id": self.id,
            "app_id": self.app_id,
            "domains": list(self.domains),
            "access": self.access,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "note": self.note,
            "token_hash": self.token_hash,
            "soul_did": self.soul_did,
            "public_key": self.public_key,
        }

    def signing_message(self) -> bytes:
        from soul_protocol.spec.trust import _canonical_json

        return _canonical_json(self.signed_fields())

    def signature_valid(self) -> bool:
        """True when ``signature`` verifies against the embedded public key."""
        if not self.signature or not self.public_key:
            return False
        from soul_protocol.spec.trust import _verify_with_algorithm

        try:
            return _verify_with_algorithm(
                "ed25519", self.signing_message(), self.signature, self.public_key
            )
        except Exception:
            return False

    def status(self, now: datetime | None = None) -> ConsentStatus:
        if self.revoked_at is not None:
            return "revoked"
        if _as_utc(now or utc_now()) >= self.expires_at:
            return "expired"
        return "active"

    def allows_domain(self, domain: str) -> bool:
        return domain in self.domains

    def public_view(self, now: datetime | None = None) -> dict[str, Any]:
        """JSON-safe description for CLI / MCP / dashboard. Never includes the token."""
        return {
            "id": self.id,
            "app_id": self.app_id,
            "domains": list(self.domains),
            "access": self.access,
            "status": self.status(now),
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoke_reason": self.revoke_reason,
            "note": self.note,
            "signature_valid": self.signature_valid(),
        }


class ConsentEvent(BaseModel):
    """One line of the consent access log.

    ``chain_payload()`` is exactly what gets hashed into the matching
    ``consent.<kind>`` trust-chain entry, so the readable log can be checked
    against the signed chain (see :meth:`ConsentRegistry.verify_events`).
    """

    kind: ConsentEventKind
    at: datetime
    pass_id: str | None = None
    app_id: str | None = None
    domains: list[str] = Field(default_factory=list)
    count: int = 0
    memory_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    chain_seq: int | None = None

    @field_validator("at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _as_utc(value)

    def chain_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"chain_seq"})

    def public_view(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
