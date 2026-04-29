---
{
  "title": "Retrieval Spec — Request/Response Models, Adapter Protocols, Credential Broker, and Exception Hierarchy",
  "summary": "This module defines the complete vocabulary for soul retrieval: request and response models (`RetrievalRequest`, `RetrievalResult`), the `SourceAdapter` and `AsyncSourceAdapter` protocols, the `CredentialBroker` interface for federated source access, a `DataRef` type for Zero-Copy candidate payloads, and a structured exception hierarchy. Concrete implementations (the router, in-memory broker, projection adapters) live in the consuming runtime.",
  "concepts": [
    "RetrievalRequest",
    "RetrievalResult",
    "SourceAdapter",
    "AsyncSourceAdapter",
    "CredentialBroker",
    "Credential",
    "DataRef",
    "Zero-Copy",
    "point_in_time",
    "time travel",
    "NoSourcesError",
    "CredentialExpiredError",
    "RetrievalTrace",
    "CandidateSource"
  ],
  "categories": [
    "retrieval",
    "spec layer",
    "protocol interfaces",
    "federated sources"
  ],
  "source_docs": [
    "5ef4ef753a42e6fe"
  ],
  "backlinks": null,
  "word_count": 467,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Retrieval is the bridge between stored soul knowledge and the LLM context window. When an agent answers a question, it dispatches a `RetrievalRequest` through a router that queries registered sources — soul memories, kb articles, external APIs — and merges the results into a ranked `RetrievalResult`. This module defines every type a third-party runtime needs to implement or consume that flow without depending on PocketPaw's concrete router.

## Request and Response Models

### `RetrievalRequest`
Carries the query, the requesting actor (for journal logging), scope context (for source filtering), dispatch strategy, timeout, and an optional `point_in_time` for historical queries:

```python
class RetrievalRequest(BaseModel):
    query: str
    actor: Actor
    scopes: list[str]
    strategy: Literal["first", "parallel", "sequential"]
    timeout_s: float
    point_in_time: datetime | None  # UTC, validated
```

`point_in_time` enables time-travel queries against sources that support snapshots (Drive revisions, Salesforce `AT`, Snowflake TIME TRAVEL). The UTC validator (`_point_in_time_must_be_utc`) prevents naive datetimes from silently producing wrong historical windows.

### `RetrievalResult`
The merged output: candidates list, which sources were queried, which failed (with reason), total latency, and an optional `RetrievalTrace` receipt for downstream observability.

## Zero-Copy Data References

`DataRef` in this module is a **candidate identifier** — different from the journal-layer `DataRef` which is a query recipe. Here, a source adapter returns a `RetrievalCandidate` whose `content` is a `DataRef` pointing to a specific record in an external system:

```python
class DataRef(BaseModel):
    kind: Literal["dataref"] = "dataref"
    source: str      # "drive", "salesforce"
    id: str          # stable record ID
    revision_id: str | None
    extra: dict[str, Any]
```

The consumer resolves the ref at query time rather than copying the data into the org boundary. A discriminator guard (`_promote_dataref_dict`) promotes dicts with `kind="dataref"` to typed `DataRef` objects on deserialization, preventing Pydantic's union from silently leaving them as plain dicts.

## Source Adapter Protocols

```python
class SourceAdapter(Protocol):
    supports_dataref: bool
    def query(self, request, credential) -> list[RetrievalCandidate]: ...

class AsyncSourceAdapter(Protocol):
    def query(...)  -> list[RetrievalCandidate]: ...
    async def aquery(...) -> list[RetrievalCandidate]: ...
```

`AsyncSourceAdapter` is a structural tag — adapters with async backends implement `aquery` in addition to `query`. The router detects `aquery` via `inspect.iscoroutinefunction` rather than requiring all sync-only adapters to stub the async method.

## Credential Broker

Federated sources require short-lived scoped tokens. The `CredentialBroker` protocol mints and manages them:

- `acquire(source, scopes)` — mints a token
- `ensure_usable(credential, requester_scopes)` — raises `CredentialScopeError` or `CredentialExpiredError` if not valid
- `mark_used(credential)` — updates `last_used_at` for audit
- `revoke(credential_id)` — invalidates immediately

## Exception Hierarchy

```
RetrievalError
  ├─ NoSourcesError
  ├─ SourceTimeoutError
  ├─ CredentialScopeError
  └─ CredentialExpiredError
```

Structured exceptions let callers handle different failure modes specifically rather than catching a broad `Exception`.

## Known Gaps

- `PointInTimeNotSupported` is raised by adapters that can't honor time-travel requests. The router catches it and records the source in `sources_failed` — but the spec doesn't prescribe whether to surface a warning to the caller or silently degrade.