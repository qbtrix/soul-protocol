---
{
  "title": "Test Suite: Org Journal Spec — Actor, DataRef, and EventEntry Primitives",
  "summary": "Validates the foundational primitives of Soul Protocol's organizational journal spec: `Actor` (the entity writing an event), `DataRef` (an external data reference with cache policy), and `EventEntry` (an immutable journal record). The suite enforces UTC-only datetimes, non-anonymous writes, required scopes, and payload union handling.",
  "concepts": [
    "Actor",
    "DataRef",
    "EventEntry",
    "UTC-only datetime",
    "causation_id",
    "scope required",
    "action field",
    "cache_policy",
    "point_in_time",
    "payload union",
    "anonymous writes",
    "Literal validation",
    "org journal"
  ],
  "categories": [
    "testing",
    "spec layer",
    "org journal",
    "event sourcing",
    "test"
  ],
  "source_docs": [
    "a82055a38fd8a6c1"
  ],
  "backlinks": null,
  "word_count": 521,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The org journal is an append-only, scoped event log for multi-agent organizational workflows. Before agents can write to the journal or reference external data, the spec must enforce strict data contracts — no anonymous writers, no ambiguous timestamps, no scope-free events. This test file locks those contracts at the model level, preventing silent drift in the primitives that downstream components depend on.

## Actor

```python
actor = Actor(kind="agent", id="did:soul:sales-lead", scope_context=["org:sales"])
restored = Actor.model_validate_json(actor.model_dump_json())
assert restored == actor
```

Key validation rules:
- **`kind` is a `Literal`**: Only `"agent"`, `"user"`, and `"system"` are valid. Unknown kinds (`"wizard"`) raise `ValidationError`. This prevents actors from using arbitrary role strings that the rest of the system would not recognize.
- **`id` must be non-empty**: Empty `id` raises `ValidationError`. The doc string says "no anonymous writes" — every event in the journal must be attributable to a specific entity. Empty IDs would make audit trails unreliable.
- **`scope_context` defaults to `[]`**: System actors like `"system:kb-go"` may not have organizational scope; the empty list is a valid representation of "no scope context assigned."

## DataRef

`DataRef` points to an external data snapshot (Salesforce query, S3 object, Snowflake table) with a `point_in_time` that records when the data was current:

```python
ref = DataRef(
    source="salesforce",
    query="SELECT Id, Name FROM Account WHERE OwnerId = :me",
    point_in_time=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    cache_policy="ttl",
    cache_ttl_s=300,
)
```

**UTC-only enforcement** is strict:
- Naive datetimes raise `ValidationError` — callers cannot omit timezone info
- Non-UTC timezone-aware datetimes (e.g., UTC+5:30) also raise — the spec is UTC-only, not "any tz-aware"
- However, any timezone whose UTC offset is zero (e.g., `datetime.timezone.utc`) is accepted as equivalent

This strictness prevents a class of timezone bugs where two agents write `point_in_time` values that appear equal but are actually 5.5 hours apart.

`cache_policy` defaults to `"ttl"` (per the RFC) and is also a `Literal` — unknown policies raise `ValidationError`.

## EventEntry

`EventEntry` is the core journal record. Key invariants:

- **Naive `ts` raises**: All event timestamps must be UTC-aware — same reasoning as `DataRef.point_in_time`
- **Scope is required and non-empty**: `scope` must contain at least one non-empty string. This enforces that every event is scoped to an organizational context — no "global" writes that bypass access control.
- **Scope entries cannot be empty strings**: An entry like `[""]` is rejected even though the list is non-empty. This prevents accidentally unscoped events from slipping through on a technicality.
- **`action` is required**: `min_length=1` on the string. Empty action strings would break downstream routing.
- **`causation_id` is None for genesis events**: Unsolicited events (not caused by a prior event) have `None` causation, which round-trips cleanly. Non-genesis events carry a UUID that can be traversed to reconstruct the event chain.
- **Payload union**: `EventEntry` accepts either an inline dict or a `DataRef` as payload. Both are tested for clean round-trips.

## Known Gaps

No TODO or FIXME markers visible. The test file header notes that `find_corrections_for` filters on `causation_id` (not `correlation_id`) — but the `correlation_id` field behavior (if any) on `EventEntry` is not tested here. The file covers only the spec primitives; higher-level journal operations are covered in `test_decisions.py`.