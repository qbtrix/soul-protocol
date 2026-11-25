# consent/models.py — Data models for consent passes and the consent access log.
# Created: 2026-11-14 — ConsentPass (a signed, time-limited, domain-scoped
#   grant of memory access to one app) and ConsentEvent (one line in the
#   consent access log). Also the token + duration helpers used by the
#   service and the CLI.
# Updated: 2026-11-25 (#326 review) — Signing and verification no longer
#   import private helpers from spec.trust. ConsentEvent gains "trim" records
#   (signed lists of log lines dropped by the size cap). A revoke's chain
#   payload leaves out the free-text reason so the runtime can rebuild it from
#   the pass and the chain entry's timestamp and check revocation against the
#   signed chain, not just the editable consent file.

from __future__ import annotations

import base64
import hashlib
import json
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


def as_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC and normalise aware ones to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def canonical_bytes(data: Any) -> bytes:
    """Deterministic JSON bytes (sorted keys, compact) for signing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def verify_ed25519(message: bytes, signature_b64: str, public_key_b64: str) -> bool:
    """Verify an Ed25519 signature. Never raises."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        key.verify(base64.b64decode(signature_b64), message)
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


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
    the pass is issued, so any edit to them makes the pass invalid.
    ``revoked_at`` is outside the signature so a soul can revoke without
    its private key; the signed ``consent.revoke`` chain entry is what the
    runtime trusts (see ``ConsentManager``).
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
        return None if value is None else as_utc(value)

    def signed_fields(self) -> dict[str, Any]:
        """The exact dict the soul signs."""
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
        return canonical_bytes(self.signed_fields())

    def signature_valid(self) -> bool:
        """True when ``signature`` verifies against the embedded public key."""
        if not self.signature or not self.public_key:
            return False
        return verify_ed25519(self.signing_message(), self.signature, self.public_key)

    def status(self, now: datetime | None = None) -> ConsentStatus:
        if self.revoked_at is not None:
            return "revoked"
        if as_utc(now or utc_now()) >= self.expires_at:
            return "expired"
        return "active"

    def allows_domain(self, domain: str) -> bool:
        return domain in self.domains

    def ended_at(self) -> datetime:
        """When the pass stopped being usable (revocation or expiry)."""
        return self.revoked_at or self.expires_at

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

    ``chain_payload()`` is what gets hashed into the matching
    ``consent.<kind>`` trust-chain entry, and ``chain_seq`` points at that
    entry. For denials, ``count`` is how many refusals the line stands for
    (repeats within the rate-limit window are folded into the next line).
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
        return as_utc(value)

    def chain_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"chain_seq"})
        if self.kind == "revoke":
            # Rebuildable from the pass + chain timestamp, so the runtime can
            # check revocation against the signed chain. The reason is a note.
            payload.pop("reason", None)
        return payload

    def public_view(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class TrimRecord(BaseModel):
    """Signed record of log lines dropped by the access log's size cap."""

    at: datetime
    seqs: list[int]
    chain_seq: int | None = None

    @field_validator("at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    def chain_payload(self) -> dict[str, Any]:
        return {"at": self.at.isoformat(), "seqs": sorted(self.seqs)}
