# broker.py — CredentialBroker Protocol + in-memory implementation.
# Updated: feat/retrieval-router — credential lifecycle journal emits are now
# fail-closed. If a journal is attached and the append raises, the broker
# lifts the exception out to the caller instead of silently issuing / using /
# revoking a credential that never made it into the audit trail. The router's
# retrieval.query emit stays fire-and-forget (query log, not auth) with a
# comment explaining the asymmetric policy. Also drop the local
# `_scopes_overlap` duplicate and import the public `scopes_overlap` helper
# from `soul_protocol.engine.journal`.
# Created: feat/retrieval-router — Workstream C1 of Org Architecture RFC (#164).
# The broker mints short-lived credentials for external sources (Drive,
# Salesforce, Snowflake, ...). Scoped per DSP scope so a credential
# acquired for `org:sales:*` cannot be reused by a requester operating in
# `org:support:*`. Every acquire/use/expire emits a journal event when a
# journal is attached — that's the audit trail Zero-Copy federation
# depends on.
#
# `InMemoryCredentialBroker` is the reference impl. Production deployments
# swap in a broker backed by the platform's real secret store; this class
# is the one the tests and local dev use.
#
# The `Credential.token` is deliberately an opaque string. Real brokers
# produce bearer tokens / OAuth access tokens / signed JWTs; the tests pass
# a predictable string so equality assertions work. Callers that need a
# structured token can wrap this class — `token` stays `str` here.

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from soul_protocol.engine.journal import Journal, scopes_overlap
from soul_protocol.spec.journal import Actor, EventEntry

from .exceptions import CredentialExpiredError, CredentialScopeError

DEFAULT_TTL_S: float = 300.0

# Back-compat alias for tests / callers that imported the private helper from
# this module before it moved into the public journal module. The semantics
# are the same; see `soul_protocol.engine.journal.scope.scopes_overlap` for
# the pinned policy (wildcard-grant vs specific-requester AND vice versa).
_scopes_overlap = scopes_overlap


class Credential(BaseModel):
    """A short-lived token issued by the broker.

    Fields:
        id: UUID for revocation + journal linking.
        source: The source this credential authorizes against
            (``"drive"``, ``"salesforce"``, ...).
        scopes: DSP scope patterns this credential is bound to.
        token: Opaque bearer string. Real brokers populate with real
            auth material; tests use a predictable value.
        acquired_at: tz-aware UTC timestamp of issuance.
        expires_at: tz-aware UTC timestamp after which `ensure_usable`
            raises `CredentialExpiredError`.
        last_used_at: Most recent `mark_used` timestamp, or `None`.
    """

    id: UUID = Field(default_factory=uuid4)
    source: str = Field(min_length=1)
    scopes: list[str] = Field(min_length=1)
    token: str = Field(min_length=1)
    acquired_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None

    def is_expired(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return now >= self.expires_at


class CredentialBroker(Protocol):
    def acquire(self, source: str, scopes: list[str]) -> Credential: ...
    def ensure_usable(self, credential: Credential, requester_scopes: list[str]) -> None: ...
    def mark_used(self, credential: Credential) -> None: ...
    def revoke(self, credential_id: UUID) -> None: ...


class InMemoryCredentialBroker:
    """Reference broker. Not persistent, not distributed — fine for
    single-process Paw OS instances and tests."""

    def __init__(
        self,
        *,
        ttl_s: float = DEFAULT_TTL_S,
        journal: Journal | None = None,
        broker_actor: Actor | None = None,
    ) -> None:
        self._ttl_s = ttl_s
        self._journal = journal
        self._actor = broker_actor or Actor(kind="system", id="system:credential-broker")
        self._active: dict[UUID, Credential] = {}

    # -- lifecycle --------------------------------------------------------

    def acquire(self, source: str, scopes: list[str]) -> Credential:
        now = datetime.now(UTC)
        cred = Credential(
            source=source,
            scopes=list(scopes),
            token=secrets.token_urlsafe(16),
            acquired_at=now,
            expires_at=now + timedelta(seconds=self._ttl_s),
        )
        # Emit FIRST. If the audit append fails under the fail-closed policy,
        # the credential never enters `_active` and the caller gets the
        # exception — no orphan credentials hanging around post-failure.
        self._emit("credential.acquired", cred)
        self._active[cred.id] = cred
        return cred

    def ensure_usable(self, credential: Credential, requester_scopes: list[str]) -> None:
        if credential.is_expired():
            # Surface through the journal once, then forget the credential.
            if credential.id in self._active:
                self._emit("credential.expired", credential)
                self._active.pop(credential.id, None)
            raise CredentialExpiredError(
                f"credential {credential.id} for {credential.source} expired at "
                f"{credential.expires_at.isoformat()}"
            )
        if not scopes_overlap(credential.scopes, requester_scopes):
            raise CredentialScopeError(
                f"credential {credential.id} scoped to {credential.scopes} "
                f"cannot be used by requester with scopes {requester_scopes}"
            )

    def mark_used(self, credential: Credential) -> None:
        credential.last_used_at = datetime.now(UTC)
        self._emit("credential.used", credential)

    def revoke(self, credential_id: UUID) -> None:
        cred = self._active.pop(credential_id, None)
        if cred is not None:
            self._emit("credential.expired", cred)

    # -- journal glue -----------------------------------------------------

    def _emit(self, action: str, cred: Credential) -> None:
        """Append a credential-lifecycle event. Fail-closed by design.

        If no journal is configured the caller has explicitly opted into
        fire-and-forget operation (tests, ephemeral scripts). With a journal
        attached, a failed append propagates: audit integrity outranks broker
        availability on the credential path, and silently issuing /
        revoking a credential whose lifecycle never made it into the log is
        worse than surfacing the error to the caller.

        Contrast with the router's `retrieval.query` emit, which stays
        fire-and-forget — that's a query log, not an auth trail.
        """
        if self._journal is None:
            return
        entry = EventEntry(
            id=uuid4(),
            ts=datetime.now(UTC),
            actor=self._actor,
            action=action,
            scope=list(cred.scopes),
            payload={
                "credential_id": str(cred.id),
                "source": cred.source,
                "expires_at": cred.expires_at.isoformat(),
            },
        )
        self._journal.append(entry)
