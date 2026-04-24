---
{
  "title": "Test Suite for the Retrieval Spec: Credentials, Protocols, and Request Contracts",
  "summary": "This test suite validates the spec-level contracts defined in `soul_protocol.spec.retrieval` — covering `Credential` validation and expiry logic, structural Protocol conformance for sync and async adapters, `DataRef` promotion from dicts, and timezone-aware `RetrievalRequest` point-in-time fields. These tests intentionally contain no runtime machinery, serving as a conformance suite for any implementation of the retrieval standard.",
  "concepts": [
    "retrieval spec",
    "Credential",
    "SourceAdapter",
    "AsyncSourceAdapter",
    "DataRef",
    "RetrievalRequest",
    "Protocol conformance",
    "point-in-time",
    "expiry logic",
    "structural typing"
  ],
  "categories": [
    "testing",
    "retrieval",
    "spec",
    "test"
  ],
  "source_docs": [
    "ebff4c56f6ac8b8d"
  ],
  "backlinks": null,
  "word_count": 438,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Scope and Motivation

The retrieval vocabulary was extracted from `engine/retrieval/` into `spec/retrieval.py` during the `feat/0.3.2-prune-retrieval-infra` refactor. The concrete orchestration layer (routers, credential brokers, projection adapters) moved to the `pocketpaw` consumer. These spec tests exist to lock the contracts that moved, ensuring that any future refactor or third-party implementation can verify conformance without running the full runtime.

## Credential Validation (`TestCredentialValidation`)

The `Credential` model enforces that `source`, `token`, and `scopes` are all non-empty. Tests document exactly which conditions raise `ValidationError`:

- Empty `scopes` list → rejected (an unscoped credential would implicitly grant access to everything)
- Empty `source` string → rejected (makes the credential unroutable)
- Empty `token` string → rejected (a blank token is indistinguishable from no auth)

The auto-generated `id` field (UUID) is asserted to exist on a valid credential, confirming that `last_used_at` defaults to `None` (not set until first use).

## Credential Expiry (`TestCredentialIsExpired`)

```python
cred.is_expired()                  # uses datetime.now(UTC) internally
cred.is_expired(now=pinned_time)   # deterministic for tests
```

The `now` override parameter exists specifically to make boundary tests deterministic — wall-clock tests that check "exactly at expiry" are inherently flaky. The suite verifies the boundary semantics: `now == expires_at` is considered expired (not valid), preventing a class of credential-reuse bug at the exact expiry moment.

## Protocol Conformance (`TestProtocolConformance`)

The suite defines two stub adapters and verifies structural typing:

```python
class _StubSyncAdapter:
    supports_dataref: bool = False
    def query(self, request, credential): ...

class _StubAsyncAdapter(_StubSyncAdapter):
    async def aquery(self, request, credential): ...
```

Key assertions:
- A sync adapter matches `SourceAdapter` but NOT `AsyncSourceAdapter`
- An async adapter matches both
- A plain `object()` matches neither

This prevents adapter authors from accidentally shipping a class that claims async support but lacks `aquery`.

## DataRef Promotion (`TestDataRefPromotion`)

`RetrievalCandidate.content` is a union type. When the dict payload contains `"kind": "dataref"`, Pydantic automatically promotes it to a typed `DataRef` model. When the dict lacks that key, it stays as a plain dict. The tests pin this discrimination logic so that a Pydantic upgrade cannot silently change how content types are resolved.

## Point-in-Time Validation (`TestRetrievalRequestPointInTime`)

The `RetrievalRequest.point_in_time` field must be either `None` or a timezone-aware UTC datetime:

```python
# Accepted
point_in_time=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
point_in_time=None

# Rejected
point_in_time=datetime(2026, 4, 1, 12, 0, 0)  # naive datetime
```

Naive datetimes are rejected because comparisons between naive and aware datetimes raise a `TypeError` at runtime — catching this at validation time produces a cleaner error.

## Known Gaps

- Tests for `RetrievalRequest` scope matching (`match_scope`) live in a separate test file and are not duplicated here.
- The `AsyncSourceAdapter.aquery` signature is tested for structural presence but not for actual async execution behavior.