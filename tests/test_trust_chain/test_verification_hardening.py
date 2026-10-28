# tests/test_trust_chain/test_verification_hardening.py — Hardening tests
# for #199 (timestamp monotonicity), #200 (strict canonical JSON), and
# #205 (BaseModel guard on compute_payload_hash).
# Created: 2026-04-29 — Part of the trust chain verification hardening
# bundle. These three issues tighten the verifier and the hashing contract
# so the chain stays provably stable as more entries accumulate.

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.trust.manager import TrustChainManager
from soul_protocol.spec.trust import (
    GENESIS_PREV_HASH,
    TrustChain,
    TrustEntry,
    _canonical_json,
    _signing_message,
    _strict_default,
    compute_entry_hash,
    compute_payload_hash,
    verify_chain,
)


def _build_chain(n: int = 3) -> TrustChainManager:
    """Helper: build a signed chain with ``n`` entries."""
    p = Ed25519SignatureProvider.from_seed(b"H" * 32)
    mgr = TrustChainManager(did="did:soul:hardening", provider=p)
    for i in range(n):
        mgr.append("test.action", {"i": i})
    return mgr


# ---------------------------------------------------------------------------
# #199 — Timestamp monotonicity
# ---------------------------------------------------------------------------


class TestTimestampMonotonicity:
    """verify_chain rejects entries whose timestamp predates the previous
    entry's timestamp by more than 60s. Closes the backdating gap (#199)."""

    def test_backdated_entry_far_past_fails(self) -> None:
        """An entry timestamped 1 hour before its predecessor fails verification."""
        mgr = _build_chain(3)
        # Move entry[1] backwards by an hour. The hash chain (which is
        # signed over the entry minus signature) will also need to be
        # re-signed for the test to isolate timestamp monotonicity from
        # signature verification, so we re-sign after the mutation.
        new_ts = mgr.chain.entries[0].timestamp - timedelta(hours=1)
        mgr.chain.entries[1].timestamp = new_ts
        mgr.chain.entries[1].signature = ""
        mgr.chain.entries[1].signature = mgr.provider.sign(_signing_message(mgr.chain.entries[1]))
        # Re-sign entry[2] as well — its prev_hash now points at a
        # different entry[1] hash (timestamp changed).
        mgr.chain.entries[2].prev_hash = compute_entry_hash(mgr.chain.entries[1])
        mgr.chain.entries[2].signature = ""
        mgr.chain.entries[2].signature = mgr.provider.sign(_signing_message(mgr.chain.entries[2]))

        valid, reason = mgr.verify()
        assert valid is False
        assert reason is not None
        assert "before previous entry" in reason
        assert "seq 1" in reason

    def test_backdated_within_60s_skew_passes(self) -> None:
        """Entries up to 60s behind their predecessor are tolerated for clock skew."""
        mgr = _build_chain(3)
        # Push entry[1] back 30s — within tolerance.
        mgr.chain.entries[1].timestamp = mgr.chain.entries[0].timestamp - timedelta(seconds=30)
        mgr.chain.entries[1].signature = ""
        mgr.chain.entries[1].signature = mgr.provider.sign(_signing_message(mgr.chain.entries[1]))
        mgr.chain.entries[2].prev_hash = compute_entry_hash(mgr.chain.entries[1])
        mgr.chain.entries[2].signature = ""
        mgr.chain.entries[2].signature = mgr.provider.sign(_signing_message(mgr.chain.entries[2]))

        valid, reason = mgr.verify()
        assert valid is True, f"expected pass, got reason={reason!r}"

    def test_backdated_just_over_60s_fails(self) -> None:
        """Entries more than 60s behind their predecessor fail verification."""
        mgr = _build_chain(3)
        mgr.chain.entries[1].timestamp = mgr.chain.entries[0].timestamp - timedelta(seconds=61)
        mgr.chain.entries[1].signature = ""
        mgr.chain.entries[1].signature = mgr.provider.sign(_signing_message(mgr.chain.entries[1]))
        mgr.chain.entries[2].prev_hash = compute_entry_hash(mgr.chain.entries[1])
        mgr.chain.entries[2].signature = ""
        mgr.chain.entries[2].signature = mgr.provider.sign(_signing_message(mgr.chain.entries[2]))

        valid, reason = mgr.verify()
        assert valid is False
        assert reason is not None
        assert "before previous entry" in reason

    def test_genesis_entry_has_no_predecessor_check(self) -> None:
        """Entry 0 has no prev — the monotonicity rule starts at seq 1."""
        # Build a fresh single-entry chain. The genesis entry's timestamp
        # is whatever it is; there's no predecessor to compare against.
        mgr = _build_chain(1)
        valid, reason = mgr.verify()
        assert valid is True, f"expected pass, got reason={reason!r}"

    def test_equal_timestamps_pass(self) -> None:
        """Two entries with the exact same timestamp are valid (delta = 0s)."""
        mgr = _build_chain(2)
        same = mgr.chain.entries[0].timestamp
        mgr.chain.entries[1].timestamp = same
        mgr.chain.entries[1].signature = ""
        mgr.chain.entries[1].signature = mgr.provider.sign(_signing_message(mgr.chain.entries[1]))

        valid, reason = mgr.verify()
        assert valid is True, f"expected pass, got reason={reason!r}"


# ---------------------------------------------------------------------------
# #200 — Strict canonical JSON
# ---------------------------------------------------------------------------


class TestStrictCanonicalJSON:
    """_canonical_json refuses non-JSON-native values via _strict_default."""

    def test_strict_default_raises_for_path(self) -> None:
        """Path objects no longer get silently stringified."""
        with pytest.raises(TypeError) as exc_info:
            _canonical_json({"path": Path("/tmp/foo")})
        assert "Pre-serialize" in str(exc_info.value)
        assert "Path" in str(exc_info.value)

    def test_strict_default_raises_for_naive_datetime_in_dict(self) -> None:
        """A naive datetime nested in a dict raises; stable hashing requires
        callers to pre-serialize via .isoformat() (or use pydantic's
        model_dump(mode='json') which already does that)."""
        # When a raw datetime appears inside a dict, json.dumps falls
        # through to default since datetime is not JSON-native.
        with pytest.raises(TypeError) as exc_info:
            _canonical_json({"when": datetime.now(UTC)})
        assert "isoformat" in str(exc_info.value)

    def test_strict_default_raises_for_arbitrary_class(self) -> None:
        """A custom class instance trips the strict default."""

        class Foo:
            pass

        with pytest.raises(TypeError) as exc_info:
            _canonical_json({"f": Foo()})
        assert "Foo" in str(exc_info.value)

    def test_canonical_json_still_handles_basemodel_at_top(self) -> None:
        """Pydantic models at the top level still serialize via model_dump.
        compute_entry_hash relies on this (it passes the TrustEntry directly)."""

        class M(BaseModel):
            a: int
            b: str

        out = _canonical_json(M(a=1, b="hi"))
        assert out == b'{"a":1,"b":"hi"}'

    def test_canonical_json_native_dict_works(self) -> None:
        """JSON-native primitives serialize identically to before."""
        out = _canonical_json({"x": 1, "y": [1, 2, 3], "z": "hello"})
        assert out == b'{"x":1,"y":[1,2,3],"z":"hello"}'

    def test_strict_default_directly_raises(self) -> None:
        """Calling the helper directly raises — no silent fallback."""
        with pytest.raises(TypeError) as exc_info:
            _strict_default(object())
        assert "JSON-native" in str(exc_info.value)

    def test_existing_chain_payloads_remain_hashable(self) -> None:
        """All real chain-append payload shapes from runtime/soul.py
        and runtime/bond.py must keep hashing cleanly under strict mode.

        These are the actual payload dicts shipped to TrustChainManager.append
        in v0.4.0. Audit confirms they're all JSON-native primitives.
        """
        # memory.write
        compute_payload_hash(
            {
                "user_id": "alice",
                "domain": "default",
                "layer": None,
                "count": 2,
                "ids": ["m1", "m2"],
            }
        )
        # memory.forget
        compute_payload_hash({"id": "m1", "tier": "episodic"})
        # memory.supersede
        compute_payload_hash({"old_id": "m1", "new_id": "m2", "reason": "correction"})
        # learning.event
        compute_payload_hash(
            {
                "domain": "code",
                "skill_id": "py",
                "score": 0.83,
                "interaction_id": "i1",
            }
        )
        # evolution.proposed
        compute_payload_hash(
            {
                "mutation_id": "mut1",
                "trait": "openness",
                "new_value": "0.7",
                "reason": "growth",
            }
        )
        # evolution.applied
        compute_payload_hash({"mutation_id": "mut1"})
        # bond.strengthen / weaken
        compute_payload_hash({"user_id": "alice", "delta": 0.5, "new_strength": 51.0})

    def test_hash_is_byte_stable_across_dict_orderings(self) -> None:
        """sort_keys=True means the input dict's order does not affect the hash."""
        a = compute_payload_hash({"a": 1, "b": 2, "c": 3})
        b = compute_payload_hash({"c": 3, "a": 1, "b": 2})
        assert a == b


# ---------------------------------------------------------------------------
# #205 — compute_payload_hash typing guard
# ---------------------------------------------------------------------------


class TestComputePayloadHashTyping:
    """compute_payload_hash refuses BaseModel inputs at the public entry
    point so dict-vs-model callers can't drift."""

    def test_basemodel_input_raises(self) -> None:
        class P(BaseModel):
            x: int

        with pytest.raises(TypeError) as exc_info:
            compute_payload_hash(P(x=1))
        assert "model_dump" in str(exc_info.value)

    def test_dict_from_model_dump_works(self) -> None:
        class P(BaseModel):
            x: int

        h = compute_payload_hash(P(x=1).model_dump(mode="json"))
        # Same as if we'd passed the dict literally.
        assert h == compute_payload_hash({"x": 1})

    def test_native_dict_unchanged(self) -> None:
        """Plain dicts compute the same hash as before."""
        h = compute_payload_hash({"a": 1, "b": "hi"})
        # Manual computation to assert byte-stability.
        canonical = json.dumps(
            {"a": 1, "b": "hi"},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        assert h == hashlib.sha256(canonical).hexdigest()

    def test_compute_entry_hash_still_accepts_trustentry(self) -> None:
        """compute_entry_hash is the internal API that takes a Pydantic
        TrustEntry. The BaseModel guard is on compute_payload_hash only —
        compute_entry_hash must keep working on TrustEntry inputs."""
        p = Ed25519SignatureProvider.from_seed(b"E" * 32)
        entry = TrustEntry(
            seq=0,
            timestamp=datetime.now(UTC),
            actor_did="did:soul:typing",
            action="x.y",
            payload_hash="a" * 64,
            prev_hash=GENESIS_PREV_HASH,
            public_key=p.public_key,
        )
        entry.signature = p.sign(_signing_message(entry))
        # Should compute a stable digest, not raise.
        h = compute_entry_hash(entry)
        assert isinstance(h, str)
        assert len(h) == 64


# ---------------------------------------------------------------------------
# #199 — verify_chain at the spec layer (no manager wrapper)
# ---------------------------------------------------------------------------


class TestVerifyChainSpecLayerMonotonicity:
    """Direct spec-layer call. Catches a forged chain whose entries have
    backdated timestamps but otherwise valid hash chain + signatures."""

    def test_handcrafted_backdated_chain_fails(self) -> None:
        p = Ed25519SignatureProvider.from_seed(b"V" * 32)
        t0 = datetime.now(UTC) - timedelta(minutes=5)
        e0 = TrustEntry(
            seq=0,
            timestamp=t0,
            actor_did="did:soul:back",
            action="x.y",
            payload_hash="a" * 64,
            prev_hash=GENESIS_PREV_HASH,
            public_key=p.public_key,
        )
        e0.signature = p.sign(_signing_message(e0))
        # Backdate e1 to 30 minutes before e0.
        e1 = TrustEntry(
            seq=1,
            timestamp=t0 - timedelta(minutes=30),
            actor_did="did:soul:back",
            action="x.y",
            payload_hash="b" * 64,
            prev_hash=compute_entry_hash(e0),
            public_key=p.public_key,
        )
        e1.signature = p.sign(_signing_message(e1))
        chain = TrustChain(did="did:soul:back", entries=[e0, e1])

        valid, reason = verify_chain(chain)
        assert valid is False
        assert reason is not None
        assert "before previous entry" in reason
        assert "seq 1" in reason
