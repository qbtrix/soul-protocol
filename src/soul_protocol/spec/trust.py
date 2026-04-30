# spec/trust.py — Trust chain primitives: TrustEntry, TrustChain, SignatureProvider.
# Updated: 2026-04-30 (#201) — TrustEntry gains a non-cryptographic ``summary``
# field. Excluded from ``compute_entry_hash`` and ``_signing_message`` so it
# can be added/edited without breaking chain verification — same exclusion
# pattern already used for ``signature``. Pre-#201 chains load with
# ``summary=""`` via the Pydantic default and verify unchanged.
# Updated: 2026-04-29 (#199, #200, #205) — Verification hardening.
#   * #199: verify_chain now rejects entries whose timestamp predates the
#     previous entry's timestamp by more than 60s (skew tolerance). Closes
#     a backdating gap where a brief private-key compromise could rewrite
#     the chain head with past-dated entries.
#   * #200: _canonical_json no longer silently stringifies non-JSON-native
#     types via ``default=str``. A strict default raises TypeError with an
#     actionable message so hash-determinism cannot drift across runtimes
#     or Python versions.
#   * #205: compute_payload_hash now refuses BaseModel inputs at the public
#     entry point. Callers must pass dicts (or `model.model_dump(mode="json")`)
#     so two callers with the "same" payload always produce the same hash.
# Created: 2026-04-29 (#42) — Verifiable action history for digital souls.
# Every learning event, memory mutation, and evolution step is signed and
# traceable, forming a Merkle-style hash chain. Pure spec layer: zero
# imports from opinionated modules — runtime concrete classes
# (Ed25519SignatureProvider, TrustChainManager) live under runtime/.
#
# Semantics locked here:
#   - Canonical JSON is sorted-keys, separators=(",", ":"), no whitespace,
#     ensure_ascii=True. Both signers and verifiers MUST use ``compute_payload_hash``
#     and ``compute_entry_hash`` to stay byte-identical.
#   - ``signature`` is base64 of the raw signature bytes over the canonical JSON
#     of all OTHER fields of the entry (signature AND summary are excluded —
#     signature because it's the result, summary because it's a human-readable
#     annotation that callers may want to add or rewrite without breaking
#     verification).
#   - ``prev_hash`` is the hash of the previous entry. Entry 0 (genesis) uses
#     ``GENESIS_PREV_HASH = "0" * 64`` — a constant 64-zero hex string.
#   - ``public_key`` travels with every entry so verification works without an
#     external key registry. The key itself is base64 of the raw 32 bytes for
#     Ed25519. ``algorithm`` is the lower-case algo name (default "ed25519").
#   - ``timestamp`` is timezone-aware UTC. Serialized as ISO 8601. Each
#     successive entry's timestamp must be at-or-after the previous entry's
#     (within a 60s skew tolerance). Future timestamps beyond 60s of the
#     verifier's clock are also rejected.

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENESIS_PREV_HASH: str = "0" * 64
"""The constant ``prev_hash`` for the genesis (seq=0) entry of a trust chain.

64 hex zeros — anchors the chain so attackers can't pretend to lop off the head.
"""

DEFAULT_ALGORITHM: str = "ed25519"
"""Default signing algorithm. Future algorithms (P-256, secp256k1) live alongside."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TrustEntry(BaseModel):
    """A single signed entry in a soul's trust chain.

    One entry per audit-worthy action: a memory write, a memory supersede, a
    forget, an evolution proposal, an evolution apply, a learning event, a
    bond change, or any other action a runtime considers significant.

    The full payload is NOT stored — only ``payload_hash`` (canonical JSON
    SHA-256). This keeps the chain compact and avoids redundantly storing
    memory contents that already live in their own tier files.
    """

    seq: int = Field(ge=0, description="Monotonic 0-indexed sequence number.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp at append time.",
    )
    actor_did: str = Field(
        description="DID of the actor who signed this entry. Usually the soul's own DID."
    )
    action: str = Field(
        description="Dot-namespaced action name — memory.write, evolution.applied, etc."
    )
    payload_hash: str = Field(
        description="SHA-256 hex digest of the canonical JSON of the action's payload."
    )
    prev_hash: str = Field(
        description="SHA-256 hex digest of the previous entry, or GENESIS_PREV_HASH for seq=0."
    )
    signature: str = Field(
        default="",
        description="Base64 signature over the canonical JSON of this entry minus signature.",
    )
    algorithm: str = Field(
        default=DEFAULT_ALGORITHM,
        description="Signing algorithm name. Default 'ed25519'.",
    )
    public_key: str = Field(
        default="",
        description="Base64 of the raw public key used to verify this entry.",
    )
    summary: str = Field(
        default="",
        description=(
            "Human-readable, non-cryptographic per-action description "
            "(e.g. '3 memories', '+0.50 for alice'). Excluded from the "
            "canonical bytes used for hashing and signing — see "
            "compute_entry_hash. Pre-#201 entries load with the empty "
            "default and remain verifiable."
        ),
    )

    @field_validator("timestamp")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        """Force timestamps to be timezone-aware (UTC).

        Naive datetimes are silently coerced to UTC rather than raised — many
        callers pass ``datetime.utcnow()`` (naive). We normalize on the way in
        so canonical JSON stays stable across runtimes.
        """
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


class TrustChain(BaseModel):
    """An ordered, append-only list of TrustEntry items for a single DID."""

    did: str = Field(description="DID of the soul that owns this chain.")
    entries: list[TrustEntry] = Field(default_factory=list)

    @property
    def length(self) -> int:
        """Number of entries in the chain."""
        return len(self.entries)

    def head(self) -> TrustEntry | None:
        """Return the most recent (highest seq) entry, or None if empty."""
        return self.entries[-1] if self.entries else None

    def genesis_entry(self) -> TrustEntry | None:
        """Return entry 0 (genesis), or None if the chain is empty."""
        return self.entries[0] if self.entries else None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SignatureProvider(Protocol):
    """A minimal sign/verify interface a runtime can implement.

    Concrete implementations (Ed25519SignatureProvider) live under
    soul_protocol.runtime.crypto. The spec layer stays algorithm-agnostic.
    """

    @property
    def algorithm(self) -> str:
        """The algorithm identifier — e.g. 'ed25519'."""
        ...

    @property
    def public_key(self) -> str:
        """Base64-encoded raw public key bytes."""
        ...

    def sign(self, message: bytes) -> str:
        """Sign ``message`` and return a base64 signature."""
        ...

    def verify(self, message: bytes, signature: str, public_key: str) -> bool:
        """Verify ``signature`` against ``message`` using ``public_key``.

        Returns True on valid signature, False otherwise. Should NOT raise
        on malformed input — return False.
        """
        ...


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------


def _strict_default(o: Any) -> Any:
    """``json.dumps(default=...)`` hook that refuses non-JSON-native types.

    The trust chain's hash-stability story depends on canonical JSON being
    byte-identical across runtimes and Python versions. The previous
    ``default=str`` fallback silently stringified anything (datetimes,
    Path, custom objects, Pydantic models) — that worked today but masked
    drift: ``str(datetime)`` and ``str(Path)`` are runtime-defined and
    not part of any spec. A different verifier could legitimately compute
    a different hash for the "same" payload.

    Refusing those values forces callers to pre-serialize. Concrete
    guidance: datetimes via ``.isoformat()``, Pydantic models via
    ``.model_dump(mode="json")``, Path via ``str()``. Then the resulting
    structure is JSON-native and the hash is deterministic.
    """
    raise TypeError(
        "compute_payload_hash payloads must be JSON-native (dict / list / str / "
        f"int / float / bool / None). Got: {type(o).__name__}. Pre-serialize "
        "datetimes via .isoformat(), Pydantic models via .model_dump(mode='json'), "
        "Path objects via str()."
    )


def _canonical_json(data: Any) -> bytes:
    """Canonicalize a Python value to deterministic JSON bytes.

    Used by both signers and verifiers. The format is locked: sorted keys,
    minimal separators, ensure_ascii so unicode escapes are stable across
    runtimes. Pydantic models are dumped with ``mode='json'`` first so
    their datetimes and other rich types serialize via Pydantic's stable
    rules. Anything left over that is not JSON-native trips
    :func:`_strict_default` — see #200.
    """
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_strict_default,
    ).encode("utf-8")


def compute_payload_hash(payload: dict) -> str:
    """SHA-256 hex digest of canonical JSON of the payload.

    Stored in ``TrustEntry.payload_hash``. The payload itself is NOT in the
    chain — only its hash. So a verifier with the original payload and the
    chain entry can prove the payload existed and was not tampered with.

    ``payload`` MUST be a plain dict of JSON-native primitives. Passing a
    Pydantic model raises :class:`TypeError` (see #205): two callers with
    a logically-equivalent BaseModel and dict could otherwise produce
    different hashes if the BaseModel's ``model_dump`` shape ever drifts.
    Convert via ``model.model_dump(mode="json")`` before calling.
    """
    if isinstance(payload, BaseModel):
        raise TypeError(
            "compute_payload_hash expects a dict of JSON-native primitives. "
            "Pass payload.model_dump(mode='json') instead."
        )
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def compute_entry_hash(entry: TrustEntry) -> str:
    """SHA-256 hex digest of the canonical JSON of an entry, EXCLUDING signature and summary.

    This is the value the next entry's ``prev_hash`` must equal. Two fields
    are stripped before hashing:

    - ``signature`` — it's the *result* of signing this hash (or the bytes
      hashed here), so it can't be part of its own input.
    - ``summary`` — added by #201 as a human-readable annotation. Excluding
      it keeps the chain verifiable when callers add, edit, or remove the
      summary text without re-signing every entry. Pre-#201 chains have
      ``summary=""`` via the Pydantic default and produce identical hashes.
    """
    raw = entry.model_dump(mode="json")
    raw.pop("signature", None)
    raw.pop("summary", None)
    return hashlib.sha256(_canonical_json(raw)).hexdigest()


def _signing_message(entry: TrustEntry) -> bytes:
    """Bytes that must be signed for ``entry``.

    Same canonical-JSON-minus-signature-minus-summary shape as
    :func:`compute_entry_hash`. We sign the bytes directly (not the hash)
    so callers can use any signature scheme — Ed25519 hashes internally,
    but other algorithms might not.
    """
    raw = entry.model_dump(mode="json")
    raw.pop("signature", None)
    raw.pop("summary", None)
    return _canonical_json(raw)


# ---------------------------------------------------------------------------
# Verification functions
# ---------------------------------------------------------------------------


def verify_entry(
    entry: TrustEntry,
    prev_entry: TrustEntry | None,
    provider: SignatureProvider | None = None,
) -> bool:
    """Verify a single entry's signature and chain link.

    Args:
        entry: The entry to verify.
        prev_entry: The previous entry in the chain. Pass ``None`` for the
            genesis entry — in that case ``entry.seq`` must be 0 and
            ``entry.prev_hash`` must be ``GENESIS_PREV_HASH``.
        provider: Optional SignatureProvider whose ``verify`` is used.
            When ``None`` (default), the entry's own ``public_key`` plus a
            built-in algorithm dispatcher is used. Pass a provider only when
            you want to override key resolution (e.g. test isolation).

    Returns True on success, False on any failure (bad sig, bad chain link,
    wrong algorithm, malformed key). Does not raise.
    """
    # 1. Chain link check.
    if prev_entry is None:
        if entry.seq != 0:
            return False
        if entry.prev_hash != GENESIS_PREV_HASH:
            return False
    else:
        if entry.seq != prev_entry.seq + 1:
            return False
        if entry.prev_hash != compute_entry_hash(prev_entry):
            return False

    # 2. Signature check.
    if not entry.signature:
        return False
    message = _signing_message(entry)
    try:
        if provider is not None:
            return bool(provider.verify(message, entry.signature, entry.public_key))
        return _verify_with_algorithm(
            entry.algorithm,
            message,
            entry.signature,
            entry.public_key,
        )
    except Exception:
        return False


def _verify_with_algorithm(
    algorithm: str,
    message: bytes,
    signature: str,
    public_key: str,
) -> bool:
    """Algorithm-dispatched verification when no provider is supplied.

    Currently only Ed25519 is supported. Returns False for unknown
    algorithms rather than raising — keeps verifier code simple.
    """
    if algorithm.lower() == "ed25519":
        # Lazy import — keeps the spec layer free of cryptography at import time.
        import base64

        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        try:
            pk_bytes = base64.b64decode(public_key)
            sig_bytes = base64.b64decode(signature)
            pk = Ed25519PublicKey.from_public_bytes(pk_bytes)
            pk.verify(sig_bytes, message)
            return True
        except (InvalidSignature, ValueError):
            return False
    return False


def verify_chain(chain: TrustChain) -> tuple[bool, str | None]:
    """Verify an entire chain, sequentially.

    Returns ``(True, None)`` on a fully valid chain, or
    ``(False, "reason at seq N")`` on the first failure. The chain is
    considered valid when empty.

    Catches: bad signature, broken hash chain, non-monotonic seq,
    duplicate seq, future timestamps (more than 60 seconds in the future
    relative to ``datetime.now(UTC)``), and backdated timestamps (an
    entry whose timestamp is more than 60 seconds before the previous
    entry's timestamp — see #199).
    """
    if not chain.entries:
        return True, None

    now = datetime.now(UTC)
    seen_seq: set[int] = set()
    prev: TrustEntry | None = None

    for entry in chain.entries:
        # Duplicate seq
        if entry.seq in seen_seq:
            return False, f"duplicate seq at seq {entry.seq}"
        seen_seq.add(entry.seq)

        # Future timestamp (allow 60s clock skew)
        if (entry.timestamp - now).total_seconds() > 60:
            return False, f"timestamp in the future at seq {entry.seq}"

        # Timestamp monotonicity (#199). 60s skew tolerance absorbs minor
        # clock drift across runtimes. Anything beyond that points at a
        # backdated entry — caught here even when the rest of the entry
        # would otherwise verify.
        if prev is not None and (entry.timestamp - prev.timestamp).total_seconds() < -60:
            return False, f"timestamp before previous entry at seq {entry.seq}"

        if not verify_entry(entry, prev):
            # Distinguish chain-link failures from signature failures for the
            # message — re-derive the cause cheaply rather than instrument
            # verify_entry with structured returns.
            if prev is None:
                if entry.seq != 0:
                    return False, f"non-zero seq at genesis at seq {entry.seq}"
                if entry.prev_hash != GENESIS_PREV_HASH:
                    return False, f"bad genesis prev_hash at seq {entry.seq}"
            else:
                if entry.seq != prev.seq + 1:
                    return False, f"non-monotonic seq at seq {entry.seq}"
                if entry.prev_hash != compute_entry_hash(prev):
                    return False, f"broken hash chain at seq {entry.seq}"
            return False, f"bad signature at seq {entry.seq}"

        prev = entry

    return True, None


def chain_integrity_check(chain: TrustChain) -> dict:
    """Return a structured summary of chain integrity.

    Output keys:
        valid: bool — overall verification result
        length: int — total entries
        first_failure: dict | None — {"seq": N, "reason": "..."} on failure
        signers: list[str] — sorted unique actor_dids
    """
    valid, reason = verify_chain(chain)
    failure: dict | None = None
    if not valid and reason is not None:
        # Extract the seq number from the reason string when present.
        # Reason format is "<text> at seq <N>" — pull the trailing int.
        seq: int | None = None
        if "at seq " in reason:
            try:
                seq = int(reason.rsplit(" ", 1)[-1])
            except ValueError:
                seq = None
        failure = {"seq": seq, "reason": reason}

    return {
        "valid": valid,
        "length": chain.length,
        "first_failure": failure,
        "signers": sorted({e.actor_did for e in chain.entries}),
    }


__all__ = [
    "GENESIS_PREV_HASH",
    "DEFAULT_ALGORITHM",
    "TrustEntry",
    "TrustChain",
    "SignatureProvider",
    "compute_payload_hash",
    "compute_entry_hash",
    "verify_entry",
    "verify_chain",
    "chain_integrity_check",
]
