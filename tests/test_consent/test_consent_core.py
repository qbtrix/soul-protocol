# tests/test_consent/test_consent_core.py — Consent passes on the Soul runtime.
# Created: 2026-11-14 — Grant/recall/remember/revoke/expiry, PRIVATE and
#   cross-domain isolation, signature tamper detection, audit-or-deny for souls
#   without a private key, persistence round trips (.soul archive + directory),
#   and verification of the access log against the trust chain.

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from soul_protocol.runtime.consent import ConsentRegistry, hash_token, parse_duration
from soul_protocol.runtime.consent.models import ConsentEvent
from soul_protocol.runtime.exceptions import ConsentDeniedError, ConsentError
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryVisibility


async def _soul() -> Soul:
    soul = await Soul.birth("Consenty")
    await soul.remember("User has a knee injury from running", domain="health")
    await soul.remember("User sleeps about six hours a night", domain="health")
    await soul.remember("User salary is 80000 rupees", domain="finance")
    await soul.remember(
        "User secret health diagnosis",
        domain="health",
        visibility=MemoryVisibility.PRIVATE,
    )
    await soul.remember("User is building Soul Protocol", domain="work")
    return soul


async def _denied(coro) -> ConsentDeniedError:
    with pytest.raises(ConsentDeniedError) as info:
        await coro
    return info.value


# ---------- Granting ----------


async def test_grant_returns_signed_active_pass_and_token():
    soul = await _soul()
    consent_pass, token = soul.consent.grant("fitness-app", ["health"], duration="7d")

    assert token.startswith("scp_")
    assert consent_pass.status() == "active"
    assert consent_pass.signature_valid()
    assert consent_pass.token_hash == hash_token(token)
    assert token not in json.dumps(soul.consent.registry.to_dict())
    assert consent_pass.soul_did == soul.did
    assert consent_pass.expires_at - consent_pass.issued_at == timedelta(days=7)


async def test_grant_is_signed_onto_trust_chain():
    soul = await _soul()
    soul.consent.grant("fitness-app", ["health"], duration="1d")
    rows = soul.audit_log(action_prefix="consent.")
    assert [r["action"] for r in rows] == ["consent.grant"]
    assert rows[0]["summary"] == "fitness-app may use health"
    assert soul.verify_chain() == (True, None)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"app_id": "", "domains": ["health"], "duration": "1d"}, "Invalid app id"),
        ({"app_id": "bad app", "domains": ["health"], "duration": "1d"}, "Invalid app id"),
        ({"app_id": "a", "domains": [], "duration": "1d"}, "at least one domain"),
        ({"app_id": "a", "domains": [" "], "duration": "1d"}, "cannot be empty"),
        ({"app_id": "a", "domains": ["*"], "duration": "1d"}, "Wildcard"),
        ({"app_id": "a", "domains": ["health"], "duration": "0d"}, "greater than zero"),
        ({"app_id": "a", "domains": ["health"], "duration": "400d"}, "365"),
        ({"app_id": "a", "domains": ["health"], "duration": "soon"}, "Invalid duration"),
        ({"app_id": "a", "domains": ["health"], "duration": "1d", "access": "admin"}, "access"),
    ],
)
async def test_grant_rejects_bad_input(kwargs, message):
    soul = await _soul()
    app_id = kwargs.pop("app_id")
    domains = kwargs.pop("domains")
    with pytest.raises(ConsentError, match=message):
        soul.consent.grant(app_id, domains, **kwargs)
    assert soul.consent.registry.is_empty()


async def test_grant_needs_exactly_one_of_duration_or_expiry():
    soul = await _soul()
    with pytest.raises(ConsentError, match="exactly one"):
        soul.consent.grant("a", ["health"])
    with pytest.raises(ConsentError, match="exactly one"):
        soul.consent.grant(
            "a", ["health"], duration="1d", expires_at=datetime.now(UTC) + timedelta(days=1)
        )
    with pytest.raises(ConsentError, match="future"):
        soul.consent.grant("a", ["health"], expires_at=datetime.now(UTC) - timedelta(seconds=1))


async def test_duplicate_domains_are_collapsed():
    soul = await _soul()
    consent_pass, _ = soul.consent.grant("a", ["health", " health ", "work"], duration="1h")
    assert consent_pass.domains == ["health", "work"]


def test_parse_duration_units():
    assert parse_duration("30m") == timedelta(minutes=30)
    assert parse_duration("12H") == timedelta(hours=12)
    assert parse_duration("2w") == timedelta(weeks=2)
    assert parse_duration("365d") == timedelta(days=365)


# ---------- Reading ----------


async def test_recall_only_returns_granted_domains_and_never_private():
    soul = await _soul()
    _, token = soul.consent.grant("fitness-app", ["health"], duration="1d")

    results = await soul.consent.session(token).recall(
        "knee injury sleep salary secret diagnosis Soul Protocol", limit=20
    )

    contents = {r.content for r in results}
    assert "User has a knee injury from running" in contents
    assert all(r.domain == "health" for r in results)
    assert "User secret health diagnosis" not in contents
    assert "User salary is 80000 rupees" not in contents


async def test_recall_from_multiple_domains():
    soul = await _soul()
    _, token = soul.consent.grant("planner", ["health", "work"], duration="1d")
    results = await soul.consent.session(token).recall("User", limit=20)
    assert {r.domain for r in results} == {"health", "work"}


async def test_each_read_is_signed_with_returned_ids():
    soul = await _soul()
    _, token = soul.consent.grant("fitness-app", ["health"], duration="1d")
    results = await soul.consent.session(token).recall("knee injury")

    event = soul.consent.events(limit=1)[0]
    assert event.kind == "read"
    assert event.app_id == "fitness-app"
    assert event.memory_ids == [r.id for r in results]
    assert event.count == len(results)
    assert event.chain_seq is not None
    assert soul.audit_log(action_prefix="consent.read")
    assert soul.consent.verify()["unverified"] == 0


async def test_recall_from_other_domain_is_denied_and_logged():
    soul = await _soul()
    _, token = soul.consent.grant("fitness-app", ["health"], duration="1d")

    error = await _denied(soul.consent.session(token).recall("salary", domain="finance"))

    assert error.reason == "domain_not_allowed"
    assert error.app_id == "fitness-app"
    event = soul.consent.events(limit=1)[0]
    assert (event.kind, event.reason, event.domains) == (
        "denied",
        "domain_not_allowed",
        ["finance"],
    )
    assert soul.audit_log(action_prefix="consent.denied")


async def test_unknown_token_is_denied():
    soul = await _soul()
    error = await _denied(soul.consent.session("scp_not-a-real-token").recall("knee"))
    assert error.reason == "unknown_token"
    assert error.app_id is None


async def test_recall_limit_is_respected():
    soul = await _soul()
    _, token = soul.consent.grant("planner", ["health", "work"], duration="1d")
    assert len(await soul.consent.session(token).recall("User", limit=1)) == 1


# ---------- Expiry and revocation ----------


async def test_expired_pass_is_denied():
    soul = await _soul()
    consent_pass, token = soul.consent.grant("fitness-app", ["health"], duration="1h")
    later = consent_pass.expires_at + timedelta(seconds=1)

    error = await _denied(soul.consent.session(token).recall("knee", now=later))

    assert error.reason == "expired"
    assert consent_pass.status(later) == "expired"
    assert soul.consent.passes() == [consent_pass]
    assert soul.consent.registry.passes(now=later) == []


async def test_revoke_blocks_an_existing_session_immediately():
    soul = await _soul()
    consent_pass, token = soul.consent.grant("fitness-app", ["health"], duration="1d")
    session = soul.consent.session(token)
    assert await session.recall("knee")

    revoked = soul.consent.revoke(consent_pass.id, reason="done training")

    assert revoked.status() == "revoked"
    assert revoked.revoke_reason == "done training"
    error = await _denied(session.recall("knee"))
    assert error.reason == "revoked"
    assert [e.kind for e in soul.consent.events(limit=3)] == ["denied", "revoke", "read"]


async def test_revoke_twice_is_a_no_op_and_unknown_id_errors():
    soul = await _soul()
    consent_pass, _ = soul.consent.grant("a", ["health"], duration="1d")
    first = soul.consent.revoke(consent_pass.id)
    second = soul.consent.revoke(consent_pass.id)
    assert first.revoked_at == second.revoked_at
    assert len(soul.consent.events(app_id="a")) == 2  # grant + one revoke
    with pytest.raises(ConsentError, match="No consent pass"):
        soul.consent.revoke("cp_missing")


# ---------- Writing ----------


async def test_read_only_pass_cannot_write():
    soul = await _soul()
    _, token = soul.consent.grant("fitness-app", ["health"], duration="1d")
    error = await _denied(soul.consent.session(token).remember("Ran 5km today"))
    assert error.reason == "write_not_allowed"


async def test_read_write_pass_writes_to_granted_domain_only():
    soul = await _soul()
    _, token = soul.consent.grant("fitness-app", ["health"], duration="1d", access="read_write")
    session = soul.consent.session(token)

    memory_id = await session.remember("Ran 5km today", importance=6)
    event = soul.consent.events(limit=1)[0]
    assert (event.kind, event.memory_ids, event.domains) == ("write", [memory_id], ["health"])
    stored = await soul.recall("Ran 5km today", domain="health")
    assert any(m.id == memory_id for m in stored)

    error = await _denied(session.remember("Bought shoes", domain="finance"))
    assert error.reason == "domain_not_allowed"


# ---------- Tampering ----------


async def test_editing_a_pass_breaks_its_signature():
    soul = await _soul()
    consent_pass, token = soul.consent.grant("fitness-app", ["health"], duration="1d")
    consent_pass.domains.append("finance")

    error = await _denied(soul.consent.session(token).recall("salary"))

    assert error.reason == "invalid_signature"
    assert consent_pass.public_view()["signature_valid"] is False


async def test_extending_expiry_in_the_file_is_detected(tmp_path):
    soul = await _soul()
    _, token = soul.consent.grant("fitness-app", ["health"], duration="1h")
    soul_dir = tmp_path / "s"
    await soul.save_local(soul_dir)

    consent_file = soul_dir / "consent" / "consent.json"
    data = json.loads(consent_file.read_text(encoding="utf-8"))
    data["passes"][0]["expires_at"] = "2099-01-01T00:00:00+00:00"
    consent_file.write_text(json.dumps(data), encoding="utf-8")

    reloaded = await Soul.awaken(str(soul_dir))
    error = await _denied(reloaded.consent.session(token).recall("knee"))
    assert error.reason == "invalid_signature"


async def test_pass_from_another_soul_is_rejected():
    soul = await _soul()
    other = await Soul.birth("Other")
    consent_pass, token = other.consent.grant("fitness-app", ["health"], duration="1d")
    soul.consent.registry.add(consent_pass)

    error = await _denied(soul.consent.session(token).recall("knee"))
    assert error.reason == "invalid_signature"


async def test_edited_log_line_fails_verification():
    soul = await _soul()
    _, token = soul.consent.grant("fitness-app", ["health"], duration="1d")
    await soul.consent.session(token).recall("knee")
    assert soul.consent.verify()["unverified"] == 0

    soul.consent.registry.events(kind="read")[0].count = 0

    report = soul.consent.verify()
    assert report["unverified"] == 1
    assert report["unverified_events"][0]["kind"] == "read"


# ---------- Souls without a private key ----------


async def test_public_only_soul_cannot_grant_and_refuses_unaudited_reads(tmp_path):
    soul = await _soul()
    _, token = soul.consent.grant("fitness-app", ["health"], duration="1d")
    path = tmp_path / "shared.soul"
    await soul.export(path, include_keys=False)

    public_only = await Soul.awaken(str(path))
    assert public_only.can_sign is False

    with pytest.raises(ConsentError, match="private key"):
        public_only.consent.grant("other", ["health"], duration="1d")
    error = await _denied(public_only.consent.session(token).recall("knee"))
    assert error.reason == "audit_unavailable"
    # Revocation must still work without the key.
    consent_pass = public_only.consent.passes()[0]
    assert public_only.consent.revoke(consent_pass.id).status() == "revoked"


# ---------- Persistence ----------


@pytest.mark.parametrize("fmt", ["archive", "directory"])
async def test_passes_and_log_survive_save_and_load(tmp_path, fmt):
    soul = await _soul()
    kept, token = soul.consent.grant("fitness-app", ["health"], duration="1d", note="trial")
    gone, _ = soul.consent.grant("old-app", ["work"], duration="1d")
    soul.consent.revoke(gone.id)
    await soul.consent.session(token).recall("knee")

    if fmt == "archive":
        path = tmp_path / "s.soul"
        await soul.export(path, include_keys=True)
    else:
        path = tmp_path / "s"
        await soul.save_local(path)
    reloaded = await Soul.awaken(str(path))

    assert [p.id for p in reloaded.consent.passes()] == [kept.id]
    statuses = {p.id: p.status() for p in reloaded.consent.passes(include_inactive=True)}
    assert statuses == {kept.id: "active", gone.id: "revoked"}
    assert reloaded.consent.get(kept.id).note == "trial"
    assert len(reloaded.consent.events()) == len(soul.consent.events())
    assert reloaded.consent.verify()["unverified"] == 0
    assert reloaded.verify_chain() == (True, None)
    assert await reloaded.consent.session(token).recall("knee")


async def test_encrypted_archive_round_trip(tmp_path):
    soul = await _soul()
    consent_pass, token = soul.consent.grant("fitness-app", ["health"], duration="1d")
    path = tmp_path / "locked.soul"
    await soul.export(path, password="hunter2", include_keys=True)

    reloaded = await Soul.awaken(str(path), password="hunter2")
    assert reloaded.consent.get(consent_pass.id) is not None
    assert await reloaded.consent.session(token).recall("knee")


async def test_souls_without_consent_write_no_consent_file(tmp_path):
    soul = await Soul.birth("Plain")
    await soul.save_local(tmp_path / "plain")
    assert not (tmp_path / "plain" / "consent").exists()
    reloaded = await Soul.awaken(str(tmp_path / "plain"))
    assert reloaded.consent.registry.is_empty()


def test_registry_skips_malformed_rows_and_caps_events():
    registry = ConsentRegistry.from_dict(
        {"passes": [{"id": "broken"}], "events": [{"kind": "nope", "at": "x"}]}
    )
    assert registry.is_empty()

    small = ConsentRegistry(max_events=10)
    for i in range(12):
        small.record(ConsentEvent(kind="read", at=datetime.now(UTC), count=i))
    assert [e.count for e in small.overflow()] == [0, 1]  # batch past cap + 10% slack
