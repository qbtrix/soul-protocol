<!--
DSP-ORG-ARCHITECTURE.md — Initial draft.
Introduces four connected primitives for Paw OS org-level architecture:
  1. The Org Journal (event-sourced source of truth)
  2. The Root Agent (undeletable governance identity)
  3. The Soul Hierarchy (root / team / user / agent + pocket scopes)
  4. Zero-Copy DataRef (federate queries instead of copying data)
Companion RFC to DSP-MEMORY-ARCHITECTURE.md. Status: DRAFT.
-->

# DSP Org Architecture

> **The Universal Journal, the Root Agent, and Zero-Copy Retrieval**

**Status:** DRAFT — RFC for review
**Updated:** 2026-04-13
**Supersedes (partially):** ad-hoc retrieval-log + per-subsystem audit trails
**Related:** DSP-MEMORY-ARCHITECTURE, DSP-IMPLEMENTATION-SPEC, PAW-SPEC

---

## Executive Summary

Paw OS today has four write paths — soul memories, kb-go wiki, Fabric scoped objects, and the retrieval log — each with its own timestamp format, audit rules, and failure modes. The drift is already visible: today's 17-PR review surfaced four separate `datetime.now()` timezone bugs, two missing audit events, and the same scope-normaliser bug shipped in three places. That's the SAP FI/CO reconciliation problem accumulating in real time, four years into what should be a green-field architecture.

This document proposes the org-level architectural shift that fixes it: **one append-only event journal as the source of truth, with the soul, kb-go, and Fabric repositioned as projections over that journal.** On top of the journal sits a **Root Agent** — an undeletable governance identity that owns the journal, the scope tree, and the DID chain. Zero-Copy data federation becomes a payload variant rather than a separate subsystem. The existing `.soul` format stays portable and unchanged for day-to-day agents; it picks up a new role for the root as the signing root of the org.

The three priority actions in the current gaps analysis (Single Brain, Zero-Copy, Vertical Templates) collapse into one structural move. This RFC scopes that move.

---

## Motivation

### Problem 1: Multiple write paths produce silent drift

The 17 PRs shipped in the Moves 0-8 marathon each introduced or extended a write path. None were wrong in isolation. Taken together:

| Subsystem | Timestamp field | Audit? | Scope-aware? |
|---|---|---|---|
| Soul memory tiers | `created_at` (ISO) | Implicit | Via soul-protocol #162 (spec only) |
| kb-go wiki | `ingested_at` (ISO) | None | No |
| Fabric objects (#938) | `created_at` (ISO) | No (blocker flagged) | Yes |
| Retrieval log (#936) | `ingested_at` (naive — bug) | None | Partial |
| Graduation apply (#937) | implicit | No (blocker flagged) | No |

Same conceptual field implemented five ways. The cost is already concrete: three of today's ten blockers are drift artifacts across these surfaces, not logic bugs within any one of them.

### Problem 2: The moat named in the gaps doc isn't built

The strategic brief names four compounding data types as Paw's structural advantage over SAP and Salesforce:

1. Knowledge (kb-go) — built
2. Decisions (human corrections of agent proposals) — **not built**
3. Patterns (graduation across memory tiers) — built for UI (#941), not decisions
4. Preferences (soul OCEAN) — built

Decision traces are the moat. They don't exist because there's no unified place to write them. `RetrievalTrace` (#161) is a read-side receipt. There's no write-side "agent proposed X, human changed it to Y" pipeline because any such pipeline would have to choose between soul / kb-go / Fabric / retrieval-log to live in — and the answer is none of them.

### Problem 3: The Zero-Copy thesis isn't architecturally possible yet

The gaps doc lists Zero-Copy as Priority Action 2, framed as "extend IngestAdapter." But IngestAdapter (#939) is a copy-on-ingest primitive with source-side ACL. Real Zero-Copy means *federating* a query to Salesforce or Drive or Snowflake at retrieval time, not copying. The missing piece isn't more IngestAdapter surface — it's a retrieval primitive that accepts a *reference* instead of a payload. Today there's no place in the data model for a reference to live.

### What the architecture wants to be

All three problems resolve to the same shape: **one append-only journal that every subsystem writes to, with current stores becoming projections.** This is the Universal Journal pattern SAP reached after 40 years of reconciliation pain. The difference is we get to start there.

---

## The Org Journal

### Shape

An append-only, UTC-stamped, scope-tagged sequence of events. Every action — retrieval, ingestion, decision, graduation, admin change, agent spawn — writes one `EventEntry`. Nothing else is source-of-truth.

```python
from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel

class Actor(BaseModel):
    kind: Literal["agent", "user", "system", "root"]
    id: str                       # stable identifier (did:soul:..., user:alice, system:kb-go)
    scope_context: list[str]      # scopes the actor held when acting

class DataRef(BaseModel):
    source: str                   # "salesforce" | "gdrive" | "snowflake" | "s3" | ...
    query: str                    # source-native query recipe
    point_in_time: datetime       # tz-aware UTC
    cache_policy: Literal["always", "invalidate_on_event", "ttl"] = "ttl"
    cache_ttl_s: int | None = None

class EventEntry(BaseModel):
    id: UUID
    ts: datetime                  # tz-aware UTC, monotonic per journal
    actor: Actor
    action: str                   # structured verb, dot-separated namespace
    scope: list[str]              # scope tags from DSP scope grammar (#162)
    causation_id: UUID | None     # which prior event caused this one
    correlation_id: UUID | None   # session / flow this event is part of
    payload: dict | DataRef       # inline data or external reference
    prev_hash: bytes | None       # optional hash-chain to previous event
    sig: bytes | None             # optional signature over (id, ts, actor, action, prev_hash)
```

### What writes to it

Today's primitives all become `action` namespaces under the journal:

| Current primitive | Journal `action` |
|---|---|
| RetrievalTrace (#161) | `retrieval.query` |
| Retrieval log (#936) | `retrieval.query` (same event; log is a filter over journal) |
| Graduation apply (#937) | `graduation.applied` |
| Fabric object write (#938) | `fabric.object.created` / `fabric.object.updated` |
| Scope assignment (#162) | `scope.assigned` / `scope.revoked` |
| Soul memory write | `memory.remembered` / `memory.graduated` |
| kb-go ingest | `kb.source.ingested` / `kb.article.compiled` |
| Agent proposal | `agent.proposed` |
| Human correction | `human.corrected` — with `causation_id` = the agent proposal |
| Admin changes | `user.admin_granted` / `key.rotated` / `scope.created` |
| Onboarding bootstrap | `org.created` (genesis) / `agent.spawned` |

### Invariants

1. **Append-only.** No `UPDATE`, no `DELETE` on the `events` table. Corrections are new events with `causation_id`.
2. **Monotonic timestamps.** `ts` must be ≥ previous event's `ts`. Clock skew on multi-writer setups resolved via hybrid logical clocks (Phase 2).
3. **UTC everywhere.** `datetime.now(UTC)` is the only acceptable source. All current naive-datetime bugs get fixed at the journal layer, not per-subsystem.
4. **Scoped by default.** Every event carries `scope`. Unscoped events raise at write time — there is no "global" write path.
5. **Hash-chainable.** `prev_hash` is optional in v1, required in v2 once we ship signing. Enables tamper-evident audit.
6. **Actor-attributed.** No anonymous writes. `system:*` actors are reserved for subsystem-triggered events (kb compile cascades, graduation scheduler).

### What the journal is not

- **Not a message bus.** Events are facts that happened. Delivery to subscribers (agents reacting to events) is a separate layer.
- **Not a storage engine for large blobs.** Payloads should stay small; binary content goes to blob storage and the journal holds a `DataRef`.
- **Not the only query surface.** Projections (soul, kb, fabric, retrieval log) remain the *primary* read paths. The journal is the source; projections are the indexes.

---

## The Root Agent

### What it is

One per Paw OS instance. Created during onboarding. Cannot be deleted. Signs every event that mutates governance state. Analogous to `root` on unix or the superuser in Postgres: minimal surface, maximal trust.

### What it owns

- **The journal** — every event chains (optionally) to a `genesis` event signed by root's first keypair.
- **The scope tree root** — `org:*` is reserved. All downstream scopes are children created by `scope.created` events that root signs.
- **The DID chain** — every other agent/user DID is countersigned by root at creation time.
- **Schema migrations** — structural changes to the journal or soul format ship as `schema.migrated` events signed by root.
- **Admin invariants** — a short list of events root is the only acceptable signer for:
  - `org.created` (exactly one per instance — the genesis event)
  - `user.admin_granted` / `user.admin_revoked`
  - `scope.created` at the top level
  - `key.rotated` for root's own keys (requires m-of-n co-signing — see Security)
  - `schema.migrated`
  - `paw.os.destroyed` (terminal)

### What it does not do

- **No conversational surface.** Root is never reachable by human chat, Slack DM, email, or any channel adapter. Only via admin CLI and signed programmatic calls. This is a security posture: if root can be talked to, it can be prompt-injected, and if it can be prompt-injected it can be coerced into signing malicious governance events.
- **No free-text input to the CLI.** Root's admin CLI accepts structured inputs only — UUIDs, enum values, integer flags, file paths validated against a fixed schema. No free-text argument is passed to an LLM as part of any root-signed operation. Human-readable output (audit summaries, CLI responses) is rendered from structured journal data, not generated by an LLM prompted with arbitrary input. This closes the CLI as an implicit prompt-injection vector.
- **No day-to-day workflow involvement.** Routine agent work — answering tickets, drafting emails, running sales cadences — happens through user-spawned agents. Root signs the *spawn* event, then stays out of the loop.
- **No memory tier writes.** Root does not accumulate episodic memory. Its "memory" is the journal itself — it knows everything the org has ever recorded, by construction.

### Persona

Root has a minimal persona for its governance voice (audit messages, admin CLI responses, signed event summaries): the `governance` archetype — an addition to the soul templates shipped in #163. Values tilt toward audit, caution, durability. No OCEAN personality drift over time. This is identity, not character.

### Undeletability — three layers

1. **DB constraint.** `DELETE FROM agents WHERE role='root'` fires a trigger that raises. Same for the `org.created` genesis event in the journal.
2. **Protocol.** No `agent.deleted` event type accepts `role='root'`. The only event that ends a root's lifetime is `paw.os.destroyed`, which is terminal — it marks the journal read-only forever.
3. **CLI.** `soul delete` refuses with role=root. `paw os destroy` exists but requires `--confirm --i-mean-it`, prints a summary of what will be lost, and creates a tarball of the current state before wiping.

This matters because the moment root is deletable, every signature-chain guarantee collapses. "Who signed this audit event?" must remain answerable for the life of the org.

---

## The Soul Hierarchy

Five tiers, each with a distinct role. Not every org uses all of them.

| Tier | Scope root | Portable? | Count per org | Role |
|---|---|---|---|---|
| **Root / Org** | `org:*` | No — tied to instance | 1 | Governance identity, signs journal mutations |
| **Team** (optional) | `org:<team>:*` | No | 0–N | Shared team persona, policy defaults |
| **User** | `org:user:<name>:*` | Yes — travels with the human | 1 per human | Personal identity + OCEAN + preferences only. Org-activity episodic memory stays in the journal (org-bound) |
| **Agent** | `org:agent:<id>:*` | Yes — exportable | 0–N | Per-agent persona, skills, memory scope |
| **Pocket** | `org:pocket:<id>` — scope only | N/A — not a soul | 0–N | Workspace scope node, not an identity |

### What "portable" means for user souls

User souls carry *who you are*, not *what the org has recorded about your activity*. When a user travels to a new machine or a new org, their soul brings identity, OCEAN personality, and personal preferences. Episodic memory of specific work — deals touched, tickets resolved, decisions corrected — lives in the org journal and stays with the org. This is deliberate: org-activity memory is subject to org retention policy, legal hold, and access control that individuals cannot unilaterally export. The soul file remains a small, signed identity capsule; the journal is the heavy, org-bound event record.

For solo founders or single-user deployments where the org = the user, the practical result is the same (both files travel together) but the protocol semantics are still clean.

### Critical distinction: pockets are not souls

A pocket is the **collaboration surface** where agents and humans work together on a piece of org activity — a deal, a support case, a project, a customer account. It's a scope node in the tree, a filtered view over the journal, and the UI container that renders widgets and activity for both agents and people. It is not a separate identity.

Agents work inside pockets; humans collaborate alongside them; events from both sides land in the journal scoped to the pocket. Giving every pocket its own soul is the Confluence "a new space for every project" anti-pattern — identity sprawl, confused ownership, no audit locus. Pockets scope memory and activity; agents and users hold identity.

### Storage layout

```
~/.pocketpaw/
├── org/
│   ├── root.soul               # undeletable root agent soul (zip)
│   ├── journal.db              # SQLite WAL, append-only, org truth
│   ├── journal_archive/        # cold Parquet partitions (monthly, by scope)
│   └── keys/                   # root DID signing keys, hardware-backed when possible
├── teams/
│   └── sales.soul              # optional team souls
├── agents/
│   ├── sales-lead.soul
│   └── support-triage.soul
├── users/
│   └── prakash.soul            # travels with user across devices
└── config.toml
```

The `.soul` zip format is unchanged. Each soul file references the journal by org DID; the journal lives once at org level.

---

## Onboarding — first-run wizard

First time someone runs Paw OS, they bootstrap an org. Eight steps, target time under five minutes:

1. **Org identity.** Name, one-sentence purpose, 3-5 values (feeds root soul's OCEAN and mission statement).
2. **Founder user.** Creates first user soul in `users/`, marked `admin`.
3. **Root agent.** Pick an archetype (default: `governance` from the extended #163 template set), name it (org choice — "Nerve", "Kernel", "Ops", whatever).
4. **Key generation.** Prompt for hardware-backed key if available (Secure Enclave on macOS, TPM on Windows/Linux). Fallback: filesystem keys with 0600 ACL. Never prompt-less.
5. **Journal init.** Write `journal.db`, append `org.created` genesis event signed by root. Event #1 is the root of trust forever.
6. **Scope bootstrap.** Emit `scope.created` for `org:*` and any first-level scopes the archetype suggests (`org:sales`, `org:ops`, `org:me`).
7. **Starter fleet.** From #940 fleet bundles — Sales Fleet / Support Fleet / Solo Founder / Custom / Skip. Each fleet install is N × `agent.spawned` events signed by root.
8. **Invites.** Generate invite links that bootstrap user souls on coworkers' machines. Their souls travel; the journal stays org-side.

Final state: running Paw OS, one root agent, one admin user, 0–N spawned agents, genesis journal with 10–20 initial events, a scope tree ready to grow.

---

## Zero-Copy via `DataRef`

### Motivation

Today's IngestAdapter (#939) copies data from external sources into kb-go / soul / Fabric. For static documents this is fine. For live systems — CRM, data warehouses, inboxes — copying creates staleness, duplicates PII across boundaries, and forces every customer through an ETL pipeline before they see value. That's the onboarding bottleneck the gaps doc names.

Zero-Copy records the *reference*, not the data:

```python
EventEntry(
    action="retrieval.query",
    actor=Actor(kind="agent", id="did:soul:sales-lead"),
    scope=["org:sales:*"],
    payload=DataRef(
        source="salesforce",
        query="SELECT Id, Stage, Amount FROM Opportunity WHERE AccountId='001abc' ",
        point_in_time=datetime(2026, 4, 13, 14, 30, tzinfo=UTC),
        cache_policy="invalidate_on_event",
    ),
    ...
)
```

At retrieval, the router dispatches to the live source using cached credentials, applies the point-in-time query, returns current truth.

### Tradeoffs to design for

| Concern | Without Zero-Copy | With Zero-Copy | Mitigation |
|---|---|---|---|
| Latency | 10ms local read | 100ms–1s remote | Per-query cache keyed by `(source, query, point_in_time)` |
| Staleness | ETL lag (minutes to hours) | None (always live) | — |
| Credentials | One-time at ingest | Every retrieval | Broker model: retrieval router holds short-lived tokens, not long-lived secrets |
| Offline | Data is local, always available | Source-down = retrieval fails | Stale-while-revalidate with `cache_policy="ttl"`; journal records the staleness event |
| API quota | None at query time | Counts against source quotas | Query coalescing at the router, cache by default, explicit opt-in for `cache_policy="always"` |
| PII | Duplicated to Paw storage (GDPR liability) | Stays at source (GDPR-friendly) | — |
| Point-in-time correctness | N/A | Requires source support | Where absent (some REST APIs), record "best-effort at T" and accept drift; journal is transparent about it |

### Not a replacement for copy-on-ingest

Static sources — internal docs, handbook PDFs, onboarding guides — still copy-on-ingest because copying is cheap, queries are frequent, and point-in-time doesn't matter. `DataRef` is for live systems where freshness and data-residency matter more than retrieval latency. The router picks between the two based on the source's registered type.

### Replay semantics (non-hermetic — bounded to DataRef events)

DataRef events are live-only by design. The retrieval-router projection that resolves them is explicitly **non-hermetic** — replaying a `retrieval.query` event with a DataRef payload against a source that is down, rate-limited, or whose schema has changed will produce a different result (or a failure) than the original query. This is acknowledged, not a bug.

Every other event action namespace — `memory.*`, `kb.*`, `fabric.*`, `decision.*`, governance events — uses inline dict payloads and remains **hermetic**: projections rebuild deterministically from the journal alone, without external dependencies. The non-hermetic surface is isolated to `retrieval.query` events that carry DataRef payloads; those events are semantically receipts of live queries, not reproducible facts.

Projections that consume DataRef events must declare themselves DataRef-aware. Consumers that are not DataRef-aware (soul memory tier rebuild, kb-go compile cascade, fabric view rebuild) either do not subscribe to `retrieval.query` events, or subscribe only to the structured metadata fields (actor, ts, scope, causation_id) and ignore the payload.

---

## Projections — how today's stores fit

Each current store becomes a *projection* of the journal: a materialized view optimized for a specific read pattern. Projections are rebuildable from the journal; the journal is rebuildable from nowhere.

| Current store | Becomes | Primary read pattern | Write path |
|---|---|---|---|
| Soul memory tiers | Projection: identity + bounded recent-N per tier | Semantic/episodic recall, OCEAN queries | Journal `memory.*` events → soul snapshot rebuild |
| kb-go wiki | Projection: compiled articles + BM25 index | "What do we know about X" | Journal `kb.source.ingested` events → kb-go compile cascade |
| Fabric objects (#938) | Projection: scoped object store with filter-at-retrieval | "Give me all visible deals in Q3" | Journal `fabric.object.*` events → Fabric view rebuild |
| Retrieval log (#936) | *Deleted as a separate store* | "What did the agent retrieve" | Filter over journal `retrieval.query` events |

### What this fixes immediately

- **Four `datetime.now()` bugs** become one implementation at the journal layer. One `UTC` call, one format, one test.
- **Two missing audit events** disappear — the audit *is* the journal. Graduation-apply's lack of an audit event was a bug only because graduation had its own write path.
- **Same scope-normaliser bug in three files** gets consolidated: scope normalisation happens at journal write time, shared across all write paths.
- **Retrieval log vs. RetrievalTrace duplication** resolves — RetrievalTrace is the event payload shape for `retrieval.query` events; the log is a filter over the journal.

### Rebuild semantics

Every projection exposes a `rebuild_from_journal(start_event_id: UUID | None = None)` function. Starting fresh is `start_event_id=None` — replay the whole journal. For incremental projection updates, the projection records its last-seen event ID and resumes from there. This is standard event-sourcing; no novelty required.

---

## Storage

### Tiers

| Tier | Backend | When | Capacity |
|---|---|---|---|
| **v1 default** | SQLite WAL, single file `journal.db` | Always. Default for every install. | ~100GB before degrading |
| **Cold tier** | Parquet partitions + DuckDB query layer | Events older than N months (default 6) | TB-scale, analytics-friendly |
| **Enterprise multi-node** | Postgres | Optional backend, opt-in via config | Horizontally scalable |

The journal's API (`append`, `query`, `replay_from`) does not change across tiers. The storage backend is pluggable. Orgs start on SQLite; archival happens via a scheduled migrator; enterprise multi-node is a flag.

### Why SQLite is the right v1

- **Zero-ops.** Fits the sovereign / self-host promise. No database to run.
- **WAL handles concurrency.** Multiple writers on one file via WAL mode work fine up to the order-of-magnitude we need.
- **Portable.** `journal.db` is one file. `paw os export` tarballs it with the souls and configs. No dump/restore ceremony.
- **Queryable.** SQLite is SQL. Projections read via prepared statements; external tooling works out of the box.
- **Battle-tested at scale.** 281 trillion SQLite databases in the wild. Not a bet; a default.

---

## Security Model

### Signing

- Every governance event (onboarding, admin changes, scope mutations, schema migrations) is signed by root's current keypair.
- Day-to-day events (retrievals, memory writes, kb ingests) are signed by the originating agent's keypair. Root is not in the loop for these.
- Signatures are optional in v1 (`sig` field nullable), mandatory for governance events from v1.1, mandatory for all events from v2.

### Key Rotation

Root key compromise is the worst-case scenario. Rotation flow:

1. `key.rotated` event, signed by m-of-n admin users (default: 2 of 3). This is the only event that root itself does not sign — it authorises a new root keypair.
2. Old keys marked revoked in the journal.
3. New keys become the active signing identity from that event forward.
4. Past events remain signed by old keys and stay valid — the chain is append-only, history doesn't get re-signed.
5. Verifiers (the retrieval router, external auditors) follow key-rotation events to know which key was active at each `ts`.

### Credential broker (Zero-Copy)

The retrieval router becomes the credential broker for external sources. Three rules:

1. **Short-lived tokens only.** No long-lived secrets held in process memory beyond the minimum.
2. **Per-scope token scoping.** A token usable for `org:sales:*` cannot be used by an agent operating under `org:support:*`.
3. **Every token fetch is a journal event.** `credential.acquired` / `credential.used` / `credential.expired` — audit is built in, not bolted on.

### Threat model notes

- **Prompt injection via external data** — `DataRef` payloads returning hostile content must be sanitised at the retrieval router, before handoff to any agent. This is where the existing 7-layer stack's output filter lives.
- **Journal tamper** — hash-chain + signing prevents undetected modification. Detection is via chain verification at startup and on every admin CLI read.
- **Root key theft** — mitigated by hardware-backed keys (Secure Enclave / TPM). Full compromise requires m-of-n rotation, with the paper trail in the journal.

---

## Migration from Today's Primitives

### Order of operations

Each step is a merge-able increment that ships value on its own and does not break the steps before it.

**Phase 1 — Land the primitive.**
1. Add `EventEntry`, `Actor`, `DataRef` to `soul-protocol/spec/` with Pydantic models and round-trip tests.
2. Add `engine/journal/` module with SQLite WAL backend, `append` / `query` / `rebuild_from` APIs.
3. Add `paw os init` CLI — the onboarding wizard above, minus the starter-fleet step (deferred until Phase 3).

**Phase 2 — Retrofit the soul.**
4. Extend `Soul` to optionally back writes via the journal when `journal_path` is configured. Pure `.soul` mode (no journal) remains supported for standalone use.
5. Add `Soul.rebuild_from_journal()`.
6. Mark soul file as a snapshot/cache; journal becomes truth.

**Phase 3 — Redirect today's stores.**
7. Retrieval log (#936) writes redirect to journal `retrieval.query` events. Existing log API becomes a filter view. Delete separate storage.
8. Fabric object writes (#938) emit `fabric.object.created/updated` events, Fabric view rebuilds from those. The current schema migration blocker from today's review is fixed at the journal layer, not per-store.
9. Graduation apply (#937) emits `graduation.applied` events — the missing audit blocker closes by construction.

**Phase 4 — Ship the moat.**
10. Define `agent.proposed` and `human.corrected` event types. Wire channel adapters and dashboard UI to emit them on every agent-output-then-human-edit interaction.
11. Extend soul graduation to include decision-trace patterns: recurring corrections of the same kind graduate from episodic to semantic memory with confidence scores.

**Phase 5 — Zero-Copy.**
12. Extend retrieval router to dispatch `DataRef` payloads to registered source adapters.
13. Ship one adapter end-to-end — Google Drive is the easiest target (revision API gives clean point-in-time semantics, OAuth is well-trodden).
14. Expand adapter set based on customer demand.

**Phase 6 — Vertical templates.**
15. With the journal, the soul hierarchy, scope-tree bootstrap, and starter fleets all in place, a vertical template is reduced to: an archetype persona, a set of pocket scopes, a fleet of agents, a DataRef configuration for common sources, and a starter kb corpus. Hospitality / Events / Sales / Support become packageable.

### Rough timeline

Phases 1–3: 4 weeks. Phase 4: 1 week (small once the journal exists). Phase 5: 2–3 weeks for infra plus 1 week per adapter. Phase 6: ongoing.

### Risks during migration

- **Double-write window.** Phases 2–3 require writing to both the journal and the existing store until reads are cut over. Extend `/test-writer` coverage to verify both paths stay in sync during the overlap.
- **Soul backward compatibility.** Existing `.soul` files need to keep working on any Paw OS version that ships the journal. Treat the journal as additive until v2.
- **Event schema evolution.** Add-only. `EventEntry.action` strings are namespaced; new types can appear without breaking old consumers. Removing an action is a schema migration event, not an edit.

---

## What Ships First

Minimum reviewable cut for the first PR:

1. `soul_protocol.spec.journal` — `EventEntry`, `Actor`, `DataRef` Pydantic models, round-trip tests, docstrings locking semantics.
2. `soul_protocol.engine.journal` — SQLite WAL backend, `append` / `query` / `replay_from` APIs, migration helper to create the schema on first write.
3. `soul paw os init` — wizard that writes the genesis event.
4. Two pages of user-facing docs under `soul-protocol/docs/`: "Journal concepts" and "The root agent."

This matches the existing spec-PR pattern from #161 and #162: ship the primitive first, wire it to real workloads in follow-up PRs. Around 600–900 LOC, under a week of focused work.

---

## Open Questions

Worth resolving before coding starts:

1. **Hash-chain v1 or v2?** Optional in v1 keeps the model simpler. Mandatory in v1 enforces tamper-evidence from day one but adds verification overhead on every read. Lean toward optional-v1 with strong-by-default config.
2. **Clock skew on multi-writer setups.** Hybrid logical clocks add complexity. Single-writer-per-org is the default; do we ship HLCs in v1 or defer to v2?
3. **Event payload size limit.** Suggest 64KB cap with DataRef for anything larger. Settles the "don't put blobs in the journal" rule.
4. **Pocket-as-scope formalisation.** The current Paw codebase treats pockets as first-class objects. This RFC repositions them as scope nodes. Needs a deprecation path — probably a `pocket.created` event shipping a scope that matches the existing object's id.
5. **Multi-admin quorum default.** 2-of-3 feels right for SMBs. What about 1-of-1 (solo founder) — do we allow it, with a migration path to m-of-n when the second admin lands?
6. **Cross-org references.** If agent A in Org X talks to agent B in Org Y, does the event land in both journals? In one with a reference to the other? This is the "federation" story and probably deserves its own RFC.
7. **Naming.** "Root agent" is clear but generic. "Kernel", "Genesis", "Nerve", "Paw" — the name matters for the narrative. Captain's call.
8. **Dashboard journal query API.** The RFC specifies `append / query / replay_from` at the engine layer. The FastAPI surface the paw-enterprise dashboard reads through (to render pocket activity, agent feeds, retrieval views) needs its own design — filter shape, pagination, real-time subscription, scope-enforcement wrapping. This needs to be specced before Phase 3 redirects pocket writes, or the UI will be temporarily broken. Suggest a follow-up RFC focused on the read side.
9. **DataRef replay is bounded non-hermetic (resolved above).** The open question is whether we want a *snapshot-on-write* escape hatch — an optional mode where the engine resolves the DataRef inline at write time and caches the snapshot alongside the reference. Useful for audit-heavy deployments where every recorded query must be reproducible even if the source disappears. Cost: defeats some Zero-Copy value. Lean: ship the non-hermetic default first, add snapshot-on-write as an opt-in flag if customers ask for it.

---

## Appendix: Initial Event Type Catalog

Namespaced, dot-separated, past-tense verbs. Grow the list conservatively.

### Governance (root-signed)
- `org.created` — genesis, exactly one per instance
- `schema.migrated` — structural journal or soul-format change
- `user.admin_granted` / `user.admin_revoked`
- `scope.created` — at the top level; lower-level scope creation can be team-signed
- `key.rotated` — root key rotation, m-of-n co-signed
- `paw.os.destroyed` — terminal

### Identity
- `agent.spawned` / `agent.retired`
- `user.joined` / `user.left`
- `team.created` / `team.disbanded`
- `soul.exported` / `soul.imported`

### Memory & Knowledge
- `memory.remembered` / `memory.graduated` / `memory.forgotten`
- `kb.source.ingested` / `kb.article.compiled` / `kb.article.revised`

### Retrieval & Fabric
- `retrieval.query` — carries RetrievalTrace payload
- `fabric.object.created` / `fabric.object.updated` / `fabric.object.archived`
- `scope.assigned` / `scope.revoked` — for specific principals

### Decisions (the moat)
- `agent.proposed` — with proposal payload
- `human.corrected` — with `causation_id` to the proposal and corrected version
- `decision.graduated` — a correction pattern promoted to semantic memory

### Credentials & Zero-Copy
- `credential.acquired` / `credential.used` / `credential.expired`
- `dataref.resolved` — one per Zero-Copy query resolution, with latency and cache status

### Graduation & Policy
- `graduation.applied`
- `policy.evaluated` — one per scope-filter check at retrieval

---

## Next Steps

1. Captain review + open questions resolved.
2. First PR scoped per "What Ships First" above.
3. Follow-up RFC for cross-org federation if/when that becomes a real need.

