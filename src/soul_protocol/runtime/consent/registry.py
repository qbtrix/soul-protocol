# consent/registry.py — In-memory store of a soul's consent passes + access log.
# Created: 2026-11-14 — ConsentRegistry holds every issued ConsentPass and a
#   bounded log of ConsentEvents. Persisted as ``consent/consent.json`` inside
#   the soul (directory saves and .soul archives). Pure data: issuing,
#   checking and auditing live in consent/service.py.
# Updated: 2026-11-14 (review) — verify_events checks both directions: every
#   log line must match a signed chain entry AND every signed consent.* entry
#   must still be in the log (so deleted lines are caught). Events trimmed by
#   the size cap are tracked via ``trimmed_through_seq`` so they are not
#   reported as missing. ``was_revoked`` also consults the log. Unknown-token
#   denials are only counted, not logged, so junk requests cannot flush it.

from __future__ import annotations

import hmac
import logging
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from soul_protocol.spec.trust import TrustChain, compute_payload_hash

from .models import ConsentEvent, ConsentPass, hash_token

logger = logging.getLogger(__name__)

#: Newest events kept in the readable log. Older ones stay provable through
#: their trust-chain entries (until the chain itself is pruned).
MAX_EVENTS = 1000

_FORMAT_VERSION = 1


class ConsentRegistry:
    """All consent passes a soul has issued, plus the consent access log."""

    def __init__(self, max_events: int = MAX_EVENTS) -> None:
        self._passes: dict[str, ConsentPass] = {}
        self._events: list[ConsentEvent] = []
        self.max_events = max_events
        #: Highest chain seq among events dropped by the size cap.
        self.trimmed_through_seq: int | None = None
        #: Requests refused because their token matched no pass.
        self.unknown_token_denials = 0

    # ---------- Passes ----------

    def add(self, consent_pass: ConsentPass) -> None:
        self._passes[consent_pass.id] = consent_pass

    def get(self, pass_id: str) -> ConsentPass | None:
        return self._passes.get(pass_id)

    def find_by_token(self, token: str) -> ConsentPass | None:
        """Return the pass whose token hash matches ``token`` (constant-time compare)."""
        if not token:
            return None
        wanted = hash_token(token)
        found: ConsentPass | None = None
        for consent_pass in self._passes.values():
            if hmac.compare_digest(consent_pass.token_hash, wanted):
                found = consent_pass
        return found

    def passes(
        self,
        *,
        include_inactive: bool = False,
        app_id: str | None = None,
        now: datetime | None = None,
    ) -> list[ConsentPass]:
        """Passes newest first. Only active ones unless ``include_inactive``."""
        result = [
            p
            for p in self._passes.values()
            if (include_inactive or p.status(now) == "active")
            and (app_id is None or p.app_id == app_id)
        ]
        return sorted(result, key=lambda p: p.issued_at, reverse=True)

    # ---------- Access log ----------

    def was_revoked(self, consent_pass: ConsentPass) -> bool:
        """True if the pass is marked revoked or the log holds a revoke for it."""
        if consent_pass.revoked_at is not None:
            return True
        return any(e.kind == "revoke" and e.pass_id == consent_pass.id for e in self._events)

    def record(self, event: ConsentEvent) -> None:
        self._events.append(event)
        self._trim()

    def _trim(self) -> None:
        if self.max_events <= 0 or len(self._events) <= self.max_events:
            return
        dropped = self._events[: len(self._events) - self.max_events]
        del self._events[: len(dropped)]
        seqs = [e.chain_seq for e in dropped if e.chain_seq is not None]
        if seqs:
            self.trimmed_through_seq = max(seqs + [self.trimmed_through_seq or -1])

    def events(
        self,
        *,
        limit: int | None = None,
        app_id: str | None = None,
        pass_id: str | None = None,
        kind: str | None = None,
    ) -> list[ConsentEvent]:
        """Events newest first, optionally filtered."""
        result = [
            e
            for e in reversed(self._events)
            if (app_id is None or e.app_id == app_id)
            and (pass_id is None or e.pass_id == pass_id)
            and (kind is None or e.kind == kind)
        ]
        return result[:limit] if limit is not None and limit >= 0 else result

    def verify_events(self, chain: TrustChain) -> dict[str, Any]:
        """Check the access log against the signed trust chain, both ways.

        - A log line is *verified* when the chain holds a ``consent.<kind>``
          entry with the same payload hash. Otherwise it is *unverified*:
          it was edited, never signed (the soul could not sign then), or
          its chain entry was pruned.
        - A signed ``consent.*`` chain entry with no matching log line is
          *missing*: the line was deleted or edited. Entries at or below
          ``trimmed_through_seq`` were dropped by the log's size cap and are
          not counted.

        The chain's own signatures are checked by ``Soul.verify_chain()``.
        """
        signed = {(e.action, e.payload_hash) for e in chain.entries}
        logged: set[tuple[str, str]] = set()
        verified = 0
        unverified: list[dict[str, Any]] = []
        for event in self._events:
            key = (f"consent.{event.kind}", compute_payload_hash(event.chain_payload()))
            logged.add(key)
            if key in signed:
                verified += 1
            else:
                unverified.append(event.public_view())
        floor = -1 if self.trimmed_through_seq is None else self.trimmed_through_seq
        missing = [
            {
                "seq": e.seq,
                "action": e.action,
                "timestamp": e.timestamp.isoformat(),
                "summary": e.summary,
            }
            for e in chain.entries
            if e.action.startswith("consent.")
            and e.seq > floor
            and (e.action, e.payload_hash) not in logged
        ]
        return {
            "total": len(self._events),
            "verified": verified,
            "unverified": len(unverified),
            "unverified_events": unverified,
            "missing": len(missing),
            "missing_entries": missing,
            "ok": not unverified and not missing,
        }

    # ---------- Persistence ----------

    def is_empty(self) -> bool:
        return not self._passes and not self._events and not self.unknown_token_denials

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": _FORMAT_VERSION,
            "passes": [p.model_dump(mode="json") for p in self._passes.values()],
            "events": [e.model_dump(mode="json") for e in self._events],
            "trimmed_through_seq": self.trimmed_through_seq,
            "unknown_token_denials": self.unknown_token_denials,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ConsentRegistry:
        """Rebuild from :meth:`to_dict` output. Skips (and logs) malformed rows."""
        registry = cls()
        if not data:
            return registry
        for raw in data.get("passes") or []:
            try:
                registry.add(ConsentPass.model_validate(raw))
            except ValidationError as exc:
                logger.warning("Skipping malformed consent pass: %s", exc)
        for raw in data.get("events") or []:
            try:
                registry._events.append(ConsentEvent.model_validate(raw))
            except ValidationError as exc:
                logger.warning("Skipping malformed consent event: %s", exc)
        trimmed = data.get("trimmed_through_seq")
        registry.trimmed_through_seq = trimmed if isinstance(trimmed, int) else None
        unknown = data.get("unknown_token_denials")
        registry.unknown_token_denials = unknown if isinstance(unknown, int) else 0
        registry._trim()
        return registry
