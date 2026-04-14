# test_spec/test_journal.py — Tests for the Org Journal spec primitives.
# Created: feat/journal-spec — Phase 1 slice of the Org Architecture RFC (PR #164).
# Covers: round-trip JSON, tz-aware datetime enforcement on EventEntry.ts and
# DataRef.point_in_time, scope required/non-empty, payload union (dict | DataRef),
# Actor.kind rejects unknown values, causation_id None (genesis) and UUID round-trip.

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from soul_protocol.spec import ACTION_NAMESPACES, Actor, DataRef, EventEntry


# ----- Actor ---------------------------------------------------------------


def test_actor_round_trips_json():
    """Actor serializes to JSON and back with all fields preserved."""
    actor = Actor(
        kind="agent",
        id="did:soul:sales-lead",
        scope_context=["org:sales", "org:sales:pipeline"],
    )
    restored = Actor.model_validate_json(actor.model_dump_json())
    assert restored == actor


def test_actor_rejects_unknown_kind():
    """Actor.kind is a Literal — unknown values raise at validation time."""
    with pytest.raises(ValidationError):
        Actor(kind="wizard", id="did:soul:merlin")  # type: ignore[arg-type]


def test_actor_requires_non_empty_id():
    """Actor.id must be non-empty — no anonymous writes."""
    with pytest.raises(ValidationError):
        Actor(kind="user", id="")


def test_actor_scope_context_defaults_to_empty_list():
    """scope_context defaults to an empty list when omitted."""
    actor = Actor(kind="system", id="system:kb-go")
    assert actor.scope_context == []


# ----- DataRef -------------------------------------------------------------


def test_dataref_round_trips_json():
    """DataRef serializes and deserializes with tz-aware point_in_time."""
    ref = DataRef(
        source="salesforce",
        query="SELECT Id, Name FROM Account WHERE OwnerId = :me",
        point_in_time=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
        cache_policy="ttl",
        cache_ttl_s=300,
    )
    restored = DataRef.model_validate_json(ref.model_dump_json())
    assert restored == ref
    assert restored.point_in_time.tzinfo is not None


def test_dataref_rejects_naive_point_in_time():
    """Naive datetimes on point_in_time raise — UTC-aware only."""
    with pytest.raises(ValidationError):
        DataRef(
            source="snowflake",
            query="SELECT 1",
            point_in_time=datetime(2026, 4, 13, 12, 0),  # naive
        )


def test_dataref_rejects_non_utc_tz_aware_datetime():
    """Non-UTC tz-aware datetimes raise — the spec is UTC-only, not
    'any tz-aware'. Callers normalize at the source."""
    tz = timezone(timedelta(hours=5, minutes=30))
    with pytest.raises(ValidationError):
        DataRef(
            source="s3",
            query="s3://bucket/key",
            point_in_time=datetime(2026, 4, 13, 17, 0, tzinfo=tz),
        )


def test_dataref_accepts_alternate_utc_equivalent_tz():
    """Any tzinfo whose utcoffset is zero (e.g. datetime.timezone.utc,
    a zero-offset timezone(timedelta(0))) is accepted."""
    zero_offset = timezone(timedelta(0), name="UTC+0")
    ref = DataRef(
        source="s3",
        query="s3://bucket/key",
        point_in_time=datetime(2026, 4, 13, 12, 0, tzinfo=zero_offset),
    )
    assert ref.point_in_time.utcoffset() == timedelta(0)


def test_dataref_default_cache_policy_is_ttl():
    """cache_policy defaults to 'ttl' per the RFC."""
    ref = DataRef(
        source="gdrive",
        query="file:abc123",
        point_in_time=datetime(2026, 4, 13, tzinfo=UTC),
    )
    assert ref.cache_policy == "ttl"
    assert ref.cache_ttl_s is None


def test_dataref_rejects_unknown_cache_policy():
    """cache_policy is a Literal — unknown values raise."""
    with pytest.raises(ValidationError):
        DataRef(
            source="s3",
            query="s3://x",
            point_in_time=datetime(2026, 4, 13, tzinfo=UTC),
            cache_policy="forever",  # type: ignore[arg-type]
        )


# ----- EventEntry ----------------------------------------------------------


def _make_event(**overrides) -> EventEntry:
    base = dict(
        id=uuid4(),
        ts=datetime.now(UTC),
        actor=Actor(kind="agent", id="did:soul:sales-lead", scope_context=["org:sales"]),
        action="retrieval.query",
        scope=["org:sales:pocket:acme"],
        causation_id=None,
        correlation_id=None,
        payload={"q": "what is the status of the Acme deal?"},
    )
    base.update(overrides)
    return EventEntry(**base)


def test_event_round_trips_json_with_dict_payload():
    """EventEntry with an inline dict payload round-trips cleanly."""
    event = _make_event()
    restored = EventEntry.model_validate_json(event.model_dump_json())
    assert restored == event
    assert isinstance(restored.payload, dict)


def test_event_round_trips_json_with_dataref_payload():
    """EventEntry with a DataRef payload round-trips cleanly."""
    ref = DataRef(
        source="salesforce",
        query="SELECT Id FROM Opportunity WHERE Amount > 10000",
        point_in_time=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
        cache_policy="invalidate_on_event",
    )
    event = _make_event(payload=ref)
    restored = EventEntry.model_validate_json(event.model_dump_json())
    assert isinstance(restored.payload, DataRef)
    assert restored.payload == ref


def test_event_rejects_naive_ts():
    """Naive datetimes on ts raise — the journal refuses non-UTC-aware writes."""
    with pytest.raises(ValidationError):
        _make_event(ts=datetime(2026, 4, 13, 12, 0))


def test_event_requires_non_empty_scope():
    """Events must carry at least one scope tag — no 'global' writes."""
    with pytest.raises(ValidationError):
        _make_event(scope=[])


def test_event_rejects_empty_string_scope_entry():
    """Scope entries must themselves be non-empty strings."""
    with pytest.raises(ValidationError):
        _make_event(scope=["org:sales", ""])


def test_event_requires_non_empty_action():
    """action is required — min_length=1."""
    with pytest.raises(ValidationError):
        _make_event(action="")


def test_event_causation_id_none_for_genesis():
    """causation_id is None for genesis / unsolicited events and round-trips."""
    event = _make_event(action="org.created", causation_id=None)
    restored = EventEntry.model_validate_json(event.model_dump_json())
    assert restored.causation_id is None


def test_event_causation_id_round_trips_when_set():
    """A causation_id pointing at a prior event preserves its UUID through JSON."""
    prior = uuid4()
    event = _make_event(action="human.corrected", causation_id=prior)
    restored = EventEntry.model_validate_json(event.model_dump_json())
    assert restored.causation_id == prior


def test_event_correlation_id_round_trips():
    """correlation_id binds events within a session / flow and survives JSON."""
    correlation = uuid4()
    event = _make_event(correlation_id=correlation)
    restored = EventEntry.model_validate_json(event.model_dump_json())
    assert restored.correlation_id == correlation


def test_event_prev_hash_and_sig_round_trip():
    """Optional prev_hash and sig bytes survive the JSON round-trip."""
    event = _make_event(prev_hash=b"\x00\x01\x02\x03", sig=b"\xde\xad\xbe\xef")
    restored = EventEntry.model_validate_json(event.model_dump_json())
    assert restored.prev_hash == b"\x00\x01\x02\x03"
    assert restored.sig == b"\xde\xad\xbe\xef"


# ----- ACTION_NAMESPACES ---------------------------------------------------


def test_action_namespaces_includes_expected_catalog_entries():
    """The initial catalog covers the primitives called out in the RFC."""
    expected = {
        "org.created",
        "retrieval.query",
        "agent.proposed",
        "human.corrected",
        "dataref.resolved",
        "memory.remembered",
        "kb.source.ingested",
        "scope.created",
    }
    assert expected.issubset(set(ACTION_NAMESPACES))


def test_action_field_is_not_enum_enforced():
    """action is free-form — callers can ship new namespaces additively."""
    event = _make_event(action="custom.vertical.event")
    assert event.action == "custom.vertical.event"


def test_action_namespaces_excludes_runtime_specific_fabric():
    """Fabric is a runtime-specific concept (pocket object store) and
    must not ship in the framework-agnostic catalog. Runtimes extend
    the tuple from their own code."""
    assert not any(ns.startswith("fabric.") for ns in ACTION_NAMESPACES)


# ----- payload union discriminator -----------------------------------------


def test_payload_dict_with_dataref_shaped_keys_stays_a_dict():
    """A plain dict payload whose keys happen to overlap DataRef
    (``source``, ``query``, ``point_in_time``) must deserialize as a
    dict, not silently coerce into a DataRef."""
    lookalike = {
        "source": "user typed this",
        "query": "what's the status?",
        "point_in_time": "2026-04-13T12:00:00+00:00",
    }
    event = _make_event(payload=lookalike)
    restored = EventEntry.model_validate_json(event.model_dump_json())
    assert isinstance(restored.payload, dict)
    assert not isinstance(restored.payload, DataRef)
    assert restored.payload["source"] == "user typed this"


def test_payload_dataref_round_trips_through_the_union():
    """A DataRef payload round-trips through JSON as a DataRef."""
    ref = DataRef(
        source="salesforce",
        query="SELECT Id FROM Account",
        point_in_time=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    )
    event = _make_event(payload=ref)
    restored = EventEntry.model_validate_json(event.model_dump_json())
    assert isinstance(restored.payload, DataRef)
    assert restored.payload.source == "salesforce"


def test_payload_plain_dict_unchanged_by_discriminator():
    """Ordinary dict payloads (no DataRef-ish keys) round-trip unchanged."""
    event = _make_event(payload={"note": "hello", "count": 3})
    restored = EventEntry.model_validate_json(event.model_dump_json())
    assert isinstance(restored.payload, dict)
    assert restored.payload == {"note": "hello", "count": 3}


def test_payload_dataref_json_carries_discriminator_marker():
    """DataRef's JSON form stamps ``__dataref__: true`` so consumers
    (and the union resolver) can tell it apart from a plain dict."""
    import json as _json

    ref = DataRef(
        source="gdrive",
        query="file:abc",
        point_in_time=datetime(2026, 4, 13, tzinfo=UTC),
    )
    payload = _json.loads(ref.model_dump_json())
    assert payload.get("__dataref__") is True
