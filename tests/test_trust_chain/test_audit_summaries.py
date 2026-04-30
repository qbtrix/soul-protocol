# tests/test_trust_chain/test_audit_summaries.py — Audit-log summary registry (#201).
# Created: 2026-04-29 — Verifies that:
#   1. The default formatter registry produces a useful summary for every
#      action namespace currently emitted by Soul (memory.write,
#      memory.forget, memory.supersede, bond.strengthen, bond.weaken,
#      evolution.proposed, evolution.applied, learning.event).
#   2. An explicit ``summary=`` passed to ``TrustChainManager.append``
#      overrides the registry default.
#   3. Two chains with identical payloads but different summaries produce
#      the same hash chain — proving ``summary`` is excluded from the
#      canonical bytes used for hashing and signing.
#   4. Pre-#201 chains (TrustEntry without ``summary``) load with
#      ``summary=""`` via the Pydantic default and verify unchanged.

from __future__ import annotations

import json

import pytest

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.trust.manager import (
    _SUMMARY_FORMATTERS,
    TrustChainManager,
    _default_summary,
)
from soul_protocol.runtime.types import Interaction
from soul_protocol.spec.trust import (
    TrustChain,
    TrustEntry,
    compute_entry_hash,
    verify_chain,
)


def _seeded_provider() -> Ed25519SignatureProvider:
    return Ed25519SignatureProvider.from_seed(b"S" * 32)


# ---------------------------------------------------------------------------
# Registry coverage — every emitted Soul action has a useful default
# ---------------------------------------------------------------------------


def test_registry_covers_all_soul_emitted_actions():
    """Every action Soul appends today must have a registered formatter."""
    expected = {
        "memory.write",
        "memory.forget",
        "memory.supersede",
        "bond.strengthen",
        "bond.weaken",
        "evolution.proposed",
        "evolution.applied",
        "learning.event",
    }
    assert expected.issubset(_SUMMARY_FORMATTERS.keys())


def test_default_summary_memory_write_pluralization():
    assert _default_summary("memory.write", {"count": 0}) == "0 memories"
    assert _default_summary("memory.write", {"count": 1}) == "1 memory"
    assert _default_summary("memory.write", {"count": 3}) == "3 memories"


def test_default_summary_memory_forget_truncates_id():
    s = _default_summary(
        "memory.forget",
        {"id": "abcd1234efgh5678", "tier": "episodic"},
    )
    assert s == "deleted episodic/abcd1234"


def test_default_summary_memory_supersede_truncates_both_ids():
    s = _default_summary(
        "memory.supersede",
        {"old_id": "old123456789", "new_id": "new987654321"},
    )
    assert s == "replaced old12345 with new98765"


def test_default_summary_bond_strengthen_includes_user():
    s = _default_summary(
        "bond.strengthen",
        {"user_id": "alice", "delta": 0.5, "new_strength": 50.5},
    )
    assert s == "+0.50 for alice"


def test_default_summary_bond_strengthen_falls_back_to_default_user():
    s = _default_summary(
        "bond.strengthen",
        {"user_id": None, "delta": 1.0, "new_strength": 51.0},
    )
    assert s == "+1.00 for default"


def test_default_summary_bond_weaken_uses_negative_sign():
    s = _default_summary(
        "bond.weaken",
        {"user_id": "alice", "delta": 0.3, "new_strength": 49.7},
    )
    assert s == "-0.30 for alice"


def test_default_summary_evolution_proposed_uses_trait():
    s = _default_summary(
        "evolution.proposed",
        {"trait": "communication.warmth", "new_value": "high", "reason": "feedback"},
    )
    assert s == "communication.warmth"


def test_default_summary_evolution_applied_falls_back_when_trait_absent():
    """The Soul payload only has mutation_id — registry falls back to 'mutation'."""
    s = _default_summary("evolution.applied", {"mutation_id": "m1"})
    assert s == "applied mutation"


def test_default_summary_evolution_applied_uses_trait_when_present():
    s = _default_summary("evolution.applied", {"trait": "warmth"})
    assert s == "applied warmth"


def test_default_summary_learning_event_uses_summary_field():
    s = _default_summary("learning.event", {"summary": "learned to listen"})
    assert s == "learned to listen"


def test_default_summary_learning_event_default_when_missing():
    s = _default_summary("learning.event", {"domain": "cooking", "score": 0.8})
    assert s == "learning event"


def test_default_summary_unknown_action_returns_empty():
    assert _default_summary("anything.unregistered", {}) == ""


def test_default_summary_handles_malformed_payload_gracefully():
    """Formatters must not raise when the payload is missing expected keys."""
    # No fields at all
    assert _default_summary("memory.write", {}) == "? memories"
    assert _default_summary("memory.forget", {}) == "deleted ?/"
    assert _default_summary("memory.supersede", {}) == "replaced  with "
    # Wrong types
    assert _default_summary("bond.strengthen", {"delta": "not-a-float"}) == ""


# ---------------------------------------------------------------------------
# Manager-level summary behaviour
# ---------------------------------------------------------------------------


def test_append_uses_registry_default_when_summary_omitted():
    mgr = TrustChainManager(did="did:soul:test", provider=_seeded_provider())
    entry = mgr.append("memory.write", {"count": 4})
    assert entry.summary == "4 memories"


def test_explicit_summary_overrides_registry_default():
    mgr = TrustChainManager(did="did:soul:test", provider=_seeded_provider())
    entry = mgr.append(
        "memory.write",
        {"count": 4},
        summary="custom note",
    )
    assert entry.summary == "custom note"


def test_explicit_empty_string_summary_is_kept_not_replaced():
    """Caller passes ``summary=""`` to opt out of the default formatter."""
    mgr = TrustChainManager(did="did:soul:test", provider=_seeded_provider())
    entry = mgr.append("memory.write", {"count": 4}, summary="")
    assert entry.summary == ""


def test_audit_log_includes_summary():
    mgr = TrustChainManager(did="did:soul:test", provider=_seeded_provider())
    mgr.append("memory.write", {"count": 2})
    mgr.append("bond.strengthen", {"user_id": "alice", "delta": 0.5, "new_strength": 50.5})

    rows = mgr.audit_log()
    assert all("summary" in row for row in rows)
    assert rows[0]["summary"] == "2 memories"
    assert rows[1]["summary"] == "+0.50 for alice"


# ---------------------------------------------------------------------------
# Cryptographic-exclusion guarantee — summary changes don't break the chain
# ---------------------------------------------------------------------------


def test_summary_excluded_from_entry_hash():
    """Two entries identical in every cryptographic field but with different
    summaries must produce the same compute_entry_hash."""
    mgr_a = TrustChainManager(did="did:soul:test", provider=_seeded_provider())
    mgr_b = TrustChainManager(did="did:soul:test", provider=_seeded_provider())

    # Force the same timestamp on both so all canonical fields match.
    from datetime import UTC, datetime

    ts = datetime(2026, 4, 29, 12, 0, 0, tzinfo=UTC)
    entry_a = mgr_a.append("memory.write", {"count": 3}, summary="three things", timestamp=ts)
    entry_b = mgr_b.append("memory.write", {"count": 3}, summary="totally different", timestamp=ts)

    # Same payload + same canonical fields -> same entry hash regardless of summary.
    assert compute_entry_hash(entry_a) == compute_entry_hash(entry_b)


def test_chain_verifies_after_summary_edit():
    """An attacker (or a tool) editing only the summary on a stored entry
    should NOT break verification — that's the point of excluding it from
    the canonical bytes."""
    mgr = TrustChainManager(did="did:soul:test", provider=_seeded_provider())
    mgr.append("memory.write", {"count": 1})
    mgr.append("memory.forget", {"id": "abcd1234", "tier": "episodic"})

    # Round-trip through dict, mutate one summary, re-validate.
    data = mgr.to_dict()
    data["entries"][0]["summary"] = "rewritten by tooling"
    chain = TrustChain.model_validate(data)

    valid, reason = verify_chain(chain)
    assert valid is True, reason
    assert chain.entries[0].summary == "rewritten by tooling"


# ---------------------------------------------------------------------------
# Back-compat — pre-#201 chains have no summary field
# ---------------------------------------------------------------------------


def test_pre_201_entry_without_summary_loads_with_empty_default():
    """Older chain.json files have no ``summary`` key on entries — Pydantic
    should fill in the default empty string."""
    # Build a pre-#201-style entry dict (no ``summary`` key at all)
    legacy_entry_dict = {
        "seq": 0,
        "timestamp": "2026-04-29T12:00:00+00:00",
        "actor_did": "did:soul:legacy",
        "action": "memory.write",
        "payload_hash": "a" * 64,
        "prev_hash": "0" * 64,
        "signature": "",
        "algorithm": "ed25519",
        "public_key": "",
    }
    assert "summary" not in legacy_entry_dict

    entry = TrustEntry.model_validate(legacy_entry_dict)
    assert entry.summary == ""


def test_pre_201_chain_verifies_after_round_trip():
    """A chain serialised before #201 is still a valid TrustChain JSON
    document. Loading and verifying must not fail because of the missing
    summary field."""
    mgr = TrustChainManager(did="did:soul:test", provider=_seeded_provider())
    for i in range(4):
        mgr.append("memory.write", {"i": i})

    # Strip ``summary`` from the serialised entries to mimic a pre-#201 archive.
    data = mgr.to_dict()
    for e in data["entries"]:
        e.pop("summary", None)

    chain = TrustChain.model_validate(data)
    valid, reason = verify_chain(chain)
    assert valid is True, reason
    assert all(e.summary == "" for e in chain.entries)


def test_audit_log_returns_empty_string_for_pre_201_entries():
    """audit_log() on a chain whose entries have summary='' (the legacy
    default) should return ``summary=''`` rather than crashing or
    fabricating a value at read time."""
    # Build a manager whose chain has stripped-summary entries
    mgr = TrustChainManager(did="did:soul:test", provider=_seeded_provider())
    mgr.append("memory.write", {"count": 1})
    data = mgr.to_dict()
    for e in data["entries"]:
        e.pop("summary", None)
    restored = TrustChainManager.from_dict(data, provider=_seeded_provider())

    rows = restored.audit_log()
    assert rows[0]["summary"] == ""


# ---------------------------------------------------------------------------
# Soul-level integration — observe / supersede / forget produce useful summaries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soul_observe_emits_useful_summary():
    soul = await Soul.birth("AuditSoul")
    await soul.observe(Interaction(user_input="hi", agent_output="hello"))

    mem_rows = soul.audit_log(action_prefix="memory.write")
    assert mem_rows
    summary = mem_rows[-1]["summary"]
    assert summary  # non-empty
    assert "memor" in summary  # "X memory" or "X memories"


@pytest.mark.asyncio
async def test_soul_bond_strengthen_summary_carries_user():
    soul = await Soul.birth("AuditSoul")
    soul._bonds.strengthen(amount=1.0, user_id="alice")

    rows = soul.audit_log(action_prefix="bond.strengthen")
    assert rows
    assert "alice" in rows[-1]["summary"]


@pytest.mark.asyncio
async def test_soul_supersede_summary_includes_both_id_prefixes():
    soul = await Soul.birth("AuditSoul")
    mid = await soul.remember("first version")
    res = await soul.supersede(mid, "second version", reason="updated")
    assert res["found"] is True

    rows = soul.audit_log(action_prefix="memory.supersede")
    assert rows
    summary = rows[-1]["summary"]
    assert summary.startswith("replaced ")
    assert "with" in summary


@pytest.mark.asyncio
async def test_soul_propose_evolution_uses_explicit_summary():
    """propose_evolution passes summary=f'{trait} -> {new_value}'."""
    soul = await Soul.birth("AuditSoul")
    await soul.propose_evolution("communication.warmth", "high", reason="user feedback")

    rows = soul.audit_log(action_prefix="evolution.proposed")
    assert rows
    assert rows[-1]["summary"] == "communication.warmth -> high"


@pytest.mark.asyncio
async def test_soul_audit_json_round_trip_preserves_summary(tmp_path):
    """End-to-end: save/awaken preserves summaries across the JSON boundary."""
    soul = await Soul.birth("RoundTripSoul")
    await soul.observe(Interaction(user_input="hi", agent_output="hi"))
    soul._bonds.strengthen(amount=1.0)
    pre = soul.audit_log()

    soul_dir = tmp_path / "rt-soul"
    await soul.save_local(soul_dir)
    soul2 = await Soul.awaken(soul_dir)
    post = soul2.audit_log()

    assert len(post) == len(pre)
    for a, b in zip(pre, post):
        assert a["summary"] == b["summary"]
        assert a["payload_hash"] == b["payload_hash"]


def test_serialized_chain_does_include_summary_field():
    """to_dict()/JSON serialisation should include the summary key."""
    mgr = TrustChainManager(did="did:soul:test", provider=_seeded_provider())
    mgr.append("memory.write", {"count": 2})
    payload = json.dumps(mgr.to_dict())
    assert "summary" in payload
    assert "2 memories" in payload
