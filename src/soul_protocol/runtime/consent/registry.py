# consent/registry.py — In-memory store of a soul's consent passes + access log.
# Created: 2026-11-14 — ConsentRegistry holds every issued ConsentPass and a
#   bounded log of ConsentEvents. Persisted as ``consent/consent.json`` inside
#   the soul (directory saves and .soul archives). Pure data: issuing,
#   checking and signing live in consent/service.py.
# Updated: 2026-11-25 (#326 review) — Verification trusts only signed data:
#   each log line is checked against the chain entry at its ``chain_seq``,
#   every signed consent.* entry must be in the log or in a signed trim
#   record, and entries removed by chain pruning are reported as "pruned"
#   instead of failing. Grant/revoke lines are never trimmed. Repeated
#   denials for the same pass and reason are folded (rate-limited). Passes
#   that ended long ago are pruned. Unknown-token refusals are only counted
#   and never create the consent file on their own.

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError

from soul_protocol.spec.trust import CHAIN_PRUNED_ACTION, TrustChain, compute_payload_hash

from .models import ConsentEvent, ConsentPass, TrimRecord, as_utc, hash_token

logger = logging.getLogger(__name__)

#: Newest read/write/denied lines kept in the readable log. Grant and revoke
#: lines for passes still on file are always kept.
MAX_EVENTS = 1000

#: The log is trimmed in batches once it is this much over the cap, so one
#: signed trim record covers many lines instead of one each.
TRIM_SLACK = 0.1

#: At most one logged (and signed) denial per pass and reason in this window.
DENIAL_WINDOW = timedelta(hours=1)

#: Passes that ended (expired or revoked) longer ago than this are removed.
PASS_RETENTION = timedelta(days=90)

_FORMAT_VERSION = 2
_LIFECYCLE = ("grant", "revoke")


class ConsentRegistry:
    """All consent passes a soul has issued, plus the consent access log."""

    def __init__(self, max_events: int = MAX_EVENTS) -> None:
        self._passes: dict[str, ConsentPass] = {}
        self._events: list[ConsentEvent] = []
        self._trims: list[TrimRecord] = []
        self.max_events = max_events
        #: Requests refused because their token matched no pass (not logged).
        self.unknown_token_denials = 0
        #: Denials folded into a later line, keyed "pass_id|reason".
        self._pending_denials: dict[str, int] = {}

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

    def prune_inactive(self, now: datetime, retention: timedelta = PASS_RETENTION) -> list[str]:
        """Remove passes that ended more than ``retention`` ago. Returns their ids."""
        cutoff = as_utc(now) - retention
        gone = [
            p.id
            for p in self._passes.values()
            if p.status(now) != "active" and p.ended_at() < cutoff
        ]
        for pass_id in gone:
            del self._passes[pass_id]
        return gone

    # ---------- Access log ----------

    def record(self, event: ConsentEvent) -> None:
        self._events.append(event)

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

    def logged_revocation(self, consent_pass: ConsentPass) -> bool:
        """True if the pass is marked revoked or the log holds a revoke for it."""
        if consent_pass.revoked_at is not None:
            return True
        return any(e.kind == "revoke" and e.pass_id == consent_pass.id for e in self._events)

    # ---------- Denial rate limiting ----------

    def take_denial(self, pass_id: str, reason: str, at: datetime) -> int:
        """Decide whether a denial gets its own log line.

        Returns how many refusals the new line stands for, or 0 when this
        refusal is folded into a later line (one line per pass and reason
        per :data:`DENIAL_WINDOW`).
        """
        key = f"{pass_id}|{reason}"
        last = next(
            (
                e.at
                for e in reversed(self._events)
                if e.kind == "denied" and e.pass_id == pass_id and e.reason == reason
            ),
            None,
        )
        if last is not None and as_utc(at) - last < DENIAL_WINDOW:
            self._pending_denials[key] = self._pending_denials.get(key, 0) + 1
            return 0
        return 1 + self._pending_denials.pop(key, 0)

    def pending_denials(self) -> int:
        """Refusals not yet written to a log line."""
        return sum(self._pending_denials.values())

    # ---------- Trimming ----------

    def overflow(self) -> list[ConsentEvent]:
        """Lines to drop, oldest first, once the log is past the cap plus slack.

        Grant and revoke lines for passes still on file are never dropped.
        """
        if self.max_events <= 0:
            return []
        trimmable = [
            e for e in self._events if not (e.kind in _LIFECYCLE and e.pass_id in self._passes)
        ]
        if len(trimmable) <= int(self.max_events * (1 + TRIM_SLACK)):
            return []
        return trimmable[: len(trimmable) - self.max_events]

    def apply_trim(self, dropped: list[ConsentEvent], record: TrimRecord) -> None:
        ids = {id(e) for e in dropped}
        self._events = [e for e in self._events if id(e) not in ids]
        self._trims.append(record)

    # ---------- Verification ----------

    def verify(self, chain: TrustChain) -> dict[str, Any]:
        """Check the access log against the signed trust chain, both ways.

        - Each log line must match the ``consent.<kind>`` chain entry at its
          ``chain_seq``. Lines whose entry was removed by chain pruning are
          counted as *pruned*; anything else that doesn't match is
          *unverified* (edited, or never signed).
        - Each signed ``consent.*`` chain entry must be backed by a log line
          or listed in a signed trim record. Anything else is *missing*
          (a line was deleted or edited).
        """
        by_seq = {e.seq: e for e in chain.entries}
        pruned_below = max(
            (e.seq for e in chain.entries if e.action == CHAIN_PRUNED_ACTION), default=-1
        )

        def check(item: Any, action: str) -> str:
            if item.chain_seq is None:
                return "unverified"
            entry = by_seq.get(item.chain_seq)
            if entry is None:
                return "pruned" if 0 < item.chain_seq < pruned_below else "unverified"
            ok = entry.action == action and entry.payload_hash == compute_payload_hash(
                item.chain_payload()
            )
            return "verified" if ok else "unverified"

        accounted: set[int] = set()
        trims_verified = 0
        for trim in self._trims:
            if check(trim, "consent.trim") == "verified":
                trims_verified += 1
                accounted.add(trim.chain_seq)
                accounted.update(trim.seqs)

        counts = {"verified": 0, "unverified": 0, "pruned": 0}
        unverified: list[dict[str, Any]] = []
        for event in self._events:
            state = check(event, f"consent.{event.kind}")
            counts[state] += 1
            if state == "unverified":
                unverified.append(event.public_view())
            elif state == "verified":
                accounted.add(event.chain_seq)

        missing = [
            {
                "seq": e.seq,
                "action": e.action,
                "timestamp": e.timestamp.isoformat(),
                "summary": e.summary,
            }
            for e in chain.entries
            if e.action.startswith("consent.") and e.seq not in accounted
        ]
        return {
            "total": len(self._events),
            "verified": counts["verified"],
            "unverified": counts["unverified"],
            "pruned": counts["pruned"],
            "unverified_events": unverified,
            "missing": len(missing),
            "missing_entries": missing,
            "trims": len(self._trims),
            "trims_verified": trims_verified,
            "pending_denials": self.pending_denials(),
            "unknown_token_denials": self.unknown_token_denials,
            "ok": not unverified and not missing,
        }

    # ---------- Persistence ----------

    def is_empty(self) -> bool:
        # The unknown-token counter alone never creates a consent file.
        return not self._passes and not self._events and not self._trims

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": _FORMAT_VERSION,
            "passes": [p.model_dump(mode="json") for p in self._passes.values()],
            "events": [e.model_dump(mode="json") for e in self._events],
            "trims": [t.model_dump(mode="json") for t in self._trims],
            "pending_denials": dict(self._pending_denials),
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
        for raw in data.get("trims") or []:
            try:
                registry._trims.append(TrimRecord.model_validate(raw))
            except ValidationError as exc:
                logger.warning("Skipping malformed consent trim record: %s", exc)
        pending = data.get("pending_denials")
        if isinstance(pending, dict):
            registry._pending_denials = {
                str(k): v for k, v in pending.items() if isinstance(v, int) and v > 0
            }
        unknown = data.get("unknown_token_denials")
        registry.unknown_token_denials = unknown if isinstance(unknown, int) else 0
        return registry
