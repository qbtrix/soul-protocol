# consent/service.py — Issue, revoke and enforce consent passes on a Soul.
# Created: 2026-11-14 — grant_pass / revoke_pass write a signed pass and a
#   consent.grant / consent.revoke trust-chain entry. ConsentSession is what an
#   app holds: every recall/remember re-checks the pass (revoked? expired?
#   signature intact? domain allowed? write allowed?) at call time, filters
#   results to the pass's domains, and appends a signed consent.read /
#   consent.write entry. A read or write that cannot be signed is refused
#   ("audit_unavailable") so there is never an unaudited app access. Denials
#   are logged as consent.denied (signed when the soul can sign).
# Updated: 2026-11-14 (review) — Unknown-token denials are only counted (no
#   chain entry, no log line) so unauthenticated junk cannot grow the chain or
#   flush the log. Domains echoed into denial events are capped. Revocation is
#   also read from the access log. The pass is re-checked after recall/remember
#   finish, so a revoke that lands mid-call still wins. Recall returns copies.

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ..exceptions import ConsentDeniedError, ConsentError
from ..types import MemoryType
from .models import (
    APP_ID_PATTERN,
    MAX_PASS_DURATION,
    ConsentAccess,
    ConsentEvent,
    ConsentPass,
    _as_utc,
    hash_token,
    new_pass_id,
    new_token,
    utc_now,
)

if TYPE_CHECKING:
    from ..soul import Soul
    from ..types import MemoryEntry

logger = logging.getLogger(__name__)

#: Bond strength used for consented reads. The pass is the owner's explicit
#: permission, so BONDED memories in the granted domains are visible.
#: PRIVATE memories are never returned to an app (requester_id is set).
CONSENT_BOND_STRENGTH = 100.0

#: Upper bound on results per consented recall.
MAX_RECALL_LIMIT = 100

#: Caps on request-supplied domain names echoed into denial events.
_MAX_LOGGED_DOMAINS = 20
_MAX_DOMAIN_CHARS = 100


def _actor(app_id: str) -> str:
    return f"app:{app_id}"


def _clean_domains(domains: Sequence[str]) -> list[str]:
    if isinstance(domains, str):
        domains = [domains]
    cleaned: list[str] = []
    for raw in domains or []:
        if not isinstance(raw, str):
            raise ConsentError(f"Domain names must be strings, got {raw!r}.")
        domain = raw.strip()
        if not domain:
            raise ConsentError("Domain names cannot be empty.")
        if domain == "*":
            raise ConsentError("Wildcard '*' is not allowed. List each domain the app may use.")
        if domain not in cleaned:
            cleaned.append(domain)
    if not cleaned:
        raise ConsentError("A consent pass needs at least one domain.")
    return cleaned


def _record(
    soul: Soul,
    event: ConsentEvent,
    *,
    require_signature: bool,
) -> ConsentEvent:
    """Sign ``event`` onto the trust chain, then add it to the access log.

    With ``require_signature`` the event is only logged once it is signed;
    a failure raises :class:`ConsentDeniedError` (``audit_unavailable``).
    Otherwise signing is best effort and the event is logged unsigned.
    """
    if soul.can_sign:
        try:
            entry = soul.trust_chain_manager.append(f"consent.{event.kind}", event.chain_payload())
            event.chain_seq = entry.seq
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.warning(
                "consent.chain_append_failed kind=%s error_type=%s error=%s soul=%s",
                event.kind,
                type(exc).__name__,
                exc,
                soul.name,
            )
            if require_signature:
                raise ConsentDeniedError(
                    "audit_unavailable",
                    pass_id=event.pass_id,
                    app_id=event.app_id,
                    detail="the access could not be signed onto the trust chain",
                ) from exc
    elif require_signature:
        raise ConsentDeniedError(
            "audit_unavailable",
            pass_id=event.pass_id,
            app_id=event.app_id,
            detail="this soul was loaded without its private key",
        )
    soul.consent.record(event)
    return event


def grant_pass(
    soul: Soul,
    app_id: str,
    domains: Sequence[str],
    *,
    duration: timedelta | None = None,
    expires_at: datetime | None = None,
    access: ConsentAccess = "read",
    note: str = "",
    now: datetime | None = None,
) -> tuple[ConsentPass, str]:
    """Issue a signed pass. Returns ``(pass, token)``; the token is not stored."""
    app_id = (app_id or "").strip()
    if not APP_ID_PATTERN.match(app_id):
        raise ConsentError(
            f"Invalid app id {app_id!r}. Use 1-100 letters, digits, '.', '_', ':', '@' "
            "or '-', starting with a letter or digit."
        )
    if access not in ("read", "read_write"):
        raise ConsentError(f"Invalid access {access!r}. Use 'read' or 'read_write'.")
    clean_domains = _clean_domains(domains)
    if (duration is None) == (expires_at is None):
        raise ConsentError("Give exactly one of duration or expires_at.")
    if not soul.can_sign:
        raise ConsentError(
            "This soul was loaded without its private key, so it cannot sign a "
            "consent pass. Load it with its keys to grant access."
        )

    issued_at = _as_utc(now or utc_now())
    expiry = issued_at + duration if duration is not None else _as_utc(expires_at)
    if expiry <= issued_at:
        raise ConsentError("The pass must expire in the future.")
    if expiry - issued_at > MAX_PASS_DURATION:
        raise ConsentError("A pass cannot last longer than 365 days.")

    token = new_token()
    consent_pass = ConsentPass(
        id=new_pass_id(),
        app_id=app_id,
        domains=clean_domains,
        access=access,
        issued_at=issued_at,
        expires_at=expiry,
        note=(note or "").strip(),
        token_hash=hash_token(token),
        soul_did=soul.did,
        public_key=soul.trust_chain_manager.provider.public_key,
    )
    consent_pass.signature = soul.trust_chain_manager.provider.sign(consent_pass.signing_message())

    _record(
        soul,
        ConsentEvent(
            kind="grant",
            at=issued_at,
            pass_id=consent_pass.id,
            app_id=app_id,
            domains=clean_domains,
            reason=f"access={access}; expires_at={expiry.isoformat()}",
        ),
        require_signature=True,
    )
    soul.consent.add(consent_pass)
    return consent_pass, token


def revoke_pass(
    soul: Soul,
    pass_id: str,
    *,
    reason: str = "",
    now: datetime | None = None,
) -> ConsentPass:
    """Revoke a pass immediately. Works even when the soul cannot sign."""
    consent_pass = soul.consent.get(pass_id)
    if consent_pass is None:
        raise ConsentError(f"No consent pass with id {pass_id!r}.")
    if consent_pass.revoked_at is not None:
        return consent_pass
    at = _as_utc(now or utc_now())
    consent_pass.revoked_at = at
    consent_pass.revoke_reason = (reason or "").strip()
    _record(
        soul,
        ConsentEvent(
            kind="revoke",
            at=at,
            pass_id=consent_pass.id,
            app_id=consent_pass.app_id,
            domains=list(consent_pass.domains),
            reason=consent_pass.revoke_reason,
        ),
        require_signature=False,
    )
    return consent_pass


class ConsentSession:
    """An app's view of a soul, limited by one consent pass.

    The pass is re-checked on every call, so revocation and expiry take
    effect immediately, even for a session object that is still held.
    """

    def __init__(self, soul: Soul, token: str) -> None:
        self._soul = soul
        self._token = token

    def current_pass(self, now: datetime | None = None) -> ConsentPass:
        """The valid pass behind this session, or raise ConsentDeniedError."""
        return self._authorize(domains=None, write=False, now=now)

    def _deny(
        self,
        reason: str,
        consent_pass: ConsentPass | None,
        *,
        domains: list[str] | None,
        at: datetime,
        detail: str = "",
    ) -> ConsentDeniedError:
        if consent_pass is None:
            # Anyone can send a random token. Count it, but don't sign or log
            # it, so junk requests can't grow the chain or push real events
            # out of the access log.
            self._soul.consent.unknown_token_denials += 1
            return ConsentDeniedError(reason, detail=detail)
        _record(
            self._soul,
            ConsentEvent(
                kind="denied",
                at=at,
                pass_id=consent_pass.id,
                app_id=consent_pass.app_id,
                domains=[d[:_MAX_DOMAIN_CHARS] for d in (domains or [])[:_MAX_LOGGED_DOMAINS]],
                reason=reason,
            ),
            require_signature=False,
        )
        return ConsentDeniedError(
            reason, pass_id=consent_pass.id, app_id=consent_pass.app_id, detail=detail
        )

    def _authorize(
        self,
        *,
        domains: list[str] | None,
        write: bool,
        now: datetime | None,
    ) -> ConsentPass:
        at = _as_utc(now or utc_now())
        consent_pass = self._soul.consent.find_by_token(self._token)
        if consent_pass is None:
            raise self._deny("unknown_token", None, domains=domains, at=at)
        if self._soul.consent.was_revoked(consent_pass):
            raise self._deny("revoked", consent_pass, domains=domains, at=at)
        if at >= consent_pass.expires_at:
            raise self._deny("expired", consent_pass, domains=domains, at=at)
        if (
            not consent_pass.signature_valid()
            or consent_pass.public_key not in self._soul.trusted_public_keys()
            or consent_pass.soul_did != self._soul.did
        ):
            raise self._deny(
                "invalid_signature",
                consent_pass,
                domains=domains,
                at=at,
                detail="the stored pass was changed after it was signed",
            )
        for domain in domains or []:
            if not consent_pass.allows_domain(domain):
                raise self._deny(
                    "domain_not_allowed",
                    consent_pass,
                    domains=domains,
                    at=at,
                    detail=f"domain {domain!r} is not in this pass",
                )
        if write and consent_pass.access != "read_write":
            raise self._deny("write_not_allowed", consent_pass, domains=domains, at=at)
        if (domains is not None or write) and not self._soul.can_sign:
            raise self._deny(
                "audit_unavailable",
                consent_pass,
                domains=domains,
                at=at,
                detail="this soul was loaded without its private key",
            )
        return consent_pass

    async def recall(
        self,
        query: str,
        *,
        limit: int = 10,
        domain: str | None = None,
        now: datetime | None = None,
    ) -> list[MemoryEntry]:
        """Recall memories from the pass's domains (or one of them).

        PRIVATE memories are never returned. Each call is signed onto the
        trust chain as ``consent.read`` with the ids of what was returned.
        """
        limit = max(1, min(MAX_RECALL_LIMIT, int(limit)))
        requested = [domain] if domain is not None else None
        consent_pass = self._authorize(domains=requested or [], write=False, now=now)
        targets = requested or list(consent_pass.domains)

        per_domain: list[list[MemoryEntry]] = []
        for target in targets:
            per_domain.append(
                await self._soul.recall(
                    query,
                    limit=limit,
                    domain=target,
                    requester_id=_actor(consent_pass.app_id),
                    bond_strength=CONSENT_BOND_STRENGTH,
                )
            )

        # Round-robin merge keeps each domain's own ranking and gives every
        # granted domain a fair share. The final filter is a hard guarantee
        # that nothing outside the pass leaves this method.
        allowed = set(consent_pass.domains)
        results: list[MemoryEntry] = []
        seen: set[str] = set()
        for rank in range(limit):
            for bucket in per_domain:
                if rank < len(bucket):
                    entry = bucket[rank]
                    if entry.id not in seen and (entry.domain or "default") in allowed:
                        seen.add(entry.id)
                        results.append(entry)
        results = results[:limit]

        # A revoke or expiry that landed while recall was awaiting still wins.
        self._authorize(domains=requested or [], write=False, now=now)

        _record(
            self._soul,
            ConsentEvent(
                kind="read",
                at=_as_utc(now or utc_now()),
                pass_id=consent_pass.id,
                app_id=consent_pass.app_id,
                domains=targets,
                count=len(results),
                memory_ids=[r.id for r in results],
            ),
            require_signature=True,
        )
        # Copies, so an in-process app cannot edit the soul's stored entries.
        return [entry.model_copy(deep=True) for entry in results]

    async def remember(
        self,
        content: str,
        *,
        domain: str | None = None,
        type: MemoryType = MemoryType.SEMANTIC,
        importance: int = 5,
        emotion: str | None = None,
        now: datetime | None = None,
    ) -> str:
        """Store a memory in one of the pass's domains (needs ``read_write``).

        Defaults to the pass's first domain. Signed as ``consent.write``.
        """
        if not content or not content.strip():
            raise ConsentError("content cannot be empty.")
        current = self._soul.consent.find_by_token(self._token)
        target = domain if domain is not None else (current.domains[0] if current else "")
        consent_pass = self._authorize(domains=[target], write=True, now=now)
        memory_id = await self._soul.remember(
            content,
            type=type,
            importance=importance,
            emotion=emotion,
            domain=target,
        )
        try:
            # Re-check: a revoke that landed during the write still wins.
            self._authorize(domains=[target], write=True, now=now)
            _record(
                self._soul,
                ConsentEvent(
                    kind="write",
                    at=_as_utc(now or utc_now()),
                    pass_id=consent_pass.id,
                    app_id=consent_pass.app_id,
                    domains=[target],
                    count=1,
                    memory_ids=[memory_id],
                ),
                require_signature=True,
            )
        except ConsentDeniedError:
            # Never keep an app write that was revoked mid-call or is missing
            # from the audit trail.
            await self._soul.forget_by_id(memory_id)
            raise
        return memory_id
