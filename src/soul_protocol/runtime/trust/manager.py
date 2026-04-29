# trust/manager.py — TrustChainManager: runtime owner of a soul's trust chain.
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


class TrustChainManager:
    """Owns and mutates a single soul's :class:`TrustChain`.

    Public API:
        append(action, payload, actor_did=None) → new TrustEntry
        verify() → (bool, reason | None)
        query(action_prefix) → list[TrustEntry]
        head() → latest entry or None
        length → int
        chain → TrustChain (read-only view)
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

        entry = TrustEntry(
            seq=seq,
            timestamp=timestamp or datetime.now(UTC),
            actor_did=actor_did or self.did,
            action=action,
            payload_hash=compute_payload_hash(payload),
            prev_hash=prev_hash,
            algorithm=self.provider.algorithm,
            public_key=self.provider.public_key,
        )

        # Sign the canonical bytes of the entry minus signature.
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
        """Human-readable list of {seq, timestamp, action, actor_did, payload_hash}.

        Used by Soul.audit_log() and the ``soul audit`` CLI.
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


__all__ = ["TrustChainManager"]
