<!--
  SPEC.md — Soul Protocol, the standard.
  Updated: 2026-04-29 (v0.4.0 identity bundle) — added user_id and domain
  fields on MemoryEntry, open-string layers replacing the fixed five-tier
  enum (with the original five preserved as built-in layer names + new
  optional 'social' layer), and the trust chain primitives (TrustEntry,
  TrustChain, SignatureProvider, verification helpers). Bumped the
  conformance level and noted the migration story for 0.3.x souls.
  Created: 2026-04-19 (feat/0.3.3-prune-retrieval-infra) — companion to the
  0.3.3 retrieval prune. This doc describes what Soul Protocol IS, as a
  standard, independent of our Python reference implementation. Anyone
  implementing Soul Protocol in another language (or a custom runtime)
  reads this file.

  Runtime implementation details — algorithms, SQLite schemas, async
  strategies, test patterns — belong in docs/architecture.md, not here.
-->

# Soul Protocol — The Standard

> Soul Protocol is a portable, open standard for persistent AI identity, memory, and retrieval. This document is language-agnostic. It describes what Soul Protocol is, independent of how our Python reference implementation happens to build it.

Version: **0.4.0** (spec) · Status: **draft, breaking-change-free since 0.3**

If you are **building on top of our Python implementation**, start with [README.md](../README.md) and [docs/architecture.md](./architecture.md). If you are **implementing Soul Protocol in another language** (Rust, Go, TypeScript, etc.) or a custom runtime, this document is the authoritative contract.

---

## 1 · What Soul Protocol is

Four concerns bundled into one standard:

1. **Identity** — every soul has a DID, a persona, OCEAN personality traits, values, and an evolution history. As of 0.4.0, a soul can serve multiple users, and memory entries can be attributed to a `user_id`.
2. **Memory** — open-string layers (core, episodic, semantic, procedural, graph, social, plus any user-defined layer) with psychology-informed activation semantics and optional `domain` namespacing for context isolation.
3. **Event substrate** — an append-only journal that records every consequential change to a soul or an org, scope-stamped and tamper-evident.
4. **Trust chain** (0.4.0) — a per-soul append-only log of signed entries (memory writes, evolution steps, learning events, bond changes) so a soul can prove what it learned and where. Ed25519-signed Merkle-style hash chain, verifiable without an external key registry.

A **.soul file** carries (1), the relevant memory slice of (2), and (4) — it is a zip archive that any Soul Protocol implementation can read, write, and export from. An **org journal** carries (3) — a single SQLite database (or equivalent) that sits alongside one or more souls.

Everything else the reference implementation ships — psychology pipeline algorithms, retrieval orchestration, MCP server, CLI, web UI — is a *consumer* of this standard, not part of it.

---

## 2 · The `.soul` file format

A `.soul` file is a ZIP archive with a fixed directory layout. Any implementation must be able to read and write this layout.

```
<name>.soul/
├── identity.json         — Identity (below)
├── dna.json              — DNA (personality traits + communication style + biorhythms)
├── memory/               — Built-in layer tier files (legacy flat layout)
│   ├── core.jsonl        — MemoryEntry records, layer=core
│   ├── episodic.jsonl    — MemoryEntry records, layer=episodic
│   ├── semantic.jsonl    — MemoryEntry records, layer=semantic
│   ├── procedural.jsonl  — MemoryEntry records, layer=procedural
│   ├── graph.jsonl       — MemoryEntry records, layer=graph (entity relationships)
│   ├── social.jsonl      — MemoryEntry records, layer=social (relationship memory) [optional, 0.4.0+]
│   ├── _layout.json      — Optional layout marker (presence implies nested layout below) [0.4.0+]
│   └── <layer>/<domain>/entries.jsonl  — Nested layout for non-default-domain or custom-layer entries [0.4.0+]
├── skills/
│   └── <skill_name>.md   — Procedural capabilities with XP tracking
├── bonds/
│   └── <bond_id>.json    — Relationship state (BondTarget records)
├── trust_chain/          — Signed action history [0.4.0+, optional but expected if keys/ present]
│   ├── chain.json        — Canonical TrustChain serialization
│   └── entry_NNN.json    — One file per entry (NNN is zero-padded seq, for human inspection)
├── keys/                 — Cryptographic identity for the trust chain [0.4.0+]
│   ├── public.key        — Raw 32-byte Ed25519 public key (always shipped when the soul has signed at least once)
│   └── private.key       — Raw 32-byte Ed25519 private key (shipped only when include_private=true on export)
├── evolution.jsonl       — Append-only history of personality / trait mutations
└── manifest.json         — Container-level metadata (schema_version, created_at, owner)
```

**Invariants a conforming implementation must honor:**

- All timestamps in files are ISO-8601 with timezone offset (UTC recommended). Naive datetimes are invalid.
- JSONL files use one record per line, UTF-8, LF line endings, trailing newline optional.
- `manifest.json` includes `schema_version: "0.4.0"` (or the version the file was written against).
- A reader encountering a `schema_version` newer than it supports must fail loud, not silently drop fields.
- File-level mutations are additive within a version: new fields may appear but existing fields do not disappear or change meaning without a major version bump.
- A reader of a 0.4.0+ archive must accept either the legacy flat layout (`memory/<layer>.jsonl` only) or the nested layout (`memory/<layer>/<domain>/entries.jsonl`). Presence of `memory/_layout.json` indicates the nested layout is in use; absence implies flat. The two layouts must produce identical reader outputs for a soul whose entries all use `domain="default"`.
- A reader of a 0.4.0+ archive must accept the absence of `trust_chain/` and `keys/` (legacy 0.3.x souls). When present, both directories' contents are subject to verification per §12.

See `soul_protocol.spec.soul_file` in the reference impl for `pack_soul()` / `unpack_soul()` / `unpack_to_container()` — the codec surface any implementation must reproduce.

---

## 3 · Identity

```
Identity {
  did:         str     # "did:soul:<slug>" — stable across exports
  name:        str
  persona:     str     # short description agents inject into their own prompts
  values:      [str]   # free-form value strings, e.g. ["sovereignty", "accessibility"]
  created_at:  datetime
}
```

`did` is the canonical handle. It must be stable across `.soul` export / import cycles. The slug portion is locally unique within an org.

---

## 4 · Memory

### 4.1 · Built-in layers + open-string layer model (0.4.0)

A `MemoryEntry` belongs to exactly one **layer**. As of 0.4.0, the layer is an arbitrary string — implementations are not required to enforce a fixed enum. The reference implementation ships seven built-in layers with conventional names; user code may define additional ones.

| Layer | Meaning | When to write |
|---|---|---|
| `core` | Identity-level facts always in context ("who am I") | Rarely — these are load-bearing |
| `episodic` | Events that happened ("what occurred at time T") | Most interactions |
| `semantic` | General knowledge ("what I know") | Facts the soul should recall, not events |
| `procedural` | How-to knowledge, recipes, procedures | Skills, learned patterns |
| `graph` | Entity relationships (soul→entity→entity edges) | Links between people, orgs, concepts |
| `social` (0.4.0+) | Relationship memory — bonds, trust, communication preferences per user | When a soul updates how it relates to a specific user |
| *user-defined* (0.4.0+) | Any string the implementation accepts | Application-specific namespaces |

Pre-0.4.0 archives encode the layer in a `tier` field. 0.4.0+ archives encode it in `layer`. A reader **must** accept either field name; if both are present, `layer` wins.

### 4.2 · MemoryEntry

```
MemoryEntry {
  id:           UUID
  layer:        str          # 0.4.0+ — see §4.1. Pre-0.4.0 readers see this as `tier`.
  content:      str
  importance:   float        # 0.0..10.0, caller-assigned baseline
  scope:        [str]        # DSP scope patterns — see §7
  visibility:   MemoryVisibility   # "private" | "shared" | "public"
  created_at:   datetime
  emotion:      str | None   # optional emotional tag
  access_count: int          # incremented on recall
  last_accessed_at: datetime | None
  metadata:     dict[str, Any]

  # Identity bundle (0.4.0)
  user_id:      str | None   # The user this memory is attributed to.
                             # None = orphan / soul-default. Filtering by
                             # user_id includes None entries (legacy
                             # back-compat).
  domain:       str          # Sub-namespace within the layer. Default
                             # "default". Use to isolate context, e.g.
                             # "finance", "legal", "personal". Domain
                             # isolation enforcement is application-layer.
}
```

Pre-0.4.0 souls have neither `user_id` nor `domain`. On read, an implementation must accept their absence and treat them as `user_id=None`, `domain="default"` so legacy entries surface in every recall.

### 4.3 · Psychology-informed activation (outputs, not algorithms)

When an implementation writes a memory, it must compute and record (directly or via metadata):

- **Somatic marker** — emotional valence of the write event. The reference impl uses Damasio's somatic-marker theory; other impls may derive this differently. Required: a scalar the recall phase can use.
- **Activation** — starts at 1.0 on write, decays over time. The reference impl uses ACT-R's decay; other impls may use different decay curves. Required: activation decreases monotonically absent re-access.
- **Significance** — a gate that filters "trivial" memories from expensive downstream operations (dream consolidation, graph edges). The reference impl uses LIDA-style global workspace scoring; other impls may use simpler heuristics. Required: memories have a boolean or scalar "significant enough" flag.

These are spec *outputs*, not spec *algorithms*. A Rust implementation does not need to port Damasio/ACT-R/LIDA line-for-line. It needs to produce comparable outputs so merged souls behave consistently across implementations.

### 4.4 · Recall contract

```
recall(query: str, *, limit: int, min_importance: float = 0) -> list[MemoryEntry]
```

- Results ordered by descending relevance × activation × importance (relative weighting up to implementation).
- `access_count` and `last_accessed_at` updated on every return.
- Filtering by `scope` (caller's scope context) applied before limit and ranking.

---

## 5 · DNA (personality)

```
DNA {
  ocean:               OCEAN     # openness, conscientiousness, extraversion, agreeableness, neuroticism (0..1)
  communication_style: CommunicationStyle  # verbosity, formality, humor, directness (0..1)
  biorhythms:          Biorhythms | None   # circadian preferences
  values:              [str]
  emotional_baseline:  Mood
}
```

DNA is the slow-moving part of identity. It is mutated through the **evolution** subsystem — see §6.

---

## 6 · Evolution

Evolution is how souls change over time without losing portability. Every mutation is an append-only `EvolutionEvent` recorded in `evolution.jsonl`.

```
EvolutionEvent {
  id:          UUID
  ts:          datetime
  kind:        Literal["trait_mutation", "skill_level_up", "bond_deepened", ...]
  before:      dict            # previous state of the mutated field
  after:       dict            # new state
  trigger:     str             # free-form cause description
  importance:  float
}
```

An implementation may apply its own triggers, thresholds, and mutation strategies. What it must not do is mutate DNA, skills, or bonds silently — every change is recorded here.

---

## 7 · Scope grammar

Soul Protocol uses a dotted, wildcard-capable scope string.

```
<segment>         ::= [a-z0-9_-]+
<scope>           ::= <segment> ( ":" <segment> )* ( ":*" )?
<example>         ::= "org:sales:leads"
                  ::= "org:sales:*"
                  ::= "user:alice"
                  ::= "fleet:hospitality:front-desk"
```

**Matching rule:** scope A matches scope B if A == B, or if one is a prefix of the other where the longer side ends in `*`. Wildcard-grant + specific-requester matches. Specific-grant + wildcard-requester matches. Disjoint scopes do not match.

All writes to the journal carry a non-empty `scope` list. All reads filter by caller scope context before aggregation.

---

## 8 · The Journal

### 8.1 · Append-only, hash-chained, UTC-stamped

The org journal is the substrate that every Soul Protocol consumer (pocketpaw, future Rust runtimes, third-party agents) writes to for consequential events.

```
EventEntry {
  id:              UUID
  ts:              datetime             # tz-aware UTC
  actor:           Actor                # kind + id + scope_context
  action:          str                  # dot-separated, past-tense, e.g. "memory.semantic.added"
  scope:           [str]                # MUST be non-empty
  causation_id:    UUID | None          # which event caused this one
  correlation_id:  UUID | None          # groups related events (a request, an install, etc.)
  payload:         dict | DataRef       # JSON-serializable; no Pydantic/class values
  prev_hash:       bytes | None         # hash link to previous entry
  sig:             bytes | None         # optional signature
  seq:             int                  # auto-incremented on append
}

Actor {
  kind:          str                    # "user" | "system" | "service"
  id:            str                    # stable identifier, e.g. "user:alice", "system:widget-graduation"
  scope_context: [str]                  # caller's scopes at the time
}
```

### 8.2 · Invariants

- No UPDATE, no DELETE, no truncate. Rows are written once, read forever.
- `ts` is timezone-aware UTC. Naive datetimes raise at validation time.
- `scope` is required and non-empty. No implicit "global" write path.
- `action` is a free-form dot-separated string. The reference impl ships `ACTION_NAMESPACES` as a catalog, but implementations may add new namespaces additively.
- `payload` is JSON-serializable — plain `dict` or a typed `DataRef` (see §9). Never a class instance.
- `seq` is monotonic and unique. A writer appending to the journal receives the committed `EventEntry` back — see §8.3.
- `prev_hash` forms a hash chain. An implementation may verify the chain on read; any break indicates tampering or corruption.

### 8.3 · Journal contract (0.3.3)

```
append(entry: EventEntry) -> EventEntry    # returns the committed entry w/ seq + prev_hash
query(
    *,
    action: str | None = None,
    action_prefix: str | None = None,      # added 0.3.3 — prefix match on dot-separated action
    actor_kind: str | None = None,
    actor_id: str | None = None,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
    since_seq: int = 0,
    until_seq: int | None = None,
    since_ts: datetime | None = None,
) -> Iterable[EventEntry]
replay_from(since_seq: int = 0) -> Iterable[EventEntry]
```

Implementations may add query dimensions (e.g., scope, payload-field) but must support the above at minimum.

### 8.4 · DataRef (journal-layer — query recipe)

Journal payloads may contain a `DataRef` instead of an inline `dict` when the data lives outside the journal and should be resolved on demand:

```
DataRef {
  source:         str              # adapter name, e.g. "drive", "salesforce"
  query:          str | None
  scopes:         [str]
  point_in_time:  datetime | None  # UTC
}
```

See also §9 for the **retrieval-layer** `DataRef`, which identifies a specific candidate returned by a `SourceAdapter`. The two share a name because they share the concept "pointer to external data" but operate at different granularities.

---

## 9 · Retrieval

The spec defines the vocabulary. Concrete routers, brokers, and adapters live in the consuming runtime.

### 9.1 · RetrievalRequest

```
RetrievalRequest {
  query:           str                # free-text or source-native query
  actor:           Actor
  scopes:          [str]              # caller's scope context, non-empty
  correlation_id:  UUID | None
  sources:         [str] | None       # explicit allowlist, or all-registered if None
  limit:           int                # default 20
  strategy:        Literal["first", "parallel", "sequential"]  # default "parallel"
  timeout_s:       float              # default 10.0
  point_in_time:   datetime | None    # UTC. Added 0.3.3 — native time-travel field
}
```

### 9.2 · RetrievalCandidate + DataRef (retrieval-layer)

> **Naming note.** The retrieval-layer `DataRef` is re-exported from `soul_protocol.spec` as `RetrievalDataRef` to distinguish it from the journal-layer `DataRef` (see §8.4, query recipe used in `EventEntry.payload`). Inside `spec/retrieval.py` itself it is named `DataRef`; at the `soul_protocol.spec` package boundary it surfaces as `RetrievalDataRef`. Language bindings should expose both names so consumers can disambiguate. The two types are intentionally distinct: the journal `DataRef` is "resolve this query at this moment," the retrieval `DataRef` is "this specific record from this source at this revision."


```
RetrievalCandidate {
  source:   str
  content:  dict | DataRef            # DataRef for zero-copy, dict for projection sources
  score:    float | None
  as_of:    datetime                  # UTC
  cached:   bool
}

DataRef {
  kind:         Literal["dataref"]
  source:       str
  id:           str                   # stable identifier in the source system
  scopes:       [str]
  revision_id:  str | None            # point-in-time identifier
  extra:        dict
}
```

### 9.3 · Protocols

```
SourceAdapter (Protocol) {
  supports_dataref: bool

  query(request: RetrievalRequest, credential: Credential | None)
    -> list[RetrievalCandidate]
}

AsyncSourceAdapter (Protocol) {
  query(...)                          # sync method present too
  async aquery(request, credential) -> list[RetrievalCandidate]   # 0.3.3
}

CredentialBroker (Protocol) {
  acquire(source: str, scopes: [str]) -> Credential
  ensure_usable(credential: Credential, requester_scopes: [str]) -> None
  mark_used(credential: Credential) -> None
  revoke(credential_id: UUID) -> None
}
```

### 9.4 · Credential

```
Credential {
  id:            UUID
  source:        str
  scopes:        [str]        # non-empty
  token:         str          # opaque bearer
  acquired_at:   datetime     # UTC
  expires_at:    datetime     # UTC
  last_used_at:  datetime | None
}
```

### 9.5 · Exception hierarchy

```
RetrievalError              (base)
├── NoSourcesError          (no registered source matched scopes/list)
├── SourceTimeoutError      (adapter did not return within timeout)
├── CredentialScopeError    (credential used outside its scope)
├── CredentialExpiredError  (credential used after TTL elapsed)
└── PointInTimeNotSupported (adapter can't honor time-travel field; router records and continues)
```

### 9.6 · What is not in the spec

- `RetrievalRouter` — the orchestrator that fans out across sources, applies strategies, handles timeouts, emits `retrieval.query` journal events. **Application-layer.** The reference implementation (Python) ships it inside pocketpaw.
- `InMemoryCredentialBroker` — a concrete broker. **Application-layer.** Production deployments use their platform's secret store.
- `ProjectionAdapter`, `MockAdapter` — concrete adapters. **Application-layer / test helpers.**

A third-party runtime implementing Soul Protocol provides these for itself. The spec only pins the interfaces they implement.

---

## 10 · CognitiveEngine

The spec defines the single-method interface agents use to invoke their underlying LLM.

```
CognitiveEngine (Protocol) {
  think(prompt: str) -> str
}
```

A `CognitiveEngine` is the agent's thinking substrate — Claude, GPT-4, local Ollama, whatever. The protocol is deliberately minimal: string in, string out. Streaming, tool use, vision, etc., are consumer-level concerns built on top.

---

## 10A · Trust chain (0.4.0)

Every soul carries an append-only log of signed entries — the trust chain. One entry per audit-worthy action: a memory write, a memory supersede, a forget, an evolution proposal, an evolution apply, a learning event, a bond change, or any other action a runtime considers significant. Reading a soul's chain answers "what did this soul do, and can I prove it?"

### 10A.1 · TrustEntry

```
TrustEntry {
  seq:          int         # monotonic 0-indexed
  timestamp:    datetime    # UTC, ISO-8601
  actor_did:    str         # DID of the signer (usually the soul's own DID)
  action:       str         # dot-namespaced ("memory.write", "evolution.applied", ...)
  payload_hash: str         # SHA-256 hex of the canonical JSON of the action's payload
  prev_hash:    str         # SHA-256 hex of the previous entry, or GENESIS_PREV_HASH for seq=0
  signature:    str         # base64 of the raw signature bytes
  algorithm:    str         # signing algorithm; default "ed25519"
  public_key:   str         # base64 of the raw public key used to verify (32 bytes for ed25519)
}
```

The full payload is **not stored** — only its SHA-256 hash. This keeps the chain compact and avoids redundant storage of memory contents that already live in their own tier files. A verifier with the original payload and the chain entry can prove the payload existed at signing time.

### 10A.2 · Canonical encoding

Both signers and verifiers must use the same canonical JSON encoding:

- Sorted keys
- Separators `(",", ":")` (no whitespace)
- `ensure_ascii=true` (unicode escaped)
- Datetimes serialized via `isoformat()`, UTC-normalized

The hash of an entry is computed over the canonical JSON of every field **except `signature`** (the signature is the result of signing; it cannot be part of its own input). This hash is what the next entry's `prev_hash` must equal.

### 10A.3 · GENESIS_PREV_HASH

```
GENESIS_PREV_HASH = "0" * 64
```

A constant 64 hex zeros. Anchors the chain at seq=0; an attacker cannot pretend to lop off the head since the genesis prev_hash is fixed.

### 10A.4 · TrustChain

```
TrustChain {
  did:     str
  entries: [TrustEntry]   # ordered ascending by seq, no gaps
}
```

### 10A.5 · SignatureProvider (Protocol)

```
SignatureProvider {
  algorithm:  str
  public_key: str

  sign(message: bytes) -> str         # returns base64 signature
  verify(message: bytes, signature: str, public_key: str) -> bool
}
```

The reference implementation ships `Ed25519SignatureProvider`. Other implementations may add P-256, secp256k1, etc. — provided the `algorithm` field on each entry identifies which one was used.

### 10A.6 · Verification contract

A conforming verifier checks each entry sequentially. The chain is valid iff every entry passes:

1. **Chain link.** For seq=0: `prev_hash == GENESIS_PREV_HASH`. For seq>0: `prev_hash` matches `compute_entry_hash(prev_entry)` AND `seq == prev.seq + 1`.
2. **Signature.** `verify(canonical_json_minus_signature, signature, public_key) == true`.
3. **No duplicates.** No two entries share a `seq` value.
4. **Future timestamps.** Entry's timestamp is no more than 60 seconds beyond the verifier's local clock (skew tolerance).

The verifier returns the seq of the first failure plus a reason string. An empty chain is trivially valid.

### 10A.7 · Identity binding

The chain itself proves *some key* signed these entries. To prove **this soul** signed them, an implementation must additionally check that every entry's `public_key` matches the soul's loaded keystore public key. The reference implementation enforces this in `Soul.verify_chain()`. Implementations that only verify chain-internal consistency MUST NOT claim "soul X performed these actions" — they can only claim "this is a self-consistent chain."

### 10A.8 · Threat model summary

The chain detects: tampering with past entries, forged signatures, mid-chain insertion, reordering, replay, future-timestamped entries.

The chain does NOT defend against: head truncation (a receiver-side concern — pin the latest known head externally), private-key compromise (rotate keys), censorship of which actions get recorded (the chain only attests to what was signed), payload confidentiality (only hashes on the chain — protect the payload files themselves), or external-time correctness (use a timestamping service if you need that).

### 10A.9 · Optionality

The trust chain is **optional** for 0.4.0 conformance. Souls without a `keys/` or `trust_chain/` directory in their archive remain valid 0.4.0 souls — they simply cannot prove provenance. An implementation that wants to claim full 0.4.0 conformance must also support the chain (read, write, verify); a partial implementation that only handles identity + memory + journal is allowed to ship as "0.4.0 (no trust chain)."

---

## 11 · Conformance

An implementation **claims Soul Protocol 0.4.0 compliance** when it can:

- [ ] Read and write `.soul` files at schema_version 0.4.0 (§2), accepting both the legacy flat memory layout and the nested `memory/<layer>/<domain>/entries.jsonl` layout
- [ ] Honor the memory layer semantics including the open-string layer model and the `domain` namespacing (§4.1, §4.2)
- [ ] Round-trip 0.3.x souls into 0.4.0 form (treat absent `user_id` as None, absent `domain` as `"default"`, absent `layer` as the legacy `tier` value)
- [ ] Implement the `Journal.append` / `Journal.query` contract including `action_prefix` (§8)
- [ ] Emit scope-non-empty `EventEntry` records with UTC timestamps (§8)
- [ ] Round-trip `.soul` files produced by the reference impl without field loss (§2)
- [ ] Implement the `CognitiveEngine` protocol (§10)

**Optional extension — Trust Chain (§10A):**

- [ ] Read, write, and verify `TrustChain` records
- [ ] Bind verification to the loaded keystore public key (§10A.7) — required if claiming "verifiable history" in marketing
- [ ] Generate Ed25519 keypairs and sign new entries

An implementation may claim "0.4.0 (no trust chain)" if it implements all the required boxes but skips the trust chain extension.

Retrieval infrastructure (Router/Broker/Adapter implementations) is explicitly NOT required for compliance — it is application-layer.

A conformance test suite lives in the reference implementation under `tests/conformance/` (planned — 0.4.x).

---

## 12 · Versioning

- **Patch** (0.3.1 → 0.3.3) — additive fields, new query parameters, new exported types. Non-breaking.
- **Minor** (0.3.x → 0.4.0) — backward-compatible structural changes. Implementations may need to upgrade but old `.soul` files still read. The 0.4.0 minor introduced multi-user attribution (`user_id`), open-string layers + `domain` namespacing, and the optional trust chain.
- **Major** (0.x → 1.0) — reserved for the first stable release.

The reference implementation may release patch versions faster than the spec. Spec versions advance only when the contract changes.

---

## 13 · Reference implementation

The reference implementation lives in this repository under `src/soul_protocol/`:

```
src/soul_protocol/
├── spec/           # This document's contract, as Python types + Protocols.
│                   # Zero imports from opinionated modules. Implements §2–§10.
├── engine/         # Substrate implementations (currently: the journal).
├── runtime/        # Reference algorithms (psychology pipeline, memory managers,
│                   # dream consolidation, retrieval-over-memory, ...)
├── cli/            # CLI reference tool (soul command).
├── mcp/            # MCP server reference tool.
└── spike/          # Experimental modules. NOT part of the shipped API.
```

See [docs/architecture.md](./architecture.md) for the detailed internal layout. Other runtimes (Rust, Go, TypeScript) implement against §2–§10 of this document and are free to ignore `engine/`, `runtime/`, `cli/`, `mcp/`.

---

## See also

- [docs/architecture.md](./architecture.md) — reference implementation's internal architecture.
- [docs/org-journal-spec.md](./org-journal-spec.md) — deeper dive on the journal, its scope grammar, and the decision-trace vocabulary on top of it.
- [docs/memory-architecture.md](./memory-architecture.md) — reference impl's memory subsystem in depth.
- [docs/cognitive-engine.md](./cognitive-engine.md) — how to wire a concrete LLM into the `CognitiveEngine` protocol.
