# tests/test_consent/test_consent_review.py — Regression tests for the #326 review.
# Created: 2026-11-25 — Revoked/expired-token floods, signed trims, chain-backed
#   revocation, chain auto-pruning vs. log verification, app-write provenance,
#   write rollback on any error, social writes, key rotation, junk-token files,
#   and pruning of long-ended passes.

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.exceptions import ConsentDeniedError, ConsentError
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryType
from soul_protocol.spec.memory import MemoryProvenance


async def _soul() -> Soul:
    soul = await Soul.birth("Review")
    await soul.remember("User has a knee injury", domain="health")
    await soul.remember("User salary is 80000 rupees", domain="finance")
    return soul


async def _refused(coro) -> str:
    with pytest.raises(ConsentDeniedError) as info:
        await coro
    return info.value.reason


async def test_revoked_token_flood_cannot_push_real_events_out():
    soul = await _soul()
    soul.consent.registry.max_events = 50
    consent_pass, token = soul.consent.grant("fit", ["health"], duration="1d")
    await soul.consent.session(token).recall("knee")
    soul.consent.revoke(consent_pass.id)
    chain_before = soul.trust_chain.length

    for _ in range(1100):
        assert await _refused(soul.consent.session(token).recall("knee")) == "revoked"

    # One signed denial line for the whole burst; the rest are folded.
    assert soul.trust_chain.length == chain_before + 1
    kinds = [e.kind for e in soul.consent.events()]
    assert kinds == ["denied", "revoke", "read", "grant"]
    report = soul.consent.verify()
    assert report["ok"] is True
    assert report["pending_denials"] == 1099


async def test_folded_denials_are_counted_on_the_next_line():
    soul = await _soul()
    consent_pass, token = soul.consent.grant("fit", ["health"], duration="1d")
    session = soul.consent.session(token)
    start = consent_pass.issued_at
    for minutes in (1, 2, 3):
        await _refused(
            session.recall("x", domain="finance", now=start + timedelta(minutes=minutes))
        )
    assert len(soul.consent.events(app_id="fit")) == 2  # grant + first denial

    await _refused(session.recall("x", domain="finance", now=start + timedelta(hours=2)))
    latest = soul.consent.events(limit=1)[0]
    assert (latest.kind, latest.count) == ("denied", 3)


async def test_grant_and_revoke_lines_survive_heavy_reads():
    soul = await _soul()
    soul.consent.registry.max_events = 20
    _, token = soul.consent.grant("fit", ["health"], duration="1d")
    for _ in range(60):
        await soul.consent.session(token).recall("knee")
    assert len(soul.consent.events()) <= 23  # cap + slack
    assert soul.consent.registry.events(kind="grant")
    assert soul.consent.verify()["ok"] is True


async def test_editing_a_trim_record_is_detected():
    soul = await _soul()
    soul.consent.registry.max_events = 3
    _, token = soul.consent.grant("fit", ["health"], duration="1d")
    for _ in range(6):
        await soul.consent.session(token).recall("knee")
    trim = soul.consent.registry._trims[0]
    dropped = trim.seqs[0]
    trim.seqs.remove(dropped)

    report = soul.consent.verify()
    assert report["ok"] is False
    assert report["trims_verified"] < report["trims"]


async def test_revocation_is_read_from_the_signed_chain(tmp_path):
    soul = await _soul()
    consent_pass, token = soul.consent.grant("fit", ["health"], duration="1d")
    soul.consent.revoke(consent_pass.id, reason="ended")
    await soul.save_local(tmp_path / "s")

    consent_file = tmp_path / "s" / "consent" / "consent.json"
    data = json.loads(consent_file.read_text(encoding="utf-8"))
    data["passes"][0]["revoked_at"] = None
    data["events"] = [e for e in data["events"] if e["kind"] != "revoke"]
    consent_file.write_text(json.dumps(data), encoding="utf-8")

    reloaded = await Soul.awaken(str(tmp_path / "s"))
    assert await _refused(reloaded.consent.session(token).recall("knee")) == "revoked"


async def test_chain_auto_pruning_does_not_break_log_verification():
    soul = await _soul()
    soul.trust_chain_manager.max_entries = 10
    _, token = soul.consent.grant("fit", ["health"], duration="1d")
    for _ in range(25):
        await soul.consent.session(token).recall("knee")

    assert soul.verify_chain() == (True, None)
    report = soul.consent.verify()
    assert report["pruned"] > 0
    assert report["unverified"] == 0
    assert report["ok"] is True


async def test_app_writes_are_tagged_with_the_app():
    soul = await _soul()
    _, token = soul.consent.grant("coach", ["health"], duration="1d", access="read_write")
    memory_id = await soul.consent.session(token).remember("Ran 5km today")
    entry, _tier = await soul.memory.find_by_id(memory_id)
    assert entry.provenance == MemoryProvenance.AGENT
    assert entry.source == "app:coach"


async def test_write_is_rolled_back_on_any_error(monkeypatch):
    soul = await _soul()
    _, token = soul.consent.grant("coach", ["health"], duration="1d", access="read_write")
    real_record = soul.consent._record

    def failing_record(event, *, require_signature):
        if event.kind == "write":
            raise OSError("disk full")
        return real_record(event, require_signature=require_signature)

    monkeypatch.setattr(soul.consent, "_record", failing_record)
    with pytest.raises(OSError):
        await soul.consent.session(token).remember("Ran 5km today")

    assert not [m for m in await soul.recall("Ran 5km", domain="health") if "5km" in m.content]
    assert soul.audit_log(action_prefix="memory.purge")


async def test_apps_cannot_write_social_memories():
    soul = await _soul()
    _, token = soul.consent.grant("coach", ["health"], duration="1d", access="read_write")
    with pytest.raises(ConsentError, match="social"):
        await soul.consent.session(token).remember("Bob is a friend", type=MemoryType.SOCIAL)


async def test_passes_signed_with_a_rotated_key_are_refused():
    soul = await _soul()
    _, token = soul.consent.grant("fit", ["health"], duration="1d")
    new_provider = Ed25519SignatureProvider()
    soul._signature_provider = new_provider
    soul.trust_chain_manager.provider = new_provider

    assert await _refused(soul.consent.session(token).recall("knee")) == "invalid_signature"


async def test_junk_token_alone_does_not_create_a_consent_file(tmp_path):
    soul = await _soul()
    await _refused(soul.consent.session("scp_junk").recall("knee"))
    await soul.save_local(tmp_path / "s")
    assert not (tmp_path / "s" / "consent").exists()


async def test_long_ended_passes_are_pruned_on_next_grant():
    soul = await _soul()
    old, _ = soul.consent.grant("old", ["health"], duration="1h")
    later = old.expires_at + timedelta(days=91)
    soul.consent.grant("new", ["health"], duration="1h", now=later)
    assert soul.consent.get(old.id) is None
