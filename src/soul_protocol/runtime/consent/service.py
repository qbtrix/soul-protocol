# consent/service.py — Issue, revoke and enforce consent passes on a Soul.
# Created: 2026-11-14 — Signed passes, a consent.grant / consent.revoke chain
#   entry per lifecycle change, and ConsentSession: the app-side view that
#   re-checks the pass on every call and signs each read/write.
# Updated: 2026-11-25 (#326 review) — All consent API lives on
#   ConsentManager (``soul.consent``) instead of nine Soul members.
#   Revocation is checked against the signed consent.revoke chain entry, not
#   only the editable consent file. Only the soul's current key is trusted
#   (rotating the key invalidates outstanding passes). Repeated denials for a
#   pass are rate-limited and unknown tokens are only counted, so no token
#   holder can flush the log. Log trims are signed (consent.trim). Recall
#   reuses DomainIsolationMiddleware. App writes are tagged provenance=AGENT
#   with source "app:<id>", social writes are refused, and a write that can't
#   be audited is purged (chain-recorded) on any error.

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from soul_protocol.spec.memory import MemoryProvenance
from soul_protocol.spec.trust import compute_payload_hash

from ..exceptions import ConsentDeniedError, ConsentError
from ..middleware.domain_isolation import DomainIsolationMiddleware
from ..types import MemoryType
from .models import (
    APP_ID_PATTERN,
    MAX_PASS_DURATION,
    ConsentAccess,
    ConsentEvent,
    ConsentPass,
    TrimRecord,
    as_utc,
    hash_token,
    new_pass_id,
    new_token,
    parse_duration,
    utc_now,
)
from .registry import ConsentRegistry

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

#: Memory types an app may write. Social memories are relationship state
#: owned by the soul, and a consented recall would never return them.
WRITABLE_TYPES = (MemoryType.SEMANTIC, MemoryType.EPISODIC, MemoryType.PROCEDURAL)

#: Caps on request-supplied domain names echoed into denial lines.
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


class ConsentManager:
    """Owner-side consent API for one soul, reached as ``soul.consent``."""

    def __init__(self, soul: Soul, registry: ConsentRegistry | None = None) -> None:
        self._soul = soul
        self.registry = registry or ConsentRegistry()

    # ---------- Owner API ----------

    def grant(
        self,
        app_id: str,
        domains: Sequence[str],
        *,
        duration: timedelta | str | None = None,
        expires_at: datetime | None = None,
        access: ConsentAccess = "read",
        note: str = "",
        now: datetime | None = None,
    ) -> tuple[ConsentPass, str]:
        """Let ``app_id`` use ``domains`` until the pass expires or is revoked.

        Give exactly one of ``duration`` (a timedelta or text like ``"7d"``)
        or ``expires_at``. Returns ``(pass, token)``. Hand the token to the
        app; only its hash is stored, so it cannot be shown again. Signed
        onto the trust chain as ``consent.grant``.
        """
        app_id = (app_id or "").strip()
        if not APP_ID_PATTERN.match(app_id):
            raise ConsentError(
                f"Invalid app id {app_id!r}. Use 1-100 letters, digits, '.', '_', ':', '@' "
                "or '-', starting with a letter or digit."
            )
        if access not in ("read", "read_write"):
            raise ConsentError(f"Invalid access {access!r}. Use 'read' or 'read_write'.")
        clean_domains = _clean_domains(domains)
        if isinstance(duration, str):
            try:
                duration = parse_duration(duration)
            except ValueError as exc:
                raise ConsentError(str(exc)) from exc
        if (duration is None) == (expires_at is None):
            raise ConsentError("Give exactly one of duration or expires_at.")
        if not self._soul.can_sign:
            raise ConsentError(
                "This soul was loaded without its private key, so it cannot sign a "
                "consent pass. Load it with its keys to grant access."
            )

        issued_at = as_utc(now or utc_now())
        expiry = issued_at + duration if duration is not None else as_utc(expires_at)
        if expiry <= issued_at:
            raise ConsentError("The pass must expire in the future.")
        if expiry - issued_at > MAX_PASS_DURATION:
            raise ConsentError("A pass cannot last longer than 365 days.")

        self.registry.prune_inactive(issued_at)
        token = new_token()
        provider = self._soul.trust_chain_manager.provider
        consent_pass = ConsentPass(
            id=new_pass_id(),
            app_id=app_id,
            domains=clean_domains,
            access=access,
            issued_at=issued_at,
            expires_at=expiry,
            note=(note or "").strip(),
            token_hash=hash_token(token),
            soul_did=self._soul.did,
            public_key=provider.public_key,
        )
        consent_pass.signature = provider.sign(consent_pass.signing_message())

        self._record(
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
        self.registry.add(consent_pass)
        return consent_pass, token

    def revoke(self, pass_id: str, *, reason: str = "", now: datetime | None = None) -> ConsentPass:
        """Revoke a pass now. Works without the private key (then unsigned)."""
        consent_pass = self.registry.get(pass_id)
        if consent_pass is None:
            raise ConsentError(f"No consent pass with id {pass_id!r}.")
        if consent_pass.revoked_at is not None:
            return consent_pass
        at = as_utc(now or utc_now())
        consent_pass.revoked_at = at
        consent_pass.revoke_reason = (reason or "").strip()
        self._record(
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

    def session(self, token: str) -> ConsentSession:
        """The app-side view of the soul for ``token``. Checked on every call."""
        return ConsentSession(self, token)

    def get(self, pass_id: str) -> ConsentPass | None:
        return self.registry.get(pass_id)

    def passes(
        self, *, include_inactive: bool = False, app_id: str | None = None
    ) -> list[ConsentPass]:
        """Issued passes, newest first. Only active ones unless ``include_inactive``."""
        return self.registry.passes(include_inactive=include_inactive, app_id=app_id)

    def events(self, *, limit: int | None = None, app_id: str | None = None) -> list[ConsentEvent]:
        """The consent access log, newest first."""
        return self.registry.events(limit=limit, app_id=app_id)

    def verify(self) -> dict:
        """Check the access log against the signed trust chain (both directions)."""
        return self.registry.verify(self._soul.trust_chain)

    # ---------- Checks used by sessions ----------

    def chain_revoked(self, consent_pass: ConsentPass) -> bool:
        """True if the signed chain holds a consent.revoke entry for this pass."""
        for entry in self._soul.trust_chain.entries:
            if entry.action != "consent.revoke":
                continue
            candidate = ConsentEvent(
                kind="revoke",
                at=entry.timestamp,
                pass_id=consent_pass.id,
                app_id=consent_pass.app_id,
                domains=list(consent_pass.domains),
            )
            if entry.payload_hash == compute_payload_hash(candidate.chain_payload()):
                return True
        return False

    def is_revoked(self, consent_pass: ConsentPass) -> bool:
        return self.registry.logged_revocation(consent_pass) or self.chain_revoked(consent_pass)

    # ---------- Recording ----------

    def _record(self, event: ConsentEvent, *, require_signature: bool) -> ConsentEvent:
        """Sign ``event`` onto the trust chain, then add it to the access log.

        With ``require_signature`` the event is only logged once signed; a
        failure raises :class:`ConsentDeniedError` (``audit_unavailable``).
        Otherwise signing is best effort and the event is logged unsigned.
        """
        soul = self._soul
        if soul.can_sign:
            try:
                # A revoke's entry carries event.at as its timestamp so its
                # payload can be rebuilt from the pass (see chain_revoked).
                entry = soul.trust_chain_manager.append(
                    f"consent.{event.kind}",
                    event.chain_payload(),
                    timestamp=event.at if event.kind == "revoke" else None,
                )
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
        self.registry.record(event)
        self._trim(event.at)
        return event

    def _trim(self, at: datetime) -> None:
        """Drop the oldest lines past the cap, recorded by a signed consent.trim."""
        dropped = self.registry.overflow()
        if not dropped or not self._soul.can_sign:
            return  # without a key the log just grows; nothing can be signed away
        record = TrimRecord(at=at, seqs=[e.chain_seq for e in dropped if e.chain_seq is not None])
        try:
            entry = self._soul.trust_chain_manager.append("consent.trim", record.chain_payload())
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.warning("consent.trim_failed error=%s soul=%s", exc, self._soul.name)
            return
        record.chain_seq = entry.seq
        self.registry.apply_trim(dropped, record)


class ConsentSession:
    """An app's view of a soul, limited by one consent pass.

    The pass is re-checked on every call, so revocation and expiry take
    effect immediately, even for a session object that is still held.
    """

    def __init__(self, manager: ConsentManager, token: str) -> None:
        self._manager = manager
        self._soul = manager._soul
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
        registry = self._manager.registry
        if consent_pass is None:
            # Anyone can send a random token: count it, but never sign or log
            # it, so junk requests can't grow the chain or flush the log.
            registry.unknown_token_denials += 1
            return ConsentDeniedError(reason, detail=detail)
        count = registry.take_denial(consent_pass.id, reason, at)
        if count:
            self._manager._record(
                ConsentEvent(
                    kind="denied",
                    at=at,
                    pass_id=consent_pass.id,
                    app_id=consent_pass.app_id,
                    domains=[d[:_MAX_DOMAIN_CHARS] for d in (domains or [])[:_MAX_LOGGED_DOMAINS]],
                    count=count,
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
        at = as_utc(now or utc_now())
        consent_pass = self._manager.registry.find_by_token(self._token)
        if consent_pass is None:
            raise self._deny("unknown_token", None, domains=domains, at=at)
        if self._manager.is_revoked(consent_pass):
            raise self._deny("revoked", consent_pass, domains=domains, at=at)
        if at >= consent_pass.expires_at:
            raise self._deny("expired", consent_pass, domains=domains, at=at)
        provider_key = self._soul.trust_chain_manager.provider.public_key
        if (
            not consent_pass.signature_valid()
            or consent_pass.public_key != provider_key
            or consent_pass.soul_did != self._soul.did
        ):
            raise self._deny(
                "invalid_signature",
                consent_pass,
                domains=domains,
                at=at,
                detail="the pass was changed after signing, or signed by another key",
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
        requested = [domain] if domain is not None else []
        consent_pass = self._authorize(domains=requested, write=False, now=now)

        sandbox = DomainIsolationMiddleware(self._soul, allowed_domains=consent_pass.domains)
        results = await sandbox.recall(
            query,
            limit=limit,
            domain=domain,
            requester_id=_actor(consent_pass.app_id),
            bond_strength=CONSENT_BOND_STRENGTH,
        )

        # A revoke or expiry that landed while recall was awaiting still wins.
        self._authorize(domains=requested, write=False, now=now)
        self._manager._record(
            ConsentEvent(
                kind="read",
                at=as_utc(now or utc_now()),
                pass_id=consent_pass.id,
                app_id=consent_pass.app_id,
                domains=requested or list(consent_pass.domains),
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

        Defaults to the pass's first domain. The memory is tagged
        ``provenance=AGENT`` with ``source="app:<app_id>"`` and the write is
        signed as ``consent.write``.
        """
        if not content or not content.strip():
            raise ConsentError("content cannot be empty.")
        if type not in WRITABLE_TYPES:
            raise ConsentError(
                f"Apps cannot write {type.value} memories. Use semantic, episodic or procedural."
            )
        current = self._manager.registry.find_by_token(self._token)
        target = domain if domain is not None else (current.domains[0] if current else "")
        consent_pass = self._authorize(domains=[target], write=True, now=now)
        memory_id = await self._soul.remember(
            content,
            type=type,
            importance=importance,
            emotion=emotion,
            domain=target,
            provenance=MemoryProvenance.AGENT,
        )
        try:
            entry, _tier = await self._soul.memory.find_by_id(memory_id)
            if entry is not None:
                entry.source = _actor(consent_pass.app_id)
            # Re-check: a revoke that landed during the write still wins.
            self._authorize(domains=[target], write=True, now=now)
            self._manager._record(
                ConsentEvent(
                    kind="write",
                    at=as_utc(now or utc_now()),
                    pass_id=consent_pass.id,
                    app_id=consent_pass.app_id,
                    domains=[target],
                    count=1,
                    memory_ids=[memory_id],
                ),
                require_signature=True,
            )
        except BaseException:
            # Never keep an app write that isn't audited. purge() records the
            # removal on the chain when the soul can sign.
            await self._soul.purge(memory_id)
            raise
        return memory_id
