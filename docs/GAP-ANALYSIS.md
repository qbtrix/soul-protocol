<!--
  GAP-ANALYSIS.md — what is shipped vs what is missing in soul-protocol.
  Updated: 2026-05-25 — rewrite against 0.5.0.dev0 surface. Previous version
  (2026-03-06, scored against the 0.2.2 vision baseline) is preserved in git
  history. Most of the original "missing" rows have shipped through the 0.3.x
  spec/runtime work, the 0.4.0 identity bundle (multi-user, layers + domains,
  trust chain), and the 0.5.0.dev0 memory + evaluation primitives.
-->

# Soul Protocol — Gap Analysis

> [!NOTE]
> **Last refreshed:** 2026-05-25 against soul-protocol **v0.5.0.dev0** (CHANGELOG `[Unreleased]` + last tagged release `0.4.0`).
> **Previous version:** March 2026, scored against the 0.2.2 vision baseline. Preserved in git history.

This document is a working answer to one question: **what is genuinely missing from soul-protocol today?** It's written for two readers — a third-party runtime author deciding whether the spec is complete enough to target, and a contributor looking for a real gap to close.

Every "shipped" row is grounded in `CHANGELOG.md`, `docs/SPEC.md`, or `src/soul_protocol/`. Every "missing" row was verified against the same sources before being listed.

---

## 1 · Status header

| Aspect | State |
|---|---|
| Spec version | **0.4.0** (`docs/SPEC.md`) |
| Reference runtime | **0.5.0.dev0** (`pyproject.toml`, on `dev`; tagged release pending) |
| Last shipped release | 0.4.0 — 2026-04-29 ("identity bundle") |
| Standard vs runtime split | Headless standard since 0.3.3; spec lives in `soul_protocol.spec.*` |
| Conformance suite | Planned (`tests/conformance/`, target 0.4.x) — not shipped yet |
| Module layout | `spec/` (contract) · `runtime/` (reference impl) · `engine/` (org journal) · `cli/` · `mcp/` · `optimize/` · `eval/` |

---

## 2 · What is now shipped

Capabilities that the March 2026 gap analysis listed as missing or partial but have since landed. Each row carries the release that introduced it so a downstream reader can pin a minimum version.

### 2.1 · Identity, multi-user, and access control

| Capability | Since | Notes |
|---|---|---|
| Multi-user souls (`user_id` on `MemoryEntry`, `Soul.observe`, `Soul.recall`) | 0.4.0 (#46) | One soul, multiple humans, per-user context isolation. Filters include `None` entries for legacy back-compat. |
| Open-string memory layers + `domain` namespacing | 0.4.0 (#41) | `LAYER_CORE`/`EPISODIC`/`SEMANTIC`/`PROCEDURAL`/`SOCIAL` as built-in constants, plus arbitrary user-defined layers. `domain` defaults to `"default"`. |
| `social` layer + `SocialStore` | 0.4.0 (#41) | Relationship memory tier for per-user bond / preference / trust signal storage. |
| `DomainIsolationMiddleware` + `DomainAccessError` | 0.4.0 (#41) | Allow-list enforcement on cross-domain reads and writes. |
| Per-user bond strength + `BondTarget` list | 0.2.5 → 0.4.0 | `Identity.bonds: list[BondTarget]` replaces the deprecated `bonded_to` string; auto-migration on load. |
| System prompt safety guardrails (`Soul.to_system_prompt`) | 0.3.3 (#185) | Default safety section declines requests for core memory, bond details, evolution history. Opt out for transparent deployments. |
| `Soul.public_profile()` | 0.3.3 (#185) | Safe-to-expose subset of identity for registries / agent cards. Excludes memory contents and bond details. |
| `MemoryVisibility` tier (`PUBLIC`/`BONDED`/`PRIVATE`) | 0.2.5 (#114) | Recall is filtered by requester identity and bond strength. |

### 2.2 · Trust chain (signed action history)

| Capability | Since | Notes |
|---|---|---|
| Ed25519-signed Merkle-style chain (`TrustEntry`, `TrustChain`) | 0.4.0 (#42) | Spec primitives in `soul_protocol.spec.trust`; verifier helpers `verify_chain`, `verify_entry`, `chain_integrity_check`, `compute_payload_hash`, `compute_entry_hash`. |
| `Ed25519SignatureProvider` + `Keystore` | 0.4.0 (#42) | Public/private key pair stored under `keys/`. `Soul.export(include_keys=False)` (default) keeps chain verifiable without leaking the signing key. |
| Auto-append hooks on consequential actions | 0.4.0 (#42) | Memory writes (observe), supersedes, forgets, evolution proposed/applied, learning events, and bond strengthen/weaken all sign automatically. |
| `soul verify` + `soul audit` CLI + `soul_verify` / `soul_audit` MCP tools | 0.4.0 (#42) | `verify` exits 1 on tampering; `audit` prints a Rich timeline filterable by action prefix. |
| Timestamp monotonicity in `verify_chain` | 0.5.0.dev0 (#199) | Rejects entries backdated by more than 60s past the previous entry; closes a head-replacement backdating gap. |
| Strict canonical JSON for hashing | 0.5.0.dev0 (#200) | `_canonical_json` raises `TypeError` on non-JSON-native values rather than `default=str`-coercing; hash determinism across Python versions enforced. |
| Public-API typing guard on `compute_payload_hash` | 0.5.0.dev0 (#205) | Refuses `BaseModel` inputs at the entry point; prevents dict-vs-model hash drift. |
| Key rotation allow-list (`Keystore.previous_public_keys`) | 0.5.0.dev0 (#204) | `verify_chain` accepts the current key OR any allow-listed prior key; default empty list preserves 0.4.0 strict behaviour. `keys/previous.keys` persists alongside the active pair. |
| Non-cryptographic `TrustEntry.summary` | 0.5.0.dev0 (#201) | Short human-readable description per entry, excluded from canonical bytes so it's editable without breaking verification. `soul audit` renders a Summary column. |
| Structured chain-append-failure logging | 0.5.0.dev0 (#202) | `runtime.chain_append_skipped` + `runtime.bond_callback_failed` at WARNING; routine read-only skips stay at DEBUG. |
| Touch-time chain pruning | 0.5.0.dev0 (#203) | `Biorhythms.trust_chain_max_entries` (default 0 = unbounded); positive values compress old entries into a signed `chain.pruned` marker. New `soul prune-chain` CLI + `soul_prune_chain` MCP tool. Full archival design deferred to 0.5.x. |

### 2.3 · Memory primitives and update verbs

| Capability | Since | Notes |
|---|---|---|
| Vector / embedding search | 0.2.5 → present | `runtime/embeddings/` ships `HashEmbedder`, `TFIDFEmbedder`, `SentenceTransformerProvider`, `OpenAIEmbeddingProvider`, `OllamaEmbeddingProvider`, `VectorSearchStrategy`. `get_embedding_provider()` factory with lazy imports. |
| Real cognitive engine adapters | 0.2.5 → present | `AnthropicEngine`, `OpenAIEngine`, `OllamaEngine`, `LiteLLMEngine`, `CallableEngine`, `MCPSamplingEngine` under `runtime/cognitive/adapters/`. |
| Dream cycle (offline batch consolidation) | 0.3.0 | `Soul.dream()` + `soul dream` CLI. Topic clusters, recurring procedures, behavioural trends, graph consolidation, cross-tier synthesis. Pure heuristic, no LLM required. |
| Smart recall (LLM rerank with prompt-injection defence) | 0.3.0 | `Soul.smart_recall()`. Hardened with content sanitisation, `BEGIN/END MEMORIES` fence, 30s timeout, clean fallback to heuristic order. |
| Significance short-circuit | 0.3.0 | `observe()` skips entity extraction + self-model update on low-significance interactions when fact extraction also returns nothing. |
| Archival tier + auto-consolidation | 0.2.9 | `MemoryManager.archive_old_memories()` compresses episodic > 48h into `ConversationArchive`. `observe()` auto-triggers every `consolidation_interval` interactions. |
| Progressive recall (L0 abstract overflow) | 0.2.9 | `recall(progressive=True)` returns primary entries + abstract overflow. |
| Supersede with two-way provenance | 0.4.0 (#193) → 0.5.0.dev0 (#192) | `Soul.supersede(old_id, new_content)` sets `old.superseded_by = new.id` AND `new.supersedes = old.id`. `Soul.last_recall_provenance` walks back to the oldest known version. |
| `Soul.confirm`, `Soul.update`, `Soul.forget`, `Soul.purge`, `Soul.reinstate` | 0.5.0.dev0 (#192) | Prediction-error gated, one-hour reconsolidation window. `confirm` refreshes activation (PE ~0); `update` patches in place (PE 0.2-0.85, recall-within-window); `supersede` ≥0.85; `forget` shifts to weight-decay (0.05, below recall floor); `purge` is the GDPR hard-delete with `.soul.bak`; `reinstate` restores weight to 1.0. Out-of-band PE raises `PredictionErrorOutOfBandError`; out-of-window `update` raises `ReconsolidationWindowClosedError`. |
| Dedup-aware writes (`Soul.note`) | 0.5.0.dev0 (#231) | Runs new content through `reconcile_fact()` (Jaccard + containment) before storing. Returns `{action: "CREATE"\|"SKIP"\|"MERGE", id, existing_id, similarity}`. Episodic memories bypass dedup (events are unique by time). Per-domain isolation. New `soul note` CLI. |
| `MemoryEntry` additive fields | 0.5.0.dev0 (#192) | `retrieval_weight: float = 1.0`, `supersedes: str \| None = None`, `prediction_error: float \| None = None`. Pydantic backfills on awaken — pre-0.5 souls round-trip without migration code. |
| `MemoryManager.recall(min_weight=0.1)` + `Soul.recall(include_superseded=True)` | 0.5.0.dev0 (#192) | Filter by retrieval weight; opt-in surfacing of superseded back-edges. |

### 2.4 · Graph traversal and typed entity ontology

| Capability | Since | Notes |
|---|---|---|
| `Soul.graph` view with `nodes/edges/neighbors/path/subgraph/to_mermaid/reachable/stats` | 0.5.0.dev0 (#108, #190) | In-memory dict + adjacency-list backing; `to_dict`/`from_dict` round-trip; pre-0.5.0 graphs load cleanly. |
| Eight built-in entity kinds | 0.5.0.dev0 (#190) | `person`, `place`, `org`, `concept`, `tool`, `document`, `event`, `relation` — plus open-string extension. |
| Eight built-in relation predicates | 0.5.0.dev0 (#190) | `mentions`, `related`, `depends_on`, `contributes_to`, `causes`, `follows`, `supersedes`, `owned_by` — plus open-string. |
| `Soul.recall(graph_walk={...})` with pagination + budget | 0.5.0.dev0 (#190) | `{"start": entity_id, "depth": 2, "edge_types": [...]}`; `page_token` + `token_budget`; new `RecallResults` carries `next_page_token`, `total_estimate`, `truncated_for_budget`. Legacy callers still get `list[MemoryEntry]`. |
| Trust-chain hooks for graph mutations | 0.5.0.dev0 (#190) | `observe()` appends `graph.entity_added` and `graph.relation_added` for net-new entities/edges. |
| `soul graph` CLI group | 0.5.0.dev0 (#190) | `nodes`/`edges`/`neighbors`/`path`/`mermaid`, all with `--json`. Plus `soul_graph_query` MCP tool. |

### 2.5 · Evaluation, optimization, and diff tooling

| Capability | Since | Notes |
|---|---|---|
| Soul-aware evals (YAML + runner) | 0.5.0.dev0 (#160) | `soul_protocol.eval` ships `runner.py`, `schema.py`, `scoring.py`. Five scoring kinds: `keyword`, `regex`, `semantic` (Jaccard + containment), `judge` (LLM-as-judge), `structural`. `respond` vs `recall` modes; deterministic fallback without an engine. New `soul eval` CLI + `soul_eval` MCP tool. Five example specs under `tests/eval_examples/`. Full doc at `docs/eval-format.md`. |
| Autonomous self-improvement (`soul optimize`) | 0.5.0.dev0 (#142) | `soul_protocol.optimize.OptimizeRunner`, `optimize()` entry point, `Knob` protocol + four built-in knobs (`OceanTraitKnob`, `PersonaTextKnob`, `SignificanceThresholdKnob`, `BondThresholdKnob`), `Proposer` (LLM + heuristic fallback), `OptimizeResult`/`OptimizeStep` models. Defaults to dry-run; `--apply` keeps wins and writes one `soul.optimize.applied` trust-chain entry per kept change. New `soul optimize` CLI + `soul_optimize` MCP tool. Full doc at `docs/soul-optimize.md`. |
| Structured `soul diff` | 0.5.0.dev0 (#191) | Soul-level (not byte-level) comparison across identity, OCEAN/DNA, state, core memory, memories per layer + per domain, bond, skills, trust chain, self-model, evolution. Formats: text (Rich), `--format json` (`SoulDiff` Pydantic dump), `--format markdown`. New public API: `soul_protocol.runtime.diff_souls`, `SoulDiff`, `SchemaMismatchError`. |

### 2.6 · Journal + decision traces

| Capability | Since | Notes |
|---|---|---|
| Append-only org journal (SQLite WAL) | 0.3.1 (#172) | Atomic `seq` allocation, opportunistic hash chain for tamper evidence. `EventEntry`, `Actor`, `DataRef` in `soul_protocol.spec.journal`. |
| `Journal.query(action_prefix=...)` + `Journal.append` returns committed entry | 0.3.3 (#179) | The five spec primitives that any conforming impl must provide. |
| Decision traces (`agent.proposed`, `human.corrected`, `decision.graduated`) | 0.3.1 (#168) | Causation chains, cluster recurring patterns. |
| `decision.outcome_attached` journal action | post-0.4.0 (#255) | Attach observed outcomes to a prior decision. |
| `soul journal init/append/query` shell-hook CLI | 0.5.0.dev0 (#189) | Wraps the org journal for non-Python runtimes and CI scripts. JSONL stdin batching; committed entries echoed to stdout for downstream causation. `--at <iso>` for point-in-time replay. |
| `RetrievalTrace` receipt on every recall | 0.3.1 (#161) | `Soul.last_retrieval` exposes query, candidate set, rerank decisions, final selection. |
| `MemoryEntry.scope` + `match_scope` bidirectional matcher | 0.3.1 (#162) + fix (#175) | DSP scope grammar (`org:sales:*`, `agent:<id>`, `session:<id>`). |

### 2.7 · CLI / MCP surface

| Capability | Since | Notes |
|---|---|---|
| CLI commands (current count: ~50) | running total | `birth`, `awaken`, `inspect`, `status`, `list`, `delete`, `init`, `export`, `unpack`, `migrate`, `retire`, `remember`, `note`, `recall`, `layers`, `observe`, `reflect`, `dream`, `feel`, `prompt`, `forget`, `supersede`, `confirm`, `update`, `purge`, `reinstate`, `upgrade`, `edit-core`, `evolve`, `evaluate`, `learn`, `skills`, `bond`, `events`, `context`, `health`, `cleanup`, `repair`, `verify`, `audit`, `prune-chain`, `inject`, `eternal-status`, `template list/show/create`, `org init/status/destroy`, `import-soulspec`, `export-soulspec`, `import-tavernai`, `export-tavernai`, `export-a2a`, `import-a2a`, plus subcommand groups for `journal`, `diff`, `eval`, `optimize`, `graph`. |
| MCP server | 0.2.3 → 0.5.0.dev0 | FastMCP-based, 28+ tools (per `docs/mcp-server.md`), 2 prompts. Added in 0.5.0.dev0: `soul_eval` (#160), `soul_optimize` (#142), `soul_prune_chain` (#203); 0.5.0.dev0 memory primitives: `soul_confirm`, `soul_update`, `soul_supersede`, `soul_purge`, `soul_reinstate`. |
| Inject targets for IDE integration | 0.3.x | `soul inject --target {claude-code, cursor, vscode, windsurf, cline, continue}`. Marker-based idempotent replacement. |
| Format importers / exporters | 0.2.5 | SoulSpec (SOUL.md / soul.json), TavernAI Character Card V2 (JSON + PNG tEXt chunks, no Pillow), Google A2A Agent Cards (`soul export-a2a` / `soul import-a2a`). |
| Bundled role archetype templates | 0.3.1 (#163) | Arrow, Flash, Cyborg, Analyst. `load_template()` + `soul template` CLI. |
| Safety net: dry-run by default on `soul forget` and `soul cleanup` | 0.3.3 (#181) | `.soul.bak` written before destructive saves. `--apply` required to execute. Closes #148. |

### 2.8 · Documentation surface

| Doc | Status |
|---|---|
| `docs/SPEC.md` | Authoritative language-agnostic contract. Versioned at 0.4.0. |
| `docs/architecture.md` | Reference implementation internals. |
| `docs/api-reference.md` | Public Python API. 1,302 lines. |
| `docs/cli-reference.md` | CLI command reference. 1,450 lines. |
| `docs/memory-architecture.md` | Memory subsystem deep dive. Updated for 0.5.0.dev0 update primitives. |
| `docs/trust-chain.md` | Threat model, key management, sharing souls safely. Touch-time pruning section added in 0.5.0.dev0. |
| `docs/eval-format.md` | YAML eval spec + runner walkthrough. New in 0.5.0.dev0. |
| `docs/soul-optimize.md` | Autoresearch loop, knob catalog, dry-run semantics. New in 0.5.0.dev0. |
| `docs/rfc-memory-update-primitives.md` | Cog-sci grounding for the 0.5.0.dev0 memory verbs (Nader/LeDoux on reconsolidation, Sevenster/Beckers/Kindt on PE, Bjork/Wimber on forgetting). |
| `docs/org-journal-spec.md` | Framework-agnostic journal wire format. |
| `docs/mcp-server.md` | MCP setup, tool catalog, sampling engine. |
| `docs/wiki/` | 328 auto-generated articles (rebuilt in 0.4.0 via #186). |

---

## 3 · What is still missing

Honest gaps, verified against `src/soul_protocol/` and the CHANGELOG. Each row distinguishes "real gap" from "intentionally application-layer."

### 3.1 · Real gaps (likely candidates for issues)

| Gap | Status | Notes |
|---|---|---|
| Real IPFS / Arweave / blockchain providers | Mock only | `runtime/eternal/providers/` ships `local.py` plus `mock_ipfs.py`, `mock_arweave.py`, `mock_blockchain.py`. The `EternalStorageProvider` protocol is real and stable; no provider talks to a live network. `soul archive` flow exists but resolves to mock CIDs / TXIDs. |
| Cross-soul federation / handoff protocol | Spec draft only | Multi-soul coordination is described in the DSP v0.5.0 draft (Tuckman lifecycle, transitive trust decay, reputation scoring, handoff). No runtime implementation yet. |
| Vector DB backends (Chroma, Pinecone, Qdrant, Weaviate) | Not implemented | `EmbeddingProvider` + `VectorSearchStrategy` exist and are stable. No store-side adapter ships — all vector search runs over in-memory tier files. |
| Persistent graph backends (Neo4j, JanusGraph) | Not implemented | `Soul.graph` is in-memory dict + adjacency list. Production-scale graphs would need an external store. |
| Conformance test suite (`tests/conformance/`) | Planned (0.4.x), not shipped | Without it, third-party impls can't self-certify "0.4.0 compliant" mechanically. |
| Streaming wire protocol for real-time soul sync | Not addressed | No spec section, no runtime. Souls move as `.soul` archives only. |
| Mobile / browser runtime | Not in scope of this repo | The Python reference impl is server-side / CLI / MCP. No JS/TS port, no IndexedDB backend, no React Native wrapper. A separate repo would carry this. |
| Hardware wallet / HSM key custody | Not implemented | `Keystore` reads / writes Ed25519 keys from local files. No PKCS#11 / WebAuthn / Ledger / Trezor integration. |
| Encrypted-at-rest `.soul` export by default | Functions exist, not wired | `runtime/crypto/encrypt.py` ships Fernet + PBKDF2; `Soul.export()` does not encrypt by default. Passphrase-encrypted export remains opt-in. |
| `soul rotate-keys` CLI | Not shipped | Allow-list infrastructure landed in #204; the rotation command itself is intentionally not in 0.5.0.dev0. Callers can rotate manually by editing `Keystore.previous_public_keys`. |
| Full trust-chain archive (`trust_chain/archive/` with checkpoints) | Deferred to 0.5.x | The 0.5.0.dev0 touch-time pruning (#203) is the stub. The full archival design with checkpoint entries is tracked but not implemented. |
| Streak tracking on `SoulState` | Not implemented | Vision originally described `streak: <int>` for consecutive interaction days. Not in `types.py`. |
| Mobile-format identity carriers (QR-encoded `.soul` summary, NFC export) | Not addressed | No spec, no runtime. |
| Multi-language reference impls (Rust / Go / TS) | Not in this repo | The spec is now language-agnostic (0.3.3+) and a third-party can target it. None ship from us. |

### 3.2 · Partial / shaped but not finished

| Item | Current state | What's left |
|---|---|---|
| Memory compression / SimpleMem-style recursive consolidation | Dream cycle handles topic clustering + dedup; archival tier compresses old episodic. | Recursive multi-level summarisation (summary-of-summaries) not implemented. |
| Working memory tier | Vision concept — runtime treats this as the caller's session buffer. | No `WorkingMemoryStore` exists. Probably stays the caller's responsibility. |
| Automatic evolution triggers | `evolution/manager.py` runs supervised/autonomous approval flows; `check_triggers()` still a placeholder. | Threshold-based auto-proposals from accumulated `EvaluationHistory` are not wired. The signal exists (#160 evals, #142 optimize); a direct evolution loop on top is the next step. |
| Skills decay + XP | `Skill.decay()` shipped 0.2.9; significance-weighted XP grants shipped 0.2.9. | Per-skill config (level-up gates, decay curves per skill) is hard-coded; not yet driven by a per-skill manifest. |

---

## 4 · What is deferred (intentional)

These are not gaps — they're explicit "application-layer, not part of the standard" decisions documented in `docs/SPEC.md` or the relevant CHANGELOG entry.

| Item | Why it's deferred |
|---|---|
| Concrete `RetrievalRouter` orchestration | Removed from `soul_protocol.engine.retrieval` in 0.3.3 (#179). Now in pocketpaw at `pocketpaw.retrieval`. Spec only defines the `SourceAdapter` / `CredentialBroker` / `RetrievalRequest` / `RetrievalCandidate` vocabulary; orchestration belongs to the consuming runtime. |
| `InMemoryCredentialBroker`, `ProjectionAdapter`, `MockAdapter` | Same move — application-layer / test helpers, not part of the standard. |
| SaaS-specific source adapters (Drive, Slack, Salesforce, etc.) | Adapters are the consuming runtime's job. The spec defines the Protocol; pocketpaw ships the concrete adapters today, third-party runtimes would ship their own. |
| LangChain / Vercel AI / "framework adapter" integrations | Soul Protocol is consumer-agnostic by design. Anything LangChain-specific lives downstream of the `CognitiveEngine` protocol and the `.soul` file. |
| Reconsolidation-window persistence | The one-hour window in `Soul.update()` is in-memory only, capped at 1000 LRU entries. Modelled after cellular destabilisation; persisting it would distort the cog-sci grounding. |

---

## 5 · Track-by-track summary

A reader trying to map remaining work to milestones can read this as a roadmap snapshot.

| Track | Where it is | Next likely step |
|---|---|---|
| **Identity & access control** | Largely complete after 0.4.0. Multi-user, layers + domains, signed history all shipped. | Cross-soul federation (DSP v0.5.0 draft → runtime). |
| **Memory** | Strongest area. Vector + heuristic + graph + dream + evals + optimize all shipped. | Recursive summarisation; persistent graph + vector backends. |
| **Trust chain** | Verifiable, prunable, observable. | Full archival design (deferred 0.5.x); `soul rotate-keys` CLI; HSM custody. |
| **Evals + optimize** | New in 0.5.0.dev0. Foundation for evolution-driven self-improvement. | Wire `OptimizeRunner` results into automatic evolution triggers. |
| **Eternal storage** | Protocol stable; only mock providers ship. | Real IPFS provider; real Arweave provider; spec for content-addressed soul recovery. |
| **Standard maturity** | Headless standard since 0.3.3; SPEC.md tracks 0.4.0. | Conformance test suite (`tests/conformance/`); first non-Python reference impl. |
| **Distribution** | Python wheel + sdist on PyPI; MCP server for Claude Desktop / Cursor / etc. | Mobile / browser runtime out of scope here; would be a separate repo. |

---

## 6 · How this doc stays honest

- Refresh on each major release (next: when 0.5.0 tags). Section 2 grows; Section 3 shrinks or migrates rows into Section 2 with a `since` value.
- Anything claimed as "shipped" must point at a CHANGELOG row or a file in `src/soul_protocol/`.
- Anything claimed as "missing" must have been verified by reading the current code, not by reading an old version of this doc.
- Previous editions of this file live in git history (`git log -- docs/GAP-ANALYSIS.md`). The March 2026 version with the original 0.2.2 vision-baseline scoring is at commit `eaaeebd` ± neighbouring commits.
