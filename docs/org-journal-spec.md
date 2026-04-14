<!--
org-journal-spec.md — Framework-agnostic protocol spec for Soul Protocol's
org layer. Introduces the Universal Journal, Root Agent concept, soul
hierarchy, RetrievalRouter + CredentialBroker contracts, and DataRef
zero-copy payload variant. Consumers integrate via the Journal/Router
APIs; runtime choices (CLI, storage paths, UI) are implementation
concerns, not protocol concerns.
-->

# Org Journal Spec

> **The Universal Journal, the Root Agent, and Zero-Copy Retrieval**

**Status:** DRAFT — RFC for review
**Updated:** 2026-04-13
**Related:** DSP-MEMORY-ARCHITECTURE (per-soul), architecture.md (implementation)

---

## Abstract

Soul Protocol's v0.2 model is per-soul: one `.soul` file holds identity, OCEAN, and tiered memory for a single agent or user. That model stays. This document specifies an **org layer** above it — a boundary holding multiple souls (root, users, agents), a shared append-only event journal, scope-based access control, and a credential broker for federated external sources.

The org layer is framework-agnostic. Any agent runtime can adopt it by implementing the Journal / Router contracts documented here. It is not tied to any specific implementation, CLI, or storage convention.

---

## Motivation

An org-scoped agent system needs to answer four questions:

1. **What is the source of truth?** If multiple subsystems (memory, knowledge base, object stores, retrieval logs) each hold their own state, they drift. Timestamps diverge, audit rules diverge, scope enforcement diverges.
2. **Who can sign what?** Governance events (creating scopes, promoting admins, rotating keys) need a root of trust that survives every downstream churn.
3. **Can retrieval reach live data without copying it?** External systems (CRM, file drives, warehouses) hold org-critical data. ETL pipelines duplicate it (stale, PII-leaky); live federation preserves it (latency-sensitive, auth-heavy).
4. **How do we compound human feedback?** Every correction a human makes to an agent's proposal is a pattern candidate. Without a structured place to record them, the signal is lost.

The org layer proposes one shape that answers all four: **a single append-only event journal as source of truth, a Root Agent as signing root, a `DataRef` payload variant for federated queries, and a proposal-correction event pair as the decision-trace primitive.**

---

## The Org Journal

### Shape

An append-only, UTC-stamped, scope-tagged sequence of events. Every action — retrieval, ingestion, decision, graduation, admin change, agent spawn — writes one `EventEntry`. Nothing else is source-of-truth; everything else is a projection.

```python
from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel

class Actor(BaseModel):
    kind: Literal["agent", "user", "system", "root"]
    id: str                       # stable identifier (did:soul:..., user:alice, system:kb)
    scope_context: list[str]      # scopes the actor held when acting

class DataRef(BaseModel):
    source: str                   # source identifier registered with the retrieval router
    query: str                    # source-native query recipe
    point_in_time: datetime       # tz-aware UTC
    cache_policy: Literal["always", "invalidate_on_event", "ttl"] = "ttl"
    cache_ttl_s: int | None = None

class EventEntry(BaseModel):
    id: UUID
    ts: datetime                  # tz-aware UTC, monotonic per journal
    actor: Actor
    action: str                   # dot-separated verb namespace (e.g., "retrieval.query")
    scope: list[str]              # scope tags, non-empty
    causation_id: UUID | None     # prior event that caused this one
    correlation_id: UUID | None   # session or flow this event is part of
    payload: dict | DataRef       # inline data or external reference
    prev_hash: bytes | None       # optional hash-chain link
    sig: bytes | None             # optional signature over (id, ts, actor, action, prev_hash)
```

### Invariants (enforced at `Journal.append()`)

1. **Append-only.** No `UPDATE`, no `DELETE` on events. Corrections are new events with `causation_id`.
2. **UTC everywhere.** `datetime.now(UTC)`. Naive datetimes rejected.
3. **Monotonic timestamps.** `ts` must be >= previous event's `ts`.
4. **Scoped by default.** `scope` is required and non-empty. No anonymous writes either — `actor` must be set.
5. **Hash-chainable.** `prev_hash` is optional in v1, mandatory in v2 once signing ships.
6. **Actor-attributed.** `system:*` actors are reserved for subsystem-triggered events (not human-runnable).

### What the journal is not

- Not a message bus. Events are facts that happened. Subscription / delivery is a separate layer.
- Not a blob store. Payloads stay small (recommend 64KB cap); large content goes to blob storage referenced by `DataRef`.
- Not the only query surface. Projections remain primary read paths; the journal is the source and audit trail.

### Action namespace catalog (initial)

Dot-separated, past-tense verbs. Additive — new actions can be shipped without breaking existing consumers.

```
# Governance (root-signed)
org.created, org.destroyed, schema.migrated,
user.admin_granted, user.admin_revoked,
scope.created, key.rotated

# Identity
agent.spawned, agent.retired,
user.joined, user.left,
team.created, team.disbanded,
soul.exported, soul.imported

# Memory & Knowledge
memory.remembered, memory.graduated, memory.forgotten,
kb.source.ingested, kb.article.compiled, kb.article.revised

# Retrieval & scope
retrieval.query,
scope.assigned, scope.revoked

# Decisions
agent.proposed, human.corrected, decision.graduated

# Credentials & Zero-Copy
credential.acquired, credential.used, credential.expired,
dataref.resolved

# Graduation & Policy
graduation.applied, policy.evaluated
```

Implementations may extend this catalog with runtime-specific namespaces. The catalog is a tuple, not a closed enum; unregistered actions are allowed but should be documented. Runtime-specific concepts do not belong in the base catalog: for example, a pocket runtime with a scoped object store might emit `fabric.object.created`, but that namespace is the runtime's to define, not the protocol's.

---

## The Root Agent

### What it is

One per org. Created during org bootstrap. Cannot be deleted. Signs every event that mutates governance state. Analogous to the `root` user on unix or the superuser in a database: minimal surface, maximal trust.

### What it owns

- **The journal.** Every event chains (optionally via `prev_hash`) to a `genesis` event signed by root's first keypair.
- **The scope tree root.** The top-level scope (by convention `org:*`) is reserved. All downstream scopes are children created by `scope.created` events root signs.
- **The DID chain.** Every other agent or user DID is countersigned by root at creation time.
- **Schema migrations.** Structural journal or soul-format changes ship as `schema.migrated` events signed by root.
- **Admin invariants.** Events for which root is the only acceptable signer:
  - `org.created` (exactly one per instance — the genesis event)
  - `user.admin_granted` / `user.admin_revoked`
  - Top-level `scope.created`
  - `key.rotated` for root's own keys (requires m-of-n co-signing — see Security)
  - `schema.migrated`
  - `org.destroyed` (terminal)

### What it does not do

- **No conversational surface.** Root is never reachable by human chat, DM, email, or any channel adapter. Only via structured admin interfaces and signed programmatic calls.
- **No free-text CLI input.** Admin interfaces accept structured inputs only — UUIDs, enum values, integer flags, file paths validated against a fixed schema. No free-text argument is passed to an LLM as part of any root-signed operation. Human-readable output is rendered from structured journal data, not generated by an LLM prompted with arbitrary input. This closes the admin surface as an implicit prompt-injection vector.
- **No day-to-day workflow involvement.** Routine agent work happens through user-spawned agents. Root signs the *spawn* event, then stays out.
- **No memory tier writes.** Root does not accumulate episodic memory; its "memory" is the journal itself.

### Undeletability — three layers

1. **Storage layer.** The root soul file (or row, depending on implementation) refuses deletion via the normal delete API. `Soul.delete()` raises when `role == "root"`.
2. **Protocol layer.** No `agent.retired` or `soul.deleted` event accepts an actor whose id matches the root DID. A helper `check_root_undeletable(event, root_did)` is provided for advisory use by projections and external tooling.
3. **Interface layer.** Admin CLIs, APIs, or UIs must refuse deletion paths on role=root. The only acceptable terminal action is an explicit `org.destroyed` event that wipes the whole instance.

The moment root is deletable, every signature-chain guarantee collapses. "Who signed this audit event?" must remain answerable for the life of the org.

### Governance persona

Root's persona is minimal and strictly for its governance voice (audit summaries, signed event attestations). Low openness, high conscientiousness, audit-oriented values. No OCEAN personality drift over time. This is identity, not character.

---

## Soul Hierarchy

Five conceptual tiers. Implementations may use fewer if the runtime is simpler.

| Tier | Scope root | Portable? | Count | Role |
|---|---|---|---|---|
| **Root / Org** | `org:*` | No — tied to instance | 1 | Governance identity, signs journal mutations |
| **Team** (optional) | `org:<team>:*` | No | 0–N | Shared team persona, policy defaults |
| **User** | `org:user:<name>:*` | Yes — travels with the human | 1 per human | Personal identity + OCEAN + preferences only. Org-activity episodic memory stays in the journal (org-bound). |
| **Agent** | `org:agent:<id>:*` | Yes — exportable | 0–N | Per-agent persona, skills, memory scope |
| **Pocket** | `org:pocket:<id>` — scope only | N/A — not a soul | 0–N | Workspace scope node + journal slice. Agents and humans collaborate within; identity does not live here. |

### Critical distinction: pockets are not souls

A pocket is the **collaboration surface** where agents and humans work together on org activity — a deal, a case, a project. It is a scope tree node, a filtered view over the journal, and (in runtimes that render UI) the container for widgets and activity. It is not a separate identity.

Agents work inside pockets; humans collaborate alongside them; events from both sides land in the journal scoped to the pocket. Giving every pocket its own soul is the "new space for every project" anti-pattern — identity sprawl, confused ownership, no audit locus.

### What "portable" means for user souls

User souls carry *who you are*, not *what the org has recorded about your activity*. When a user moves to a new machine or a new org, their soul brings identity, OCEAN personality, and personal preferences. Episodic memory of specific work — decisions corrected, tickets resolved, deals touched — lives in the org journal and stays with the org. This is deliberate: org-activity memory is subject to org retention policy, legal hold, and access control that individuals cannot unilaterally export.

For solo single-user deployments where the org = the user, both files travel together in practice but the protocol semantics are still clean.

---

## Retrieval: Router + Broker + DataRef

### RetrievalRouter

Dispatches queries across candidate sources. Each source is either a local **projection** (materialized view over the journal — memory, knowledge base articles, scoped object stores) or a **DataRef** source (live external system, queried at retrieval time).

```python
router.register_source(
    CandidateSource(name="memory", kind="projection", scopes=["org:*"], adapter_ref="..."),
    ProjectionAdapter(callback=memory_recall_fn),
)
router.register_source(
    CandidateSource(name="drive", kind="dataref", scopes=["org:sales:*"], adapter_ref="..."),
    DriveAdapter(...),  # implementation-specific
)

result = router.dispatch(RetrievalRequest(
    query="Q3 pipeline forecasts",
    actor=actor,
    scopes=["org:sales:*"],
    strategy="parallel",
    timeout_s=10.0,
))
```

Strategies: `first` (stop at first non-empty), `parallel` (thread-pool, merge by score), `sequential` (walk in order, accumulate up to `limit`).

**Scope enforcement:** sources whose registered `scopes` don't overlap the request `scopes` are filtered out before dispatch. Scope match is bidirectional.

**Journal emission:** if a journal is passed to the router, each dispatch emits a `retrieval.query` event. Payload is either inline (projection source) or `DataRef` (federated source). This is the audit trail for every retrieval.

### CredentialBroker

Safe credential delegation for federated sources.

```python
credential = broker.acquire(source="drive", scopes=["org:sales:*"])
broker.ensure_usable(credential, requester_scopes=["org:sales:leads"])
result = adapter.query(request, credential)
broker.mark_used(credential)
```

Rules:

1. **Short-lived tokens only.** Default TTL 300s; callers opt into longer.
2. **Per-scope scoping.** A credential acquired for `org:sales:*` raises `CredentialScopeError` if used by a requester in `org:support:*`.
3. **Full lifecycle audit.** Every acquire / use / expire emits a corresponding journal event (`credential.acquired`, `credential.used`, `credential.expired`).
4. **Token contents are opaque.** The `Credential.token` field carries an implementation-opaque string. Consumers don't introspect; adapters pass through.

### DataRef — the Zero-Copy payload variant

```python
EventEntry(
    action="retrieval.query",
    actor=agent_actor,
    scope=["org:sales:*"],
    payload=DataRef(
        source="salesforce",
        query="SELECT Id, Stage, Amount FROM Opportunity WHERE AccountId='001abc'",
        point_in_time=datetime(2026, 4, 13, 14, 30, tzinfo=UTC),
        cache_policy="invalidate_on_event",
    ),
    ...
)
```

At retrieval, the router dispatches the `DataRef` to the registered source adapter using a broker-issued credential. The journal records the reference, not the data — enabling always-current reads against live systems without ETL duplication.

**Tradeoffs:**

| Concern | Static copy-on-ingest | DataRef Zero-Copy | Mitigation |
|---|---|---|---|
| Latency | 10ms local | 100ms–1s remote | Per-query cache keyed by `(source, query, point_in_time)` |
| Staleness | ETL lag (minutes to hours) | None (always live) | — |
| Credentials | One-time at ingest | Every retrieval | Broker holds short-lived tokens only |
| Offline | Data local, always available | Source down = retrieval fails | Stale-while-revalidate with `cache_policy="ttl"` |
| API quota | None at query time | Counts against source | Query coalescing at the router |
| PII | Duplicated to local storage | Stays at source | — |
| Point-in-time correctness | N/A | Requires source support | Where absent, record "best-effort at T" transparently |

**Not a replacement for copy-on-ingest.** Static sources (handbook PDFs, onboarding guides) still copy because copying is cheap, queries are frequent, and point-in-time doesn't matter. DataRef is for live systems where freshness and data-residency matter more than retrieval latency.

### Replay semantics

`Journal.replay_from(seq)` is the mechanism projections use to rebuild:

- **Hermetic** for every action except `retrieval.query` with a `DataRef` payload. Rebuild is deterministic from the journal file alone.
- **Non-hermetic (bounded)** for `retrieval.query` events carrying DataRef payloads. Replay against a down / rate-limited / schema-changed source produces different results or fails. This is acknowledged, not a bug — DataRef events are receipts of live queries, not reproducible facts.

Projections that consume DataRef events must declare themselves DataRef-aware. Consumers that aren't DataRef-aware subscribe only to the structured metadata (actor, ts, scope, causation_id) and ignore the payload.

**Optional escape hatch:** implementations may offer a snapshot-on-write mode where the engine resolves DataRef inline at write time and caches the snapshot alongside the reference. Useful for audit-heavy deployments. Costs: defeats some Zero-Copy value and inflates storage. Not the default.

---

## Decision Traces

### The loop

```
agent.proposed           human.corrected              decision.graduated
(proposal payload)  -->  (causation_id = ^)    -->    (supporting_correction_ids = [...])
```

An agent proposes an action. A human edits, accepts, rejects, or defers it. A correction is recorded with `causation_id` pointing to the proposal. Over N similar corrections with matching `structured_reason_tags`, the pattern graduates from episodic to semantic memory.

### Payload types

```python
class AgentProposal(BaseModel):
    proposal_kind: str              # "tool_call" | "message_draft" | "decision" | "custom:<ns>"
    summary: str                    # human-readable summary
    proposal: dict                  # structured payload
    confidence: float | None
    alternatives: list[dict]
    context_refs: list[UUID]        # prior event IDs the agent consulted

class HumanCorrection(BaseModel):
    disposition: Literal["accepted", "edited", "rejected", "deferred"]
    corrected_value: dict | None
    correction_reason: str | None
    structured_reason_tags: list[str]   # for clustering
    edit_distance: float | None

class DecisionGraduation(BaseModel):
    pattern_summary: str
    supporting_correction_ids: list[UUID]
    graduated_to_tier: Literal["semantic", "core"]
    confidence: float
    applies_to: dict
```

### Why this matters

Agents that improve over time are the point of the protocol. The decision-trace pattern gives runtimes a structured, auditable, org-scoped place to capture the signal humans generate when they edit agent output. Over time, clustering on `structured_reason_tags` surfaces patterns; graduation promotes them into the agent's persistent memory. Signal that today is lost becomes tomorrow's training data — but org-owned, not aggregated into someone else's dataset.

---

## Storage

### Tiers

| Tier | Backend | When | Capacity |
|------|---------|------|----------|
| Default | SQLite WAL, single file | Always — zero-ops default | ~100GB |
| Cold | Parquet partitions + columnar query layer | Events older than N months | TB-scale |
| Multi-node | Postgres (or equivalent) | Horizontal scale opt-in | Unbounded |

The `JournalBackend` protocol is designed so that switching backends is a configuration change, not an API break. Default implementations should favor the zero-ops option (SQLite) to keep self-host viable.

### Portability

`.soul` files remain the portable identity capsule. The journal is org-bound and lives alongside soul files in an implementation-defined directory. Orgs export their state as a bundle of soul files + journal + key material; importing on a new host preserves DID lineage.

---

## Security

### Signing

- Governance events (onboarding, admin changes, scope mutations, schema migrations) are signed by root's current keypair.
- Day-to-day events (retrievals, memory writes, kb ingests) are signed by the originating agent's keypair.
- Signatures are optional in v1 (`sig` field nullable), mandatory for governance events from v1.1, mandatory for all events from v2.

### Key rotation

`key.rotated` is the only event root itself does not sign. Rotation requires m-of-n signatures from existing admin users (default: 2 of 3). Old keys marked revoked; new keys sign going forward. Past events stay signed by old keys and remain valid — the chain is append-only. Verifiers follow `key.rotated` events to know which key was active at each `ts`.

### Credential broker threat model

The broker holds short-lived tokens only; long-lived secrets never leave secure storage. Per-scope scoping prevents lateral credential use. Every token fetch is a journal event, so credential misuse is auditable after the fact. Prompt injection via external data is mitigated at the retrieval router before data reaches any agent — this is where a runtime's output filter lives.

### Journal tamper-evidence

Hash-chain + signing enables detection of undetected modification. Projections verify the chain at startup and on every admin read. Compromise of root keys is survivable via m-of-n rotation; compromise of the journal file itself is detected by hash mismatch on next verification.

---

## Open Questions

1. **Hash-chain v1 or v2?** Optional in v1 keeps the model simpler. Mandatory in v1 enforces tamper-evidence from day one but adds verification overhead. Lean: optional-v1 with strong-by-default config.
2. **Clock skew on multi-writer setups.** Hybrid logical clocks add complexity. Single-writer-per-org is the default; HLCs deferred to v2.
3. **Event payload size limit.** Suggest 64KB cap with DataRef for anything larger.
4. **Pocket-as-scope formalization.** Runtimes that previously treated pockets as first-class objects need a deprecation path. Proposed: emit a `pocket.created` scope event mapping old pocket IDs to new scope names.
5. **Multi-admin quorum default.** 2-of-3 feels right for typical orgs. Solo deployments (1-of-1) need a migration path to m-of-n when a second admin lands.
6. **Cross-org references.** If agent A in Org X talks to agent B in Org Y, does the event land in both journals? In one with a reference? This is federation; deserves its own RFC.
7. **Naming.** "Root agent" is clear but generic. Implementations may pick instance-specific names for their governance identity.
8. **Query API surface for consumers.** The engine exposes `append / query / replay_from`. Specific runtime APIs (FastAPI, JSON-RPC, GraphQL) are implementation concerns — this spec does not mandate one.
9. **DataRef snapshot-on-write escape hatch.** Opt-in mode where DataRef resolves inline at write time. Ship non-hermetic default first; add snapshot mode when customers ask.

---

## Conformance Notes for Implementers

A runtime conforms to this spec if it:

1. Implements `EventEntry` with the fields specified, enforcing the stated invariants at write time.
2. Provides an append-only journal with `append / query / replay_from` operations.
3. Enforces the Root Agent's undeletability across all layers it controls.
4. Implements scope-based access control using the grammar documented in the existing Soul Protocol scope spec.
5. If federating external sources, implements a retrieval router that dispatches `DataRef` payloads to registered adapters through a credential broker with per-scope scoping.
6. If capturing human feedback on agent proposals, emits `agent.proposed` / `human.corrected` event pairs with `causation_id` linkage.

Runtimes may add implementation-specific action namespaces, storage backends, CLI tools, and UI surfaces. These are not protocol concerns.

---

*This specification is framework-agnostic. It defines the contracts; runtimes choose the implementations. For a specific runtime's integration plan, see the runtime's own migration documentation.*
