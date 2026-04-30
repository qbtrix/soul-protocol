# trust/manager.py — TrustChainManager: runtime owner of a soul's trust chain.
# Updated: 2026-04-29 (#201) — append() accepts an optional ``summary`` string
# stored on the resulting TrustEntry. When ``summary=None``, falls back to
# an action-keyed formatter registry (``_SUMMARY_FORMATTERS``) so common
# actions like ``memory.write`` and ``bond.strengthen`` get a useful
# default. ``audit_log()`` returns ``summary`` in each row. The summary
# is non-cryptographic — see ``compute_entry_hash`` in spec/trust.py.
# Created: 2026-04-29 (#42) — Provides the append/verify/query API the Soul
# class wires into observe/supersede/forget/learn/evolve/bond hooks.
#
# The manager is intentionally thin: it owns a SignatureProvider (used to
# sign new entries) and a TrustChain (the data). It does NOT own any policy
# about WHEN to append — that's the Soul layer's call. That separation
# keeps the manager re-usable for tooling that wants to verify-only or
# replay a chain into another store.

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from soul_protocol.spec.trust import (
    GENESIS_PREV_HASH,
    SignatureProvider,
    TrustChain,
    TrustEntry,
    chain_integrity_check,
    compute_entry_hash,
    compute_payload_hash,
    verify_chain,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Summary formatter registry (#201)
# ---------------------------------------------------------------------------
#
# Each entry maps a dot-namespaced ``action`` to a callable that turns a
# payload dict into a short human-readable string. Used by
# :meth:`TrustChainManager.append` when the caller doesn't pass an explicit
# ``summary=``. Formatters MUST be defensive — payloads come from many
# Soul callsites and may be missing fields. Each formatter runs in a
# try/except in :meth:`_default_summary`; failures yield ``""``.

SummaryFormatter = Callable[[dict], str]


def _fmt_memory_write(p: dict) -> str:
    count = p.get("count", "?")
    if isinstance(count, int):
        noun = "memory" if count == 1 else "memories"
        return f"{count} {noun}"
    return f"{count} memories"


def _fmt_memory_forget(p: dict) -> str:
    tier = p.get("tier") or "?"
    mid = (p.get("id") or "")[:8]
    return f"deleted {tier}/{mid}"


def _fmt_memory_supersede(p: dict) -> str:
    old = (p.get("old_id") or "")[:8]
    new = (p.get("new_id") or "")[:8]
    return f"replaced {old} with {new}"


def _fmt_bond_strengthen(p: dict) -> str:
    delta = p.get("delta", 0)
    user = p.get("user_id") or "default"
    return f"+{float(delta):.2f} for {user}"


def _fmt_bond_weaken(p: dict) -> str:
    delta = p.get("delta", 0)
    user = p.get("user_id") or "default"
    return f"-{float(delta):.2f} for {user}"


def _fmt_evolution_proposed(p: dict) -> str:
    return p.get("trait") or "evolution proposal"


def _fmt_evolution_applied(p: dict) -> str:
    trait = p.get("trait") or "mutation"
    return f"applied {trait}"


def _fmt_learning_event(p: dict) -> str:
    return p.get("summary") or "learning event"


_SUMMARY_FORMATTERS: dict[str, SummaryFormatter] = {
    "memory.write": _fmt_memory_write,
    "memory.forget": _fmt_memory_forget,
    "memory.supersede": _fmt_memory_supersede,
    "bond.strengthen": _fmt_bond_strengthen,
    "bond.weaken": _fmt_bond_weaken,
    "evolution.proposed": _fmt_evolution_proposed,
    "evolution.applied": _fmt_evolution_applied,
    "learning.event": _fmt_learning_event,
}


def _default_summary(action: str, payload: dict) -> str:
    """Look up an action's default formatter and run it against ``payload``.

    Returns ``""`` for actions without a registered formatter or when the
    formatter raises (defensive — formatters run on payloads from many
    callsites with variable shape).
    """
    fmt = _SUMMARY_FORMATTERS.get(action)
    if fmt is None:
        return ""
    try:
        return fmt(payload) or ""
    except Exception:  # pragma: no cover — defensive against bad payloads
        return ""


class TrustChainManager:
    """Owns and mutates a single soul's :class:`TrustChain`.

    Public API:
        append(action, payload, actor_did=None, summary=None) → new TrustEntry
        verify() → (bool, reason | None)
        query(action_prefix) → list[TrustEntry]
        head() → latest entry or None
        length → int
        chain → TrustChain (read-only view)
        audit_log(action_prefix=None, limit=None) → list[dict] including summary
        to_dict() / from_dict()
    """

    def __init__(
        self,
        did: str,
        provider: SignatureProvider,
        chain: TrustChain | None = None,
    ) -> None:
        self.did = did
        self.provider = provider
        self.chain: TrustChain = chain if chain is not None else TrustChain(did=did)
        # Light sanity: when an existing chain is loaded for a different DID,
        # warn but don't refuse — operators may want to inspect a foreign chain.
        if self.chain.did and self.chain.did != did:
            logger.warning(
                "TrustChainManager DID mismatch: manager.did=%s chain.did=%s",
                did,
                self.chain.did,
            )

    # ---------- Mutation ----------

    def append(
        self,
        action: str,
        payload: dict,
        actor_did: str | None = None,
        timestamp: datetime | None = None,
        summary: str | None = None,
    ) -> TrustEntry:
        """Append a signed entry for ``action`` with ``payload``.

        Args:
            action: Dot-namespaced action (memory.write, evolution.applied,
                bond.strengthen, ...).
            payload: Dict to hash. Only the SHA-256 hex digest is stored —
                callers can keep the original payload outside the chain.
            actor_did: DID of the signer. Defaults to the manager's DID.
            timestamp: Override timestamp (used by test fixtures). Defaults
                to UTC now.
            summary: Optional non-cryptographic human-readable annotation
                stored on the entry. When ``None`` (the default), an
                action-keyed default formatter from
                :data:`_SUMMARY_FORMATTERS` is used; actions without a
                registered formatter get ``""``. The summary is excluded
                from canonical bytes (see ``compute_entry_hash``), so the
                resulting hash chain is identical regardless of summary
                contents — callers can rewrite summaries later without
                breaking verification (#201).

        Returns the appended entry. Raises :class:`ValueError` if the
        provider doesn't have a public key (e.g. a partial keystore loaded
        without a private key). Verification-only flows should use the
        chain directly without appending.
        """
        if not self.provider.public_key:
            raise ValueError(
                "TrustChainManager.append requires a SignatureProvider with a public key. "
                "This soul was loaded without a private key — verification-only mode."
            )

        head = self.chain.head()
        seq = 0 if head is None else head.seq + 1
        prev_hash = GENESIS_PREV_HASH if head is None else compute_entry_hash(head)

        resolved_summary = summary if summary is not None else _default_summary(action, payload)

        entry = TrustEntry(
            seq=seq,
            timestamp=timestamp or datetime.now(UTC),
            actor_did=actor_did or self.did,
            action=action,
            payload_hash=compute_payload_hash(payload),
            prev_hash=prev_hash,
            algorithm=self.provider.algorithm,
            public_key=self.provider.public_key,
            summary=resolved_summary,
        )

        # Sign the canonical bytes of the entry minus signature and summary.
        from soul_protocol.spec.trust import _signing_message

        message = _signing_message(entry)
        entry.signature = self.provider.sign(message)

        self.chain.entries.append(entry)
        logger.debug(
            "Trust chain entry appended: seq=%d action=%s actor=%s",
            seq,
            action,
            entry.actor_did,
        )
        return entry

    # ---------- Read ----------

    def head(self) -> TrustEntry | None:
        """The most recent entry, or None when the chain is empty."""
        return self.chain.head()

    @property
    def length(self) -> int:
        """Number of entries in the chain."""
        return self.chain.length

    def query(self, action_prefix: str) -> list[TrustEntry]:
        """Return entries whose ``action`` starts with ``action_prefix``.

        Empty prefix returns every entry. Suffix wildcards aren't needed —
        actions are dot-namespaced (``memory.write``, ``memory.supersede``)
        so a prefix like ``"memory."`` is enough to scope to a category.
        """
        if not action_prefix:
            return list(self.chain.entries)
        return [e for e in self.chain.entries if e.action.startswith(action_prefix)]

    def verify(self) -> tuple[bool, str | None]:
        """Run :func:`verify_chain` over this manager's chain."""
        return verify_chain(self.chain)

    def integrity(self) -> dict:
        """Return a summary :func:`chain_integrity_check` dict."""
        return chain_integrity_check(self.chain)

    def audit_log(
        self, *, action_prefix: str | None = None, limit: int | None = None
    ) -> list[dict]:
        """Human-readable list of ``{seq, timestamp, action, actor_did, payload_hash, summary}``.

        Used by Soul.audit_log() and the ``soul audit`` CLI. The ``summary``
        field is the per-entry human annotation set at append time — see
        :meth:`append`. Pre-#201 entries serialised before the field
        existed load with ``summary=""``.
        """
        entries = self.query(action_prefix) if action_prefix else list(self.chain.entries)
        if limit is not None:
            entries = entries[-limit:]
        return [
            {
                "seq": e.seq,
                "timestamp": e.timestamp.isoformat(),
                "action": e.action,
                "actor_did": e.actor_did,
                "payload_hash": e.payload_hash,
                "summary": e.summary,
            }
            for e in entries
        ]

    # ---------- Persistence ----------

    def to_dict(self) -> dict[str, Any]:
        """Pydantic-friendly dict of the chain (for chain.json)."""
        return self.chain.model_dump(mode="json")

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        provider: SignatureProvider,
    ) -> TrustChainManager:
        """Reconstruct a manager from a serialized chain dict + a provider."""
        chain = TrustChain.model_validate(data)
        return cls(did=chain.did, provider=provider, chain=chain)


__all__ = ["TrustChainManager", "_SUMMARY_FORMATTERS"]
