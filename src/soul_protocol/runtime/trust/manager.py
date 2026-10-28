# trust/manager.py — TrustChainManager: runtime owner of a soul's trust chain.
# Updated: 2026-04-29 (#201) — append() accepts an optional ``summary`` string
# stored on the resulting TrustEntry. When ``summary=None``, falls back to
# an action-keyed formatter registry (``_SUMMARY_FORMATTERS``) so common
# actions like ``memory.write`` and ``bond.strengthen`` get a useful
# default. ``audit_log()`` returns ``summary`` in each row. The summary
# is non-cryptographic — see ``compute_entry_hash`` in spec/trust.py.
# Created: 2026-04-29 (#42) — Provides the append/verify/query API the Soul
# class wires into observe/supersede/forget/learn/evolve/bond hooks.
# Updated: 2026-04-29 (#203) — Touch-time chain pruning stub. The manager
#   gains a ``max_entries`` cap and a ``prune(keep)`` method that compresses
#   non-genesis history into a single ``chain.pruned`` signed marker. When
#   ``max_entries`` is positive, ``append()`` runs ``_maybe_auto_prune``
#   before adding the new entry so the chain never exceeds the cap. The
#   marker carries ``{count, low_seq, high_seq, reason}`` and is the only
#   action that the verifier permits to break seq monotonicity (see
#   spec.trust.CHAIN_PRUNED_ACTION). Full archival design with a separate
#   archive directory and checkpoint entries is deferred to v0.5.x.
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
    CHAIN_PRUNED_ACTION,
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


def _empty_summary(reason: str) -> dict[str, Any]:
    """Return a 'no-op' prune summary. Shape matches ``TrustChainManager.prune``."""
    return {
        "count": 0,
        "low_seq": None,
        "high_seq": None,
        "reason": reason,
        "marker_seq": None,
    }


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
        max_entries: int = 0,
    ) -> None:
        self.did = did
        self.provider = provider
        self.chain: TrustChain = chain if chain is not None else TrustChain(did=did)
        # max_entries: 0 disables auto-prune (preserves prior unbounded behaviour).
        # Positive values cap the chain — append() compresses old history into a
        # single chain.pruned marker before adding the new entry once the cap
        # is reached. Soul.birth wires this from Biorhythms.trust_chain_max_entries.
        self.max_entries: int = max(0, int(max_entries))
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

        Touch-time pruning (#203): when ``max_entries`` is positive and the
        chain has reached the cap, the manager compresses non-genesis
        history into a signed ``chain.pruned`` marker BEFORE adding the new
        entry. The user-supplied entry then chains from the marker. The
        chain.pruned action is the only entry permitted to break seq
        monotonicity (see spec.trust.CHAIN_PRUNED_ACTION).
        """
        if not self.provider.public_key:
            raise ValueError(
                "TrustChainManager.append requires a SignatureProvider with a public key. "
                "This soul was loaded without a private key — verification-only mode."
            )

        # Touch-time pruning happens BEFORE the new entry is added so the
        # chain.pruned marker links from genesis and the user's entry then
        # links from the marker. This keeps the post-prune monotonicity
        # rule (every non-prune entry has seq == prev.seq + 1) intact for
        # everything appended after the marker.
        self._maybe_auto_prune()

        return self._append_signed(
            action,
            payload,
            actor_did=actor_did,
            timestamp=timestamp,
            summary=summary,
        )

    def _append_signed(
        self,
        action: str,
        payload: dict,
        actor_did: str | None = None,
        timestamp: datetime | None = None,
        summary: str | None = None,
    ) -> TrustEntry:
        """Sign and append a single entry. Internal helper used by both the
        public ``append()`` and the ``prune()`` marker path.
        """
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

    # ---------- Pruning (#203) ----------

    def prune(
        self,
        keep: int | None = None,
        *,
        reason: str = "touch-time",
    ) -> dict[str, Any]:
        """Compress non-genesis history into a single ``chain.pruned`` marker.

        Touch-time stub (v0.5.0). The full archival design — moving pruned
        entries to a separate ``trust_chain/archive/`` directory and linking
        archive checkpoints — lands in a later v0.5.x release.

        Args:
            keep: Length threshold. When the current chain has more than
                ``keep`` entries, every non-genesis entry is dropped and a
                signed ``chain.pruned`` marker is appended. When ``keep`` is
                ``None``, falls back to ``self.max_entries`` (which itself
                may be 0 — in that case, this method is a no-op).
            reason: Free-form string recorded on the marker payload. Most
                callers pass ``"touch-time"`` (auto-prune at append time)
                or ``"manual"`` (explicit CLI/MCP invocation).

        Returns:
            A summary dict::

                {
                    "count": int,        # entries dropped
                    "low_seq": int|None, # lowest dropped seq, or None
                    "high_seq": int|None,# highest dropped seq, or None
                    "reason": str,
                    "marker_seq": int|None, # the new chain.pruned entry's seq, or None
                }

            When the chain is empty, has only a genesis entry, or already
            sits at or below ``keep``, ``count`` is 0 and no marker is
            appended.
        """
        if keep is None:
            keep = self.max_entries
        # Cap of 0 means pruning is disabled — preserve unbounded behaviour.
        if keep is None or keep <= 0:
            return _empty_summary(reason)

        entries = self.chain.entries
        # Nothing to do: empty chain, or genesis-only, or under the cap.
        if len(entries) <= 1 or len(entries) <= keep:
            return _empty_summary(reason)

        # We always preserve the genesis entry (seq=0, the chain's anchor)
        # and compress every later entry into a single marker. Keeping just
        # the genesis means the next entry's prev_hash links from genesis
        # via the new marker — the verifier rule "chain.pruned MAY have a
        # seq gap from prev" applies exactly once per pruning event.
        prunable = entries[1:]
        low_seq = prunable[0].seq
        high_seq = prunable[-1].seq
        count = len(prunable)

        # Drop the prunable entries. The signed genesis stays in place.
        del self.chain.entries[1:]

        # Append the marker. Its seq continues the counter (high_seq + 1)
        # so audit replays preserve the original numbering of what came
        # before the prune. Its prev_hash links from genesis.
        marker_payload = {
            "count": count,
            "low_seq": low_seq,
            "high_seq": high_seq,
            "reason": reason,
        }
        # We sign with _append_signed but force the marker's seq to be
        # (high_seq + 1) rather than (genesis.seq + 1 == 1). This way the
        # seq counter doesn't reset — replays of the chain on a peer that
        # had observed the older entries can spot the gap.
        marker = self._sign_marker_entry(
            action=CHAIN_PRUNED_ACTION,
            payload=marker_payload,
            seq=high_seq + 1,
        )

        logger.info(
            "Trust chain pruned: dropped %d entries (seq %d..%d), marker at seq=%d, reason=%s",
            count,
            low_seq,
            high_seq,
            marker.seq,
            reason,
        )
        return {
            "count": count,
            "low_seq": low_seq,
            "high_seq": high_seq,
            "reason": reason,
            "marker_seq": marker.seq,
        }

    def _sign_marker_entry(
        self,
        action: str,
        payload: dict,
        seq: int,
    ) -> TrustEntry:
        """Sign and append the chain.pruned marker with an explicit seq.

        Mirrors ``_append_signed`` but does not derive seq from head.seq+1 —
        the marker carries the *next-after-pruned* seq so the audit trail
        preserves the original numbering.
        """
        head = self.chain.head()
        if head is None:
            # Caller invariant: prune() never reaches this branch because we
            # bail out for empty chains earlier. Defensive guard.
            raise RuntimeError("cannot append a pruning marker to an empty chain")
        prev_hash = compute_entry_hash(head)

        entry = TrustEntry(
            seq=seq,
            timestamp=datetime.now(UTC),
            actor_did=self.did,
            action=action,
            payload_hash=compute_payload_hash(payload),
            prev_hash=prev_hash,
            algorithm=self.provider.algorithm,
            public_key=self.provider.public_key,
        )

        from soul_protocol.spec.trust import _signing_message

        entry.signature = self.provider.sign(_signing_message(entry))
        self.chain.entries.append(entry)
        return entry

    def dry_run_prune(self, keep: int | None = None) -> dict[str, Any]:
        """Preview what ``prune(keep)`` would drop, without mutating the chain.

        Same return shape as ``prune()`` minus the marker (since no marker
        is signed in a dry run). Intended for the ``soul prune-chain`` CLI
        and the ``soul_prune_chain`` MCP tool, both of which require an
        explicit confirmation step before any chain mutation.
        """
        if keep is None:
            keep = self.max_entries
        if keep is None or keep <= 0:
            return _empty_summary("dry-run")

        entries = self.chain.entries
        if len(entries) <= 1 or len(entries) <= keep:
            return _empty_summary("dry-run")

        prunable = entries[1:]
        return {
            "count": len(prunable),
            "low_seq": prunable[0].seq,
            "high_seq": prunable[-1].seq,
            "reason": "dry-run",
            "marker_seq": prunable[-1].seq + 1,  # what the marker WOULD be
        }

    def _maybe_auto_prune(self) -> None:
        """Run a touch-time prune when the cap is reached.

        Called from ``append()`` BEFORE adding a new entry so the cap is a
        hard ceiling. With cap=N, a chain that has hit N entries first
        compresses to ``[genesis, marker]`` (2 entries), then the user's
        entry takes total to 3 — leaving (N - 3) headroom before the next
        pruning cycle. So pruning is amortized: it fires once every (N - 2)
        appends in steady state, not on every append.

        We call ``prune(keep=1)`` rather than ``prune(keep=max_entries)``
        because the public ``prune(keep)`` semantics are "drop only if
        len > keep" — a manual ``prune(keep=N)`` on a chain of exactly N
        entries should be a no-op. The auto-prune trigger here uses
        ``keep=1`` so it fires whenever there is at least one non-genesis
        entry, which is exactly what we want when the cap is hit.
        """
        if self.max_entries <= 0:
            return
        # Use ">=" so the cap is a hard ceiling. With cap=N and len=N,
        # adding the user's next entry would push us to N+1 — preempt
        # by pruning first. keep=1 means "compress everything past genesis."
        if self.chain.length >= self.max_entries:
            self.prune(keep=1, reason="touch-time")

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
        max_entries: int = 0,
    ) -> TrustChainManager:
        """Reconstruct a manager from a serialized chain dict + a provider.

        ``max_entries`` is NOT serialized inside the chain (the cap is a
        runtime policy from Biorhythms, not a chain-internal property), so
        callers reload it from the soul's config and pass it back in.
        """
        chain = TrustChain.model_validate(data)
        return cls(did=chain.did, provider=provider, chain=chain, max_entries=max_entries)


__all__ = ["TrustChainManager", "_SUMMARY_FORMATTERS"]
