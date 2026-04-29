---
{
  "title": "Org Journal — Append-Only Event Log with Actor Attribution, Scoped Writes, and Root Protection",
  "summary": "The org journal is the immutable, UTC-stamped, scope-tagged event store that serves as a single source of truth for all mutations in an org instance. `EventEntry`, `Actor`, and `DataRef` are the core spec models; `check_root_undeletable` is an advisory safeguard that prevents any journal event from retiring or deleting the org's root soul.",
  "concepts": [
    "EventEntry",
    "Actor",
    "DataRef",
    "journal",
    "append-only log",
    "scope",
    "ACTION_NAMESPACES",
    "check_root_undeletable",
    "RootProtectedError",
    "Zero-Copy",
    "UTC enforcement",
    "seq",
    "causation_id",
    "correlation_id",
    "org journal"
  ],
  "categories": [
    "journal",
    "event sourcing",
    "spec layer",
    "audit log",
    "governance"
  ],
  "source_docs": [
    "15108464cb696504"
  ],
  "backlinks": null,
  "word_count": 553,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

An org's journal is its audit log, its event sourcing backbone, and its compliance record simultaneously. Every mutation — spawning an agent, storing a memory, ingesting a knowledge base source, rotating a key — produces an `EventEntry`. Because the journal is append-only, the full history is always recoverable. Corrections are new events that reference the original via `causation_id`.

This module ships only the spec models. The SQLite WAL engine and the `soul org init` CLI land in separate modules.

## Core Models

### `Actor`

```python
class Actor(BaseModel):
    kind: Literal["agent", "user", "system", "root"]
    id: str  # min_length=1
    scope_context: list[str]
```

There are no anonymous writes. Every event carries an actor. `scope_context` is recorded at write time so that if an actor's scopes change later, the historical record is not rewritten. `system:*` actors (e.g., `system:kb-go`, `system:graduation`) are reserved for subsystem-triggered events.

### `DataRef`

Used when the event payload points to data that lives outside the journal (Salesforce records, Google Drive files, Snowflake tables). The journal records the query recipe and a `point_in_time` UTC timestamp; the actual data stays in the source system. This is the "Zero-Copy" pattern — the org boundary never ingests the raw data unless explicitly resolved.

A critical defensive pattern here is the `__dataref__` discriminator:

```python
_DATAREF_MARKER = "__dataref__"
```

Without this marker, Pydantic's `DataRef | dict` union on `EventEntry.payload` would silently coerce any dict that happens to have `source`, `query`, and `point_in_time` keys into a `DataRef` on deserialization. The marker is stamped on every JSON serialization of `DataRef` and stripped before field validation — making the round-trip unambiguous.

### `EventEntry`

```python
class EventEntry(BaseModel):
    id: UUID
    ts: datetime       # must be timezone-aware UTC
    actor: Actor
    action: str        # dot-separated, e.g. "memory.remembered"
    scope: list[str]   # non-empty, required
    payload: dict | DataRef
    seq: int | None    # assigned by backend at commit
```

- **UTC enforcement**: `ts` raises at validation time if naive. This fixes naive-datetime bugs at the journal layer rather than per-subsystem.
- **Non-empty scope**: every write must declare a scope. Unscoped writes are rejected. This enforces RBAC/ABAC from the start.
- **`seq`**: `None` until committed. The backend assigns a monotonic sequence number on `Journal.append()`, which returns the committed entry so callers don't need to race `MAX(seq)`.

### `ACTION_NAMESPACES`

A tuple of ~40 predefined action strings (not an enum). Callers can add new action names additively without a library upgrade. Removing an action is a schema migration. This keeps the journal extensible while still providing a discoverable catalog.

## Root Protection

```python
def check_root_undeletable(entry: EventEntry, root_did: str) -> None:
    ...
    if root_did in {entry.actor.id, payload.get("target_did"), ...}:
        raise RootProtectedError(...)
```

The org's root soul (the founding identity, root-signed governance events) cannot be retired or deleted via journal events. The only legitimate removal path is `soul org destroy`, which writes a single `org.destroyed` event and archives the org directory. This advisory check is called by projections, replayers, and the CLI — it prevents accidental soft-deletion of the root that would make the org unrecoverable from the journal alone.

## Known Gaps

- `prev_hash` and `sig` (hash-chain link and signature fields) are present but optional. The comment notes signing ships in a follow-up PR — until then, the chain is not cryptographically verified.
- The SQLite WAL engine and `soul org init` CLI are referenced but live in separate modules not yet landed.